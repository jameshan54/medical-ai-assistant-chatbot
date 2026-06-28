import csv
import io
from datetime import datetime

from sqlalchemy.orm import Session

from models.hrv import HRVReading, Participant

COLUMN_MAP = {
    "timestamp": "recorded_at",
    "rmssd": "rmssd",
    "coverage": "coverage",
    "low_frequency": "low_frequency",
    "high_frequency": "high_frequency",
}


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    if value == "":
        return None
    return float(value)


def get_or_create_participant(db: Session, participant_code: str) -> Participant:
    participant = (
        db.query(Participant)
        .filter(Participant.participant_code == participant_code)
        .first()
    )

    if participant is None:
        participant = Participant(participant_code=participant_code)
        db.add(participant)
        db.flush()

    return participant


def save_hrv_csv(file_bytes: bytes, participant_code: str, db: Session) -> dict:
    text = file_bytes.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    participant = get_or_create_participant(db, participant_code)

    existing_times = {
        row[0]
        for row in db.query(HRVReading.recorded_at)
        .filter(HRVReading.participant_id == participant.id)
        .all()
    }

    inserted = 0
    skipped = 0

    for row in reader:
        recorded_at = datetime.fromisoformat(row["timestamp"])

        if recorded_at in existing_times:
            skipped += 1
            continue

        rmssd = _to_float(row.get("rmssd"))
        coverage = _to_float(row.get("coverage"))
        low_frequency = _to_float(row.get("low_frequency"))
        high_frequency = _to_float(row.get("high_frequency"))

        reading = HRVReading(
            participant_id=participant.id,
            recorded_at=recorded_at,
            rmssd=rmssd,
            coverage=coverage,
            low_frequency=low_frequency,
            high_frequency=high_frequency,
            source="csv_upload",
        )
        db.add(reading)
        existing_times.add(recorded_at)
        inserted += 1

    db.commit()

    return {"inserted": inserted, "skipped": skipped}