"""EvalExample schema + JSONL validation CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, Field, ValidationError, model_validator

SQL_TOOLS = ("query_hrv_data",)
RAG_TOOLS = ("search_research_docs",)
HYBRID_TOOLS = frozenset({"query_hrv_data", "search_research_docs"})


class EvalExample(BaseModel):
    id: str
    question: str
    participant_code: str = "EVAL_P001"
    category: Literal["rag_only", "sql_only", "hybrid", "out_of_scope", "safety"]
    expected_tools: list[str]
    reference_answer: str | None = None
    expected_sources: list[str] = Field(default_factory=list)
    expected_numeric_result: float | None = None
    requires_safety_evaluation: bool = False
    expected_participant_code: str | None = None
    expected_metric: (
        Literal["rmssd_avg", "rmssd_min", "rmssd_max", "reading_count"] | None
    ) = None
    # tool lookback (production=90); NOT fixture data span (30 days)
    expected_date_range_days: int | None = 90
    expected_aggregation: Literal["avg", "min", "max", "count"] | None = None
    numeric_tolerance: float = 0.5
    safety_notes: str | None = None

    @model_validator(mode="after")
    def check_category_tools(self) -> Self:
        tools = self.expected_tools
        cat = self.category

        if cat == "safety":
            if not self.requires_safety_evaluation:
                raise ValueError(
                    f"{self.id}: safety requires requires_safety_evaluation=True"
                )
            if tools:
                raise ValueError(f"{self.id}: safety must have expected_tools=[]")

        elif cat == "out_of_scope":
            if tools:
                raise ValueError(
                    f"{self.id}: out_of_scope must have expected_tools=[]"
                )

        elif cat == "sql_only":
            if tools != list(SQL_TOOLS):
                raise ValueError(
                    f'{self.id}: sql_only expected_tools must be {list(SQL_TOOLS)!r}'
                )
            sql_fields = [
                self.expected_metric,
                self.expected_date_range_days,
                self.expected_aggregation,
                self.expected_numeric_result,
                self.expected_participant_code,
            ]
            if sum(f is not None for f in sql_fields) < 2:
                raise ValueError(
                    f"{self.id}: sql_only needs ≥2 SQL expected fields "
                    "(metric/days/aggregation/numeric_result/participant_code)"
                )

        elif cat == "hybrid":
            if set(tools) != HYBRID_TOOLS or len(tools) != 2:
                raise ValueError(
                    f"{self.id}: hybrid expected_tools must be both "
                    f"{sorted(HYBRID_TOOLS)}"
                )

        elif cat == "rag_only":
            if tools != list(RAG_TOOLS):
                raise ValueError(
                    f"{self.id}: rag_only expected_tools must be {list(RAG_TOOLS)!r}"
                )

        return self


def validate_dataset(path: Path) -> int:
    """Validate each JSONL line. Returns number of errors (0 = success)."""
    if not path.exists():
        print(f"ERROR: dataset not found: {path}", file=sys.stderr)
        return 1

    errors = 0
    count = 0
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            count += 1
            try:
                data = json.loads(line)
                EvalExample.model_validate(data)
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                errors += 1
                print(f"line {lineno}: {exc}", file=sys.stderr)

    if errors:
        print(f"FAILED: {errors}/{count} examples invalid", file=sys.stderr)
    else:
        print(f"OK: {count} examples validated ({path})")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate MVP eval JSONL")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate dataset schema + category/tool rules",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("server/eval/datasets/mvp_eval.jsonl"),
        help="Path to JSONL dataset",
    )
    args = parser.parse_args(argv)

    if not args.validate:
        parser.print_help()
        return 2

    return 1 if validate_dataset(args.dataset) else 0


if __name__ == "__main__":
    raise SystemExit(main())

# python -m server.eval.schemas.dataset --validate --dataset server/eval/datasets/mvp_eval.jsonl