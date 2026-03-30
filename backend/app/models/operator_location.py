from sqlalchemy import Column, Integer, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.operator import Operator
from app.db.base import Base

class OperatorLocation(Base):
    __tablename__ = "operator_locations"

    id = Column(Integer, primary_key=True)

    operators_id = Column(
        Integer,
        ForeignKey("operators.operators_id"),
        nullable=False
    )

    latitude = Column(Float)
    longitude = Column(Float)
