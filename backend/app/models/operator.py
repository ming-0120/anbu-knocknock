from sqlalchemy import Column, BigInteger, String, DateTime, Enum
from sqlalchemy.sql import func
from app.db.database import Base


class Operator(Base):
    __tablename__ = "operators"

    operators_id = Column(BigInteger, primary_key=True, index=True)

    name = Column(String(50), nullable=False)

    role = Column(
        Enum("admin", "case_manager", "viewer", name="operator_role"),
        nullable=False
    )
    
    phone = Column(String(20))
    email = Column(String(254))
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    last_seen =  Column(DateTime, server_default=func.now())