from sqlalchemy import Column, BigInteger, String, DateTime, JSON
from sqlalchemy.sql import func
from app.db.database import Base


class AlertAction(Base):
    __tablename__ = "alert_actions"

    action_id = Column(BigInteger, primary_key=True, index=True)

    alert_id = Column(BigInteger, nullable=False)
    operators_id = Column(BigInteger, nullable=False)

    action_type = Column(String(50))
    result = Column(String(50))

    notes = Column(JSON)

    created_at = Column(DateTime, server_default=func.now())