from sqlalchemy import Column, BigInteger, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.db.database import Base


class OperatorTask(Base):
    __tablename__ = "operator_tasks"

    task_id = Column(BigInteger, primary_key=True, index=True)
    alert_id = Column(BigInteger, nullable=True)   # ← 추가
    resident_id = Column(BigInteger, nullable=False)
    operator_id = Column(BigInteger, nullable=False)

    task_type = Column(String(50))
    description = Column(Text)

    status = Column(String(20), default="assigned")

    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)