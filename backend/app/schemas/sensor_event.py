from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional

class SensorEventIn(BaseModel):
    sensor_id: int = Field(ge=1)
    event_type: str = Field(min_length=1, max_length=64)
    event_value: int
    event_at: datetime

class HighRiskReq(BaseModel):
    window_minutes: int = 60
    limit: int = 10
    min_level: Optional[str] = None


class HighRiskResp(BaseModel):
    window_minutes: int
    generated_at: str
    items: list