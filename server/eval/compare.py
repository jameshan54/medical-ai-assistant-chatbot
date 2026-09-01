"""Compare two baseline eval runs (metric deltas + regression flags)."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


NUMERIC_COLUMNS = [
    "routing_exact_match",
    "routing_precision",
    "routing_recall",
    "routing_f1",
    "sql_passed",
    "rag_faithfulness",
    "rag_answer_relevancy",
    "rag_context_precision",
    "rag_answer_correctness",
    "final_data_accuracy",
    "final_evidence_groundedness",
    "final_answer_relevance",
    "final_safety",
    "final_overall_quality",
]


def _load_summary(run_dir: Path) -> dict[str, dict[str, Any]]:
    path = run_dir / "summary.csv"
    if not path.exists():
        raise FileNotFoundError(f"missing summary.csv: {path}")
    rows: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows[row["example_id"]] = row
    return rows


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return 1.0 if value.lower() == "true" else 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compare_runs(
    baseline_dir: Path,
    candidate_dir: Path,
    *,
    regression_threshold: float = 0.05,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base = _load_summary(baseline_dir)
    cand = _load_summary(candidate_dir)
    ids = sorted(set(base) | set(cand))

    deltas: list[dict[str, Any]] = []
    regressions = 0
    for example_id in ids:
        b = base.get(example_id, {})
        c = cand.get(example_id, {})
        row: dict[str, Any] = {
            "example_id": example_id,
            "category_baseline": b.get("category"),
            "category_candidate": c.get("category"),
            "in_baseline": example_id in base,
            "in_candidate": example_id in cand,
            "has_regression": False,
        }
        for col in NUMERIC_COLUMNS:
            bv = _to_float(b.get(col))
            cv = _to_float(c.get(col))
            row[f"{col}_baseline"] = bv
            row[f"{col}_candidate"] = cv
            if bv is None or cv is None:
                row[f"{col}_delta"] = None
                row[f"{col}_delta_pct"] = None
                continue
            delta = cv - bv
            row[f"{col}_delta"] = delta
            row[f"{col}_delta_pct"] = (delta / abs(bv)) if bv != 0 else None
            # Higher is better for these metrics; flag drops beyond threshold.
            if delta < -regression_threshold:
                row["has_regression"] = True
        if row["has_regression"]:
            regressions += 1
        deltas.append(row)

    base_meta = {}
    cand_meta = {}
    if (baseline_dir / "metadata.json").exists():
        base_meta = json.loads((baseline_dir / "metadata.json").read_text(encoding="utf-8"))
    if (candidate_dir / "metadata.json").exists():
        cand_meta = json.loads((candidate_dir / "metadata.json").read_text(encoding="utf-8"))

    summary = {
        "baseline": str(baseline_dir),
        "candidate": str(candidate_dir),
        "n_examples": len(ids),
        "n_regressions": regressions,
        "baseline_aggregates": (base_meta.get("aggregates") or {}).get("overall"),
        "candidate_aggregates": (cand_meta.get("aggregates") or {}).get("overall"),
    }
    return deltas, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare two eval runs")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Delta CSV path (default: candidate/compare_vs_baseline.csv)",
    )
    parser.add_argument(
        "--regression-threshold",
        type=float,
        default=0.05,
        help="Absolute drop that flags regression (default 0.05)",
    )
    args = parser.parse_args(argv)

    try:
        deltas, summary = compare_runs(
            args.baseline,
            args.candidate,
            regression_threshold=args.regression_threshold,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    out = args.out or (args.candidate / "compare_vs_baseline.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(deltas[0].keys()) if deltas else ["example_id"]
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(deltas)

    print(json.dumps(summary, indent=2, default=str))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
