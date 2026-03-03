from datetime import datetime
from pydantic import BaseModel, Field

class SensorEventIn(BaseModel):
    sensor_id: int = Field(ge=1)
    event_type: str = Field(min_length=1, max_length=64)
    event_value: int
    event_at: datetime