# app/models/hourly_feature.py
from __future__ import annotations

from datetime import datetime
from sqlalchemy import BigInteger, Column, DateTime, Float, Integer, TIMESTAMP, UniqueConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class HourlyFeature(Base):
    __tablename__ = "hourly_features"

    feature_id = Column(BigInteger, primary_key=True, autoincrement=True)

    resident_id = Column(BigInteger, nullable=False, index=True)
    target_hour = Column(DateTime, nullable=False, index=True)

    x1_motion_count = Column(Integer, default=0)
    x2_door_count = Column(Integer, default=0)

    x3_avg_interval = Column(Float, default=0.0)
    x4_night_motion_count = Column(Integer, default=0)
    x5_first_motion_min = Column(Integer)

    x6_last_motion_min = Column(Integer)

    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    __table_args__ = (
        UniqueConstraint("resident_id", "target_hour", name="uq_hourly_resident_hour"),
        Index("idx_hourly_target_hour", "target_hour"),
    )