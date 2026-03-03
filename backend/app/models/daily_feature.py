from sqlalchemy import Column, BigInteger, Integer, Float, Date, DateTime
from sqlalchemy.sql import func
from app.db.database import Base
from sqlalchemy.orm import relationship

class DailyFeature(Base):
    __tablename__ = 'daily_features'

    feature_id = Column(BigInteger, primary_key=True, autoincrement=True)
    risk_scores = relationship("RiskScore", back_populates="daily_feature")
    resident_id = Column(BigInteger, nullable=False, index=True)
    target_date = Column(Date, nullable=False, index=True)
    x1_motion_count = Column(Integer, default=0)
    x2_door_count = Column(Integer, default=0)
    x3_avg_interval = Column(Float, default=0.0)
    x4_night_motion_count = Column(Integer, default=0)
    x5_first_motion_min = Column(Integer)
    x6_last_motion_min = Column(Integer)
    computed_at = Column(DateTime, server_default=func.current_timestamp())