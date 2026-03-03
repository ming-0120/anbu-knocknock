from sqlalchemy import Column, BigInteger, Integer, Float, Numeric, Time, Boolean, JSON, DateTime, text
from sqlalchemy.sql import func
from app.db.database import Base

class ResidentSetting(Base):
    __tablename__ = 'resident_settings'

    resident_id = Column(BigInteger, primary_key=True, nullable=False)
    sensitivity_weight = Column(Numeric(3, 2), server_default=text("'1.00'"))
    alpha_factor = Column(Float, server_default=text("'1'"))
    sleep_start = Column(Time, server_default=text("'22:00:00'"))
    sleep_end = Column(Time, server_default=text("'07:00:00'"))
    no_activity_threshold_min = Column(Integer, server_default=text("'720'"))
    emergency_sms_enabled = Column(Boolean, server_default=text("'1'"))
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    days_of_week = Column(JSON)