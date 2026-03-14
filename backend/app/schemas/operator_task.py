from datetime import datetime

from pydantic import BaseModel
from typing import Any, Literal, Optional


class OperatorTaskCreate(BaseModel):
    resident_id: int
    operator_id: int
    alert_id: Optional[int] = None
    task_type: Optional[str] = None
    description: Optional[str] = None


class OperatorTaskResponse(BaseModel):

    task_id: int
    resident_id: int
    operator_id: int
    status: str

    class Config:
        from_attributes = True

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