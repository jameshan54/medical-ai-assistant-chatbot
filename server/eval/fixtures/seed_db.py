"""Idempotent eval DB seed: EVAL_P001 from seed_hrv.csv (does not touch P001)."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

# Allow `from modules...` / `from models...` when run as `python -m server.eval...`
_SERVER_ROOT = Path(__file__).resolve().parents[2]
if str(_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVER_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_SERVER_ROOT / ".env")

from models.hrv import HRVReading  # noqa: E402
from modules.db import SessionLocal  # noqa: E402
from modules.csv_handlers import get_or_create_participant, _to_float  # noqa: E402

DEFAULT_FIXTURE = Path(__file__).resolve().parent / "seed_hrv.csv"
DEFAULT_PARTICIPANT = "EVAL_P001"


def seed_eval_participant(
    db: Session,
    *,
    fixture_path: Path = DEFAULT_FIXTURE,
    participant_code: str = DEFAULT_PARTICIPANT,
) -> dict:
    """Replace readings for participant_code with fixture rows (idempotent exact state)."""
    if not fixture_path.exists():
        raise FileNotFoundError(f"fixture not found: {fixture_path}")

    participant = get_or_create_participant(db, participant_code)

    deleted = (
        db.query(HRVReading)
        .filter(HRVReading.participant_id == participant.id)
        .delete(synchronize_session=False)
    )

    inserted = 0
    with fixture_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            recorded_at = datetime.fromisoformat(row["timestamp"])
            reading = HRVReading(
                participant_id=participant.id,
                recorded_at=recorded_at,
                rmssd=_to_float(row.get("rmssd")),
                coverage=_to_float(row.get("coverage")),
                low_frequency=_to_float(row.get("low_frequency")),
                high_frequency=_to_float(row.get("high_frequency")),
                source="eval_fixture",
            )
            db.add(reading)
            inserted += 1

    db.commit()
    return {
        "participant_code": participant_code,
        "deleted": deleted,
        "inserted": inserted,
        "fixture": str(fixture_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed EVAL_P001 from fixture CSV")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_FIXTURE,
        help="Path to seed_hrv.csv",
    )
    parser.add_argument(
        "--participant-code",
        default=DEFAULT_PARTICIPANT,
        help="Participant code to (re)seed",
    )
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        result = seed_eval_participant(
            db,
            fixture_path=args.fixture,
            participant_code=args.participant_code,
        )
    except Exception as exc:
        db.rollback()
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()

    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
