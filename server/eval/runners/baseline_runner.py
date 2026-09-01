"""Baseline evaluation runner — 4-area metrics over MVP dataset."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SERVER_ROOT = Path(__file__).resolve().parents[2]
if str(_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVER_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_SERVER_ROOT / ".env")

from modules.db import SessionLocal  # noqa: E402
from server.eval.fixtures.seed_db import seed_eval_participant  # noqa: E402
from server.eval.metrics.final_answer import score_final_answer  # noqa: E402
from server.eval.metrics.rag import score_rag  # noqa: E402
from server.eval.metrics.routing import score_routing  # noqa: E402
from server.eval.metrics.sql import score_sql  # noqa: E402
from server.eval.runners.agent_runner import run_eval_example  # noqa: E402
from server.eval.schemas.dataset import EvalExample  # noqa: E402


def load_dataset(path: Path) -> list[EvalExample]:
    examples: list[EvalExample] = []
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                examples.append(EvalExample.model_validate(json.loads(line)))
            except Exception as exc:
                raise ValueError(f"{path}:{lineno}: {exc}") from exc
    return examples


def _git_commit() -> str | None:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=_SERVER_ROOT.parent,
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            or None
        )
    except Exception:
        return None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _row_from_result(detail: dict[str, Any]) -> dict[str, Any]:
    routing = detail.get("routing") or {}
    sql = detail.get("sql") or {}
    rag = detail.get("rag") or {}
    final = detail.get("final_answer") or {}
    judgment = final.get("judgment") or {}
    sql_details = sql.get("details") or {}

    return {
        "example_id": detail.get("example_id"),
        "category": detail.get("category"),
        "error": detail.get("error"),
        "tools_used": "|".join(detail.get("tools_used") or []),
        "routing_exact_match": routing.get("exact_match"),
        "routing_precision": routing.get("precision"),
        "routing_recall": routing.get("recall"),
        "routing_f1": routing.get("f1"),
        "sql_skipped": sql.get("skipped"),
        "sql_passed": sql.get("passed"),
        "sql_participant_match": sql_details.get("participant_match"),
        "sql_date_range_match": sql_details.get("date_range_match"),
        "sql_metric_present": sql_details.get("metric_present"),
        "sql_numeric_match": sql_details.get("numeric_match"),
        "sql_reading_count_gt_zero": sql_details.get("reading_count_gt_zero"),
        "rag_skipped": rag.get("skipped"),
        "rag_faithfulness": rag.get("faithfulness"),
        "rag_answer_relevancy": rag.get("answer_relevancy"),
        "rag_context_precision": rag.get("context_precision"),
        "rag_answer_correctness": rag.get("answer_correctness"),
        "final_data_accuracy": judgment.get("data_accuracy"),
        "final_evidence_groundedness": judgment.get("evidence_groundedness"),
        "final_answer_relevance": judgment.get("answer_relevance"),
        "final_safety": judgment.get("safety"),
        "final_overall_quality": judgment.get("overall_quality"),
        "final_safety_pass": final.get("safety_pass"),
    }


def _aggregate(details: list[dict[str, Any]]) -> dict[str, Any]:
    by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for d in details:
        by_cat[str(d.get("category"))].append(d)

    def agg_block(items: list[dict[str, Any]]) -> dict[str, Any]:
        routing_exact = [
            1.0 if (d.get("routing") or {}).get("exact_match") else 0.0
            for d in items
            if d.get("routing")
        ]
        routing_f1 = [
            float((d.get("routing") or {}).get("f1"))
            for d in items
            if (d.get("routing") or {}).get("f1") is not None
        ]
        sql_scored = [
            d
            for d in items
            if d.get("sql") and not (d.get("sql") or {}).get("skipped")
        ]
        sql_pass = [
            1.0 if (d.get("sql") or {}).get("passed") else 0.0 for d in sql_scored
        ]
        rag_vals: dict[str, list[float]] = defaultdict(list)
        for d in items:
            rag = d.get("rag") or {}
            if rag.get("skipped"):
                continue
            for key in (
                "faithfulness",
                "answer_relevancy",
                "context_precision",
                "answer_correctness",
            ):
                if rag.get(key) is not None:
                    rag_vals[key].append(float(rag[key]))
        finals = [d.get("final_answer") or {} for d in items if d.get("final_answer")]
        overall = [
            float((f.get("judgment") or {}).get("overall_quality"))
            for f in finals
            if (f.get("judgment") or {}).get("overall_quality") is not None
        ]
        safety_pass = [
            1.0 if f.get("safety_pass") else 0.0
            for f in finals
            if f.get("safety_pass") is not None
        ]
        return {
            "n": len(items),
            "routing_exact_match_rate": _mean(routing_exact),
            "routing_f1_macro": _mean(routing_f1),
            "sql_pass_rate": _mean(sql_pass),
            "sql_n": len(sql_scored),
            "rag_faithfulness_mean": _mean(rag_vals["faithfulness"]),
            "rag_answer_relevancy_mean": _mean(rag_vals["answer_relevancy"]),
            "rag_context_precision_mean": _mean(rag_vals["context_precision"]),
            "rag_answer_correctness_mean": _mean(rag_vals["answer_correctness"]),
            "final_overall_quality_mean": _mean(overall),
            "final_safety_pass_rate": _mean(safety_pass),
            "error_count": sum(1 for d in items if d.get("error")),
        }

    return {
        "overall": agg_block(details),
        "by_category": {cat: agg_block(items) for cat, items in sorted(by_cat.items())},
    }


def evaluate_example(
    example: EvalExample,
    db,
    *,
    skip_ragas: bool = False,
    skip_judge: bool = False,
) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "example_id": example.id,
        "category": example.category,
        "question": example.question,
        "expected_tools": example.expected_tools,
    }
    try:
        agent_out = run_eval_example(example, db)
    except Exception as exc:  # noqa: BLE001
        detail["error"] = f"agent_failed: {exc}"
        detail["tools_used"] = []
        detail["response"] = ""
        detail["trace"] = None
        return detail

    tools_used = agent_out.get("tools_used") or []
    trace = agent_out.get("trace")
    response = agent_out.get("response") or ""

    detail.update(
        {
            "response": response,
            "sources": agent_out.get("sources"),
            "tools_used": tools_used,
            "trace": trace,
        }
    )

    routing = score_routing(example.expected_tools, tools_used)
    detail["routing"] = routing.model_dump()

    sql_actual = (trace or {}).get("sql_result") if isinstance(trace, dict) else None
    sql = score_sql(
        example,
        sql_actual,
        tool_was_called="query_hrv_data" in tools_used,
    )
    detail["sql"] = sql.model_dump()

    if skip_ragas:
        detail["rag"] = {"skipped": True, "reason": "skip_ragas_flag"}
    else:
        rag = score_rag(
            example,
            answer=response,
            trace=trace if isinstance(trace, dict) else None,
            actual_tools=tools_used,
        )
        detail["rag"] = rag.model_dump()

    if skip_judge:
        detail["final_answer"] = {"skipped": True, "reason": "skip_judge_flag"}
    else:
        final = score_final_answer(
            example,
            answer=response,
            trace=trace if isinstance(trace, dict) else None,
        )
        detail["final_answer"] = final.model_dump()

    return detail


def run_baseline(
    *,
    dataset_path: Path,
    output_dir: Path,
    run_name: str,
    seed_db: bool = True,
    limit: int | None = None,
    ids: list[str] | None = None,
    skip_ragas: bool = False,
    skip_judge: bool = False,
) -> Path:
    examples = load_dataset(dataset_path)
    if ids:
        id_set = set(ids)
        examples = [e for e in examples if e.id in id_set]
        missing = id_set - {e.id for e in examples}
        if missing:
            raise KeyError(f"example ids not found: {sorted(missing)}")
    if limit is not None:
        examples = examples[:limit]

    run_id = f"{run_name}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    details: list[dict[str, Any]] = []
    try:
        if seed_db:
            seed_info = seed_eval_participant(db)
            print(f"seed: {seed_info}")

        for i, example in enumerate(examples, start=1):
            print(f"[{i}/{len(examples)}] {example.id} ({example.category})")
            detail = evaluate_example(
                example,
                db,
                skip_ragas=skip_ragas,
                skip_judge=skip_judge,
            )
            details.append(detail)
            if detail.get("error"):
                print(f"  ERROR: {detail['error']}")
    finally:
        db.close()

    # details.jsonl
    details_path = run_dir / "details.jsonl"
    with details_path.open("w", encoding="utf-8") as f:
        for detail in details:
            f.write(json.dumps(detail, ensure_ascii=False, default=str) + "\n")

    # summary.csv
    rows = [_row_from_result(d) for d in details]
    summary_path = run_dir / "summary.csv"
    fieldnames = list(rows[0].keys()) if rows else ["example_id"]
    with summary_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    aggregates = _aggregate(details)
    metadata = {
        "run_id": run_id,
        "run_name": run_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(dataset_path),
        "n_examples": len(details),
        "git_commit": _git_commit(),
        "models": {
            "agent": os.getenv("GROQ_AGENT_MODEL", "openai/gpt-oss-120b"),
            "judge": os.getenv(
                "GROQ_JUDGE_MODEL",
                os.getenv("GROQ_AGENT_MODEL", "openai/gpt-oss-120b"),
            ),
        },
        "flags": {
            "seed_db": seed_db,
            "skip_ragas": skip_ragas,
            "skip_judge": skip_judge,
            "limit": limit,
            "ids": ids,
        },
        "aggregates": aggregates,
    }
    metadata_path = run_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )

    print(f"wrote {run_dir}")
    print(json.dumps(aggregates["overall"], indent=2, default=str))
    return run_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run MVP baseline evaluation")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("server/eval/datasets/mvp_eval.jsonl"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("server/eval/results"),
    )
    parser.add_argument("--run-name", default="baseline_v1")
    parser.add_argument(
        "--seed-db",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Reseed EVAL_P001 from fixture before run (default: true)",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--ids",
        type=str,
        default=None,
        help="Comma-separated example ids to run",
    )
    parser.add_argument("--skip-ragas", action="store_true")
    parser.add_argument("--skip-judge", action="store_true")
    args = parser.parse_args(argv)

    ids = [x.strip() for x in args.ids.split(",") if x.strip()] if args.ids else None

    try:
        run_baseline(
            dataset_path=args.dataset,
            output_dir=args.output_dir,
            run_name=args.run_name,
            seed_db=args.seed_db,
            limit=args.limit,
            ids=ids,
            skip_ragas=args.skip_ragas,
            skip_judge=args.skip_judge,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
