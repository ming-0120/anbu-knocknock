# app/models/hourly_feature.py
from __future__ import annotations

from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Integer, TIMESTAMP, UniqueConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class HourlyFeature(Base):
    __tablename__ = "hourly_features"

    feature_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    resident_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    # "해당 시간 블록 시작 시각" (정각: minute/second = 0 권장)
    target_hour: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    x1_motion_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    x2_door_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    
    # last motion 이후 경과 분
    x6_last_motion_min: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        UniqueConstraint("resident_id", "target_hour", name="uq_hourly_resident_hour"),
        Index("idx_hourly_target_hour", "target_hour"),
    )