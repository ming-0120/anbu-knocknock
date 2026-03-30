from sqlalchemy import Column, Integer, Float, DateTime
from datetime import datetime
from app.db.base import Base


class ResidentBaseline(Base):

    __tablename__ = "resident_baseline"

    resident_id = Column(Integer, primary_key=True)

    motion_mean = Column(Float)
    motion_std  = Column(Float)

    night_mean  = Column(Float)
    night_std   = Column(Float)

    span_mean   = Column(Float)
    span_std    = Column(Float)

    updated_at  = Column(DateTime, default=datetime.utcnow)