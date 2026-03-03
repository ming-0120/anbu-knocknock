# backend/app/models/risk_score.py
from sqlalchemy import Column, BIGINT, ForeignKey, Numeric, Enum, JSON, DateTime
from datetime import datetime
from sqlalchemy.orm import relationship
from app.db.database import Base

class RiskScore(Base):
    __tablename__ = "risk_scores"

    risk_id = Column(BIGINT, primary_key=True, autoincrement=True)
    
    # 🌟 FK 설정: daily_features 테이블의 feature_id 컬럼을 정확히 가리킴
    feature_id = Column(BIGINT, ForeignKey("daily_features.feature_id"), nullable=False)
    
    # 기초 점수 및 최종 점수
    s_base = Column(Numeric(5, 4), nullable=False)
    score = Column(Numeric(5, 4), nullable=False)
    
    # 위험 등급
    level = Column(
        Enum("normal", "watch", "alert", "emergency", name="risk_level"),
        default="normal"
    )
    
    reason_codes = Column(JSON, nullable=True)
    scored_at = Column(DateTime, nullable=False, default=datetime.now)

    # 🌟 관계 설정 (하나만 남깁니다)
    # DailyFeature 모델 파일에도 'risk_scores'라는 이름의 relationship이 있어야 합니다.
    daily_feature = relationship("DailyFeature", back_populates="risk_scores")