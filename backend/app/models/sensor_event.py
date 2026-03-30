from sqlalchemy import Column, BigInteger, String, Float, DateTime
from sqlalchemy.sql import func
from app.db.database import Base

class SensorEvent(Base):
    __tablename__ = 'sensor_events'

    event_id = Column(BigInteger, primary_key=True, autoincrement=True)
    device_id = Column(BigInteger, nullable=False, index=True)
    event_type = Column(String(20), nullable=False)
    event_value = Column(Float, default=1.0)
    event_at = Column(DateTime(6), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())