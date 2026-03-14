from sqlalchemy import Column, BigInteger, Enum, Integer, DateTime, String

from app.db.database import Base

class CallLog(Base):

    __tablename__ = "call_logs"

    call_id = Column(BigInteger, primary_key=True, index=True)

    resident_id = Column(BigInteger)
    operator_id = Column(BigInteger)

    duration_sec = Column(Integer)

    outcome = Column(Enum("connected","missed","busy","failed"))

    recording_url = Column(String(255))

    created_at = Column(DateTime)