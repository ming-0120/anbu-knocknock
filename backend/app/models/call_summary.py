from sqlalchemy import Column, BigInteger, Text, String, TIMESTAMP, func
from app.db.base import Base


class CallSummary(Base):
    __tablename__ = "call_summaries"

    summary_id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    call_id = Column(
        BigInteger,
        nullable=False,
        index=True
    )

    stt_text = Column(
        Text,
        nullable=True
    )

    summary_text = Column(
        Text,
        nullable=True
    )

    model_name = Column(
        String(50),
        nullable=True
    )

    processed_at = Column(
        TIMESTAMP,
        server_default=func.now()
    )