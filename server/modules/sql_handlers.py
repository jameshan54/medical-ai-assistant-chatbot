from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from models.hrv import HRVReading, Participant

def get_participant(db: Session, participant_code: str) -> Participant | None:
    return (
        db.query(Participant)
        .filter(Participant.participant_code == participant_code)
        .first()
    )

def get_hrv_readings(
    db: Session,
    participant_code: str,
    days: int | None = None,
) -> list[HRVReading]:
    participant = get_participant(db, participant_code)
    if participant is None:
        return []

    query = (
        db.query(HRVReading)
        .filter(HRVReading.participant_id == participant.id)
    )

    if days is not None:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = query.filter(HRVReading.recorded_at >= cutoff)

    return query.order_by(HRVReading.recorded_at.desc()).all()

def _avg(values: list[float | None]) -> float | None:
    nums = [v for v in values if v is not None]
    if not nums:
        return None
    return sum(nums) / len(nums)


def _min(values: list[float | None]) -> float | None:
    nums = [v for v in values if v is not None]
    return min(nums) if nums else None


def _max(values: list[float | None]) -> float | None:
    nums = [v for v in values if v is not None]
    return max(nums) if nums else None

def summarize_hrv_readings(readings: list[HRVReading]) -> dict:
    if not readings:
        return {"reading_count": 0}

    dates = [r.recorded_at for r in readings]

    return {
        "reading_count": len(readings),
        "date_from": min(dates).strftime("%Y-%m-%d"),
        "date_to": max(dates).strftime("%Y-%m-%d"),
        "rmssd_avg": _avg([r.rmssd for r in readings]),
        "rmssd_min": _min([r.rmssd for r in readings]),
        "rmssd_max": _max([r.rmssd for r in readings]),
        "coverage_avg": _avg([r.coverage for r in readings]),
        "low_frequency_avg": _avg([r.low_frequency for r in readings]),
        "high_frequency_avg": _avg([r.high_frequency for r in readings]),
    }

def build_sql_result(
    db: Session,
    participant_code: str,
    days: int | None = 90,
) -> dict:
    """Runtime actual only — do not use to generate eval expected values."""
    participant = get_participant(db, participant_code)
    if participant is None:
        return {
            "participant_code": participant_code,
            "days": days,
            "reading_count": 0,
            "error": "participant_not_found",
        }

    readings = get_hrv_readings(db, participant_code, days=days)
    summary = summarize_hrv_readings(readings)
    return {
        "participant_code": participant_code,
        "days": days,
        **summary,
    }


def format_sql_result(result: dict) -> str:
    participant_code = result["participant_code"]
    days = result.get("days")

    if result.get("error") == "participant_not_found":
        return "No participant found for this code."

    if result.get("reading_count", 0) == 0:
        return f"Participant {participant_code} has no HRV readings in the database."

    period = f"last {days} days" if days else "all available data"
    lines = [
        f"Participant code: {participant_code}",
        f"Period: {period} ({result['date_from']} to {result['date_to']})",
        f"Number of readings: {result['reading_count']}",
        (
            f"RMSSD — avg: {result['rmssd_avg']}, "
            f"min: {result['rmssd_min']}, max: {result['rmssd_max']}"
        ),
    ]

    if result.get("coverage_avg") is not None:
        lines.append(f"Coverage — avg: {result['coverage_avg']}")
    if result.get("low_frequency_avg") is not None:
        lines.append(f"Low frequency — avg: {result['low_frequency_avg']}")
    if result.get("high_frequency_avg") is not None:
        lines.append(f"High frequency — avg: {result['high_frequency_avg']}")

    return "\n".join(lines)


def build_sql_context(
    db: Session,
    participant_code: str,
    days: int | None = 30,
) -> str:
    return format_sql_result(build_sql_result(db, participant_code, days=days))

