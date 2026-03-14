# app/models/guardian.py
from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.database import Base

class Guardian(Base):
    __tablename__ = "guardians"

    guardian_id = Column(BigInteger, primary_key=True, autoincrement=True)
    resident_id = Column(BigInteger, ForeignKey("residents.resident_id"), nullable=False)

    name = Column(String(50), nullable=False)
    phone = Column(String(20), nullable=True)

    guardian_type = Column(
        Enum("child", "spouse", "relative", "neighbor", "caregiver", "other"),
        nullable=False,
        default="other",
    )

    is_primary = Column(Integer, nullable=False, default=0)  # tinyint(1) 대응
    priority = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # ✅ 핵심: 문자열로만 참조 (순환 import 방지)
    resident = relationship("Resident", back_populates="guardians")