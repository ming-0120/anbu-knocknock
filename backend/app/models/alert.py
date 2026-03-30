from sqlalchemy import BigInteger, Column, DateTime, Enum, ForeignKey, String, func

from app.db.database import Base


alert_status_enum = Enum(
    "open",
    "acknowledged",
    "resolved",
    "false_positive",
    name="alert_status_enum",
)


class Alert(Base):
    __tablename__ = "alerts"

    alert_id = Column(BigInteger, primary_key=True, autoincrement=True)
    resident_id = Column(BigInteger, ForeignKey("residents.resident_id"), nullable=False)
    risk_id = Column(BigInteger, ForeignKey("risk_scores.risk_id"), nullable=False)
    operators_id = Column(BigInteger, ForeignKey("operators.operators_id"), nullable=True)

    status = Column(alert_status_enum, nullable=False, default="open", server_default="open")
    summary = Column(String(255), nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    resolved_at = Column(DateTime, nullable=True)