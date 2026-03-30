# backend/app/models/risk_score.py

from sqlalchemy import Column, BIGINT, ForeignKey, Numeric, Enum, JSON, DateTime
from datetime import datetime
from sqlalchemy.orm import relationship
from app.db.database import Base


class RiskScore(Base):
    __tablename__ = "risk_scores"

    risk_id = Column(BIGINT, primary_key=True, autoincrement=True)

    # resident 직접 참조 (성능 최적화용)
    resident_id = Column(BIGINT, ForeignKey("residents.resident_id"), nullable=False)

    # 기존 feature FK
    feature_id = Column(BIGINT, ForeignKey("daily_features.feature_id"), nullable=False)

    s_base = Column(Numeric(5, 4), nullable=False)
    score = Column(Numeric(5, 4), nullable=False)

    level = Column(
        Enum("normal", "watch", "alert", "emergency", name="risk_level"),
        default="normal"
    )

    reason_codes = Column(JSON, nullable=True)

    scored_at = Column(DateTime, nullable=False, default=datetime.now)

    daily_feature = relationship("DailyFeature", back_populates="risk_scores")