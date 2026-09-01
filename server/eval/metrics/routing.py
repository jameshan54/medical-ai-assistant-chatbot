"""Agent tool-routing metrics (deterministic, no LLM)."""

from __future__ import annotations

from server.eval.schemas.results import RoutingScore


def score_routing(expected: list[str], actual: list[str]) -> RoutingScore:
    exp, act = set(expected), set(actual)
    intersection = exp & act

    if not act and not exp:
        precision = recall = f1 = 1.0
    elif not act:
        precision = 0.0
        recall = 0.0
        f1 = 0.0
    elif not exp:
        # expected=[] but tools were used (e.g. safety / out_of_scope)
        precision = 0.0
        recall = 1.0  # no expected tools were missed
        f1 = 0.0
    else:
        precision = len(intersection) / len(act)
        recall = len(intersection) / len(exp)
        f1 = (
            0.0
            if precision + recall == 0
            else 2 * precision * recall / (precision + recall)
        )

    return RoutingScore(
        exact_match=(exp == act),
        precision=precision,
        recall=recall,
        f1=f1,
        unnecessary_tools=sorted(act - exp),
        missing_tools=sorted(exp - act),
    )
