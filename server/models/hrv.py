# server/models/hrv.py

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modules.db import Base


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    participant_code: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    hrv_readings: Mapped[list["HRVReading"]] = relationship(
        "HRVReading",
        back_populates="participant",
    )


class HRVReading(Base):
    __tablename__ = "hrv_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    participant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("participants.id"),
        nullable=False,
    )

    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)

    rmssd: Mapped[float | None] = mapped_column(Float, nullable=True)
    sdnn: Mapped[float | None] = mapped_column(Float, nullable=True)
    heart_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    source: Mapped[str] = mapped_column(String, default="csv_upload")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    participant: Mapped["Participant"] = relationship(
        "Participant",
        back_populates="hrv_readings",
    )