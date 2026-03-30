from datetime import datetime
from typing import Literal, Optional, Any

from pydantic import BaseModel


ActionType = Literal["call_resident", "call_guardian", "dispatch", "note", "close", "assign"]
ActionResult = Literal["no_answer", "ok", "needs_help", "emergency", "wrong_alarm"]


class AlertActionCreate(BaseModel):
    alert_id: int
    operator_id: int
    action_type: ActionType
    result: Optional[ActionResult] = None
    memo: Optional[str] = None


class AlertActionResponse(BaseModel):
    action_id: int
    alert_id: int
    operator_id: int
    action_type: str
    result: Optional[str] = None
    notes: Optional[Any] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AlertCloseRequest(BaseModel):
    operator_id: int
    result: Literal["ok", "wrong_alarm", "needs_help", "emergency"]
    memo: Optional[str] = None
    task_type: str | None = None
    description: str | None = None