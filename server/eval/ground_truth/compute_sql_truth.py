"""Compute SQL expected metrics from eval fixture CSV (independent of sql_handlers)."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _parse_reference_date(value: str) -> datetime:
    """Parse YYYY-MM-DD as start of that calendar day (UTC-naive)."""
    return datetime.fromisoformat(value)


def compute_sql_truth(
    fixture_path: Path,
    reference_date: datetime,
    days: int,
    participant_code: str = "EVAL_P001",
) -> dict:
    cutoff = reference_date - timedelta(days=days)

    rmssd_values: list[float] = []
    timestamps: list[datetime] = []

    with fixture_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = datetime.fromisoformat(row["timestamp"])
            if ts < cutoff:
                continue
            # Match production lower-bound filter only; fixture should not
            # extend past the eval reference window.
            timestamps.append(ts)
            raw = row.get("rmssd", "").strip()
            if raw:
                rmssd_values.append(float(raw))

    result: dict = {
        "reference_date": reference_date.date().isoformat(),
        "days": days,
        "cutoff": cutoff.isoformat(sep="T"),
        "participant_code": participant_code,
        "reading_count": len(timestamps),
        "rmssd_avg": _avg(rmssd_values),
        "rmssd_min": min(rmssd_values) if rmssd_values else None,
        "rmssd_max": max(rmssd_values) if rmssd_values else None,
        "date_from": min(timestamps).date().isoformat() if timestamps else None,
        "date_to": max(timestamps).date().isoformat() if timestamps else None,
        "provenance": (
            f"fixture:{fixture_path.name}; script:compute_sql_truth.py"
        ),
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compute independent SQL ground truth from seed_hrv.csv"
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("server/eval/fixtures/seed_hrv.csv"),
        help="Path to seed HRV CSV fixture",
    )
    parser.add_argument(
        "--reference-date",
        type=str,
        default="2026-07-12",
        help="Eval reference date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Lookback window in days (production tool default=90)",
    )
    parser.add_argument(
        "--participant-code",
        type=str,
        default="EVAL_P001",
        help="Eval participant code for expected metadata",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("server/eval/ground_truth/sql_expected.json"),
        help="Output JSON path",
    )
    args = parser.parse_args(argv)

    if not args.fixture.exists():
        print(f"ERROR: fixture not found: {args.fixture}", file=sys.stderr)
        return 1

    try:
        reference = _parse_reference_date(args.reference_date)
    except ValueError as exc:
        print(f"ERROR: invalid --reference-date: {exc}", file=sys.stderr)
        return 1

    if args.days < 1:
        print("ERROR: --days must be >= 1", file=sys.stderr)
        return 1

    truth = compute_sql_truth(
        fixture_path=args.fixture,
        reference_date=reference,
        days=args.days,
        participant_code=args.participant_code,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(truth, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"wrote {args.out}")
    print(json.dumps(truth, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
