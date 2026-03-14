from sqlalchemy import select
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.websocket.manager import manager
from app.db.database import get_async_db
from app.models.resident import Resident
from app.schemas.operator_task import AlertActionCreate, AlertCloseRequest
from app.repositories.operator_task_repo import (
    create_alert_action,
    mark_alert_acknowledged_if_open,
    mark_operator_task_in_progress,
    close_alert_and_task,
)

router = APIRouter(prefix="/api/alert-actions", tags=["alert-actions"])

class AlertActionReq(BaseModel):
    alert_id: int
    operator_id: int
    action_type: str
    result: str | None = None
    memo: str | None = None


# @router.post("")
# async def create_action(
#     body: AlertActionReq,
#     db: AsyncSession = Depends(get_async_db)
# ):

#     action = await create_alert_action(
#         db,
#         alert_id=body.alert_id,
#         operators_id=body.operator_id,
#         action_type=body.action_type,
#         result=body.result,
#         memo=body.memo,
#     )

#     await db.commit()

#     return {
#         "success": True,
#         "action_id": action.action_id
#     }

@router.post("")
async def save_alert_action(
    body: AlertActionCreate,
    db: AsyncSession = Depends(get_async_db),
):

    alert = await mark_alert_acknowledged_if_open(
        db,
        alert_id=body.alert_id,
        operators_id=body.operator_id,
    )

    if not alert:
        raise HTTPException(status_code=404, detail="alert not found")

    action = await create_alert_action(
        db,
        alert_id=body.alert_id,
        operators_id=body.operator_id,
        action_type=body.action_type,
        result=body.result,
        memo=body.memo,
    )

    await mark_operator_task_in_progress(
        db,
        resident_id=alert.resident_id,
        operators_id=body.operator_id,
    )

    await db.commit()

    return {
        "success": True,
        "action_id": action.action_id,
        "alert_id": body.alert_id,
        "alert_status": alert.status,
    }


@router.post("/{alert_id}/close")
async def close_alert(
    alert_id: int,
    body: AlertCloseRequest,
    db: AsyncSession = Depends(get_async_db),
):

    alert, task, action = await close_alert_and_task(
        db,
        alert_id=alert_id,
        operator_id=body.operator_id,
        result_value=body.result,
        memo=body.memo,
    )

    if not alert:
        raise HTTPException(status_code=404, detail="alert not found")

    # resident 조회
    stmt = select(Resident).where(Resident.resident_id == alert.resident_id)
    result = await db.execute(stmt)
    resident = result.scalar_one_or_none()

    await db.commit()

    await manager.send_to_dashboard({
        "type": "task_complete",
        "alert_id": alert.alert_id,
        "resident_id": alert.resident_id,
        "resident_name": resident.name if resident else None,
        "resident_gu": resident.gu if resident else None,
    })

    return {
        "success": True,
        "alert_id": alert.alert_id,
        "alert_status": alert.status,
        "resolved_at": alert.resolved_at,
        "task_id": task.task_id if task else None,
        "task_status": task.status if task else None,
        "action_id": action.action_id if action else None,
    }