# app/models/resident.py
from __future__ import annotations

from sqlalchemy import BigInteger, Column, Date, DateTime, Double, String, Text, func
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from app.db.database import Base

DISEASE_MAP = {
    "HTN": "고혈압",
    "DM": "당뇨병",
    "CKD": "만성 신장질환",
    "COPD": "만성 폐질환",
    "HF": "심부전",
    "CAD": "관상동맥질환",
}

class Resident(Base):
    __tablename__ = "residents"

    resident_id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    resident_reg_no = Column(String(20), nullable=False)
    
    phone = Column(String(20), nullable=True)

    address_main = Column(String(150), nullable=False)
    zip_code = Column(String(10), nullable=True)
    address_detail = Column(String(100), nullable=False)

    created_at = Column(DateTime, server_default=func.now())
    lat = Column(Double, nullable=False)
    lon = Column(Double, nullable=False)

    profile_image_url = Column(String(1024), nullable=True)
    gu = Column(String(30), nullable=False)
    # 추가 컬럼
    diseases = Column(String(255), nullable=True)
    medications = Column(String(255), nullable=True)
    living_alone_since = Column(Date, nullable=True)
    note = Column(Text, nullable=True)
    @hybrid_property
    def disease_label(self):
        if not self.diseases:
            return None

        codes = [c.strip().upper() for c in self.diseases.split(",")]

        names = [
            DISEASE_MAP.get(code, code)
            for code in codes
        ]

        return ", ".join(names)
    # ✅ 핵심: 문자열로만 참조 (순환 import 방지)
    guardians = relationship("Guardian", back_populates="resident")