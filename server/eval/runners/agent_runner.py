"""Run a single EvalExample through the production agent with trace capture."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy.orm import Session

_SERVER_ROOT = Path(__file__).resolve().parents[2]
if str(_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVER_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_SERVER_ROOT / ".env")

from modules.db import SessionLocal  # noqa: E402
from modules.hrv_agent import run_hrv_agent  # noqa: E402
from server.eval.schemas.dataset import EvalExample  # noqa: E402


def run_eval_example(example: EvalExample, db: Session) -> dict:
    """Invoke agent once; always capture_trace for eval metrics."""
    result = run_hrv_agent(
        example.question,
        db,
        example.participant_code,
        capture_trace=True,
    )
    return {
        "example_id": example.id,
        "category": example.category,
        "question": example.question,
        "participant_code": example.participant_code,
        "response": result["response"],
        "sources": result["sources"],
        "tools_used": result["tools_used"],
        "trace": result.get("trace"),
        "expected_tools": example.expected_tools,
    }


def load_example(dataset_path: Path, example_id: str) -> EvalExample:
    with dataset_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            data = json.loads(line)
            if data.get("id") == example_id:
                return EvalExample.model_validate(data)
    raise KeyError(f"example id not found: {example_id}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one eval example via agent")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("server/eval/datasets/mvp_eval.jsonl"),
    )
    parser.add_argument("--id", required=True, help="EvalExample id, e.g. eval_007")
    args = parser.parse_args(argv)

    try:
        example = load_example(args.dataset, args.id)
    except (OSError, KeyError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        out = run_eval_example(example, db)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()

    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
