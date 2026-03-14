from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Literal
from datetime import datetime

RiskLevel = Literal["normal", "watch", "alert", "emergency"]

class HighRiskReq(BaseModel):
    window_minutes: int = Field(60, ge=1, le=1440)
    limit: int = Field(20, ge=1, le=200)
    min_level: Optional[RiskLevel] = None

class HighRiskItem(BaseModel):
    resident_id: int
    name: str
    gu: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    phone: Optional[str] = None
    guardian_phone: Optional[str] = None
    address_main: Optional[str] = None
    address_detail: Optional[str] = None
    note: Optional[str] = None
    risk_score: float
    risk_level: RiskLevel
    reason_codes: Dict[str, Any] | None

    scored_at: datetime

class HighRiskResp(BaseModel):
    window_minutes: int
    generated_at: datetime
    items: List[HighRiskItem]

class MapSummaryReq(BaseModel):
    window_minutes: int = Field(60, ge=1, le=1440)
    min_level: Optional[RiskLevel] = None

class MapSummaryItem(BaseModel):
    gu: str
    high_risk_count: int
    max_risk_score: float

class MapSummaryResp(BaseModel):
    window_minutes: int
    generated_at: datetime
    items: List[MapSummaryItem]

class GuResidentsReq(BaseModel):
    gu: str = Field(..., min_length=2, max_length=30)
    limit: int = Field(200, ge=1, le=1000)
    include_latest_score: bool = True

class GuResidentItem(BaseModel):
    resident_id: int
    name: str
    address_main: Optional[str] = None
    latest_risk_score: Optional[float] = None
    latest_risk_level: Optional[RiskLevel] = None
    latest_scored_at: Optional[datetime] = None

class GuResidentsResp(BaseModel):
    gu: str
    generated_at: datetime
    items: List[GuResidentItem]