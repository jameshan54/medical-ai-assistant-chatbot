"""Deterministic SQL tool metrics (no LLM judge)."""

from __future__ import annotations

from server.eval.schemas.dataset import EvalExample
from server.eval.schemas.results import SqlScore


def score_sql(
    example: EvalExample,
    sql_actual: dict | None,
    *,
    tool_was_called: bool | None = None,
) -> SqlScore:
    """Compare trace sql_actual to JSONL expected fields. Never recompute expected."""
    needs_sql = example.category in ("sql_only", "hybrid") or bool(tool_was_called)

    if sql_actual is None:
        if needs_sql:
            return SqlScore(
                skipped=False,
                passed=False,
                details={},
                reason="missing_sql_actual",
            )
        return SqlScore(skipped=True, passed=None, reason="not_applicable")

    details: dict[str, bool | None] = {}

    expected_code = example.expected_participant_code or example.participant_code
    details["participant_match"] = (
        sql_actual.get("participant_code") == expected_code
    )

    expected_days = example.expected_date_range_days or 90
    details["date_range_match"] = sql_actual.get("days") == expected_days

    metric = example.expected_metric
    if metric is None:
        details["metric_present"] = None
        details["numeric_match"] = None
    else:
        details["metric_present"] = (
            metric in sql_actual and sql_actual.get(metric) is not None
        )
        if (
            details["metric_present"]
            and example.expected_numeric_result is not None
        ):
            actual_val = float(sql_actual[metric])
            details["numeric_match"] = (
                abs(actual_val - example.expected_numeric_result)
                <= example.numeric_tolerance
            )
        else:
            details["numeric_match"] = (
                False if example.expected_numeric_result is not None else None
            )

    details["reading_count_gt_zero"] = (sql_actual.get("reading_count") or 0) > 0

    required = [
        details["participant_match"],
        details["date_range_match"],
        details["reading_count_gt_zero"],
    ]
    if metric is not None:
        required.append(details["metric_present"])
        if example.expected_numeric_result is not None:
            required.append(details["numeric_match"])

    passed = all(v is True for v in required)
    return SqlScore(skipped=False, passed=passed, details=details)
