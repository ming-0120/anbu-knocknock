from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.auth.jwt_handler import get_current_operator
from fastapi import HTTPException
from app.models.alert import Alert
from app.db.database import get_async_db
from app.schemas.operator_task import OperatorTaskCreate
from app.repositories.operator_task_repo import (
    create_operator_task,
    get_operator_tasks,
)
from app.websocket.manager import manager

router = APIRouter(prefix="/api/operator-tasks", tags=["operator-tasks"])


@router.post("")
async def create_task(
    body: OperatorTaskCreate,
    db: AsyncSession = Depends(get_async_db)
):
    task = await create_operator_task(
        db,
        alert_id=body.alert_id,
        resident_id=body.resident_id,
        operator_id=body.operator_id,
    )
    await db.commit()
    await manager.send_to_worker(
        body.operator_id,
        {
            "type": "NEW_TASK",
            "task_id": task.task_id,
            "resident_id": body.resident_id,
            "message": "새 업무가 배정되었습니다"
        }
    )
    return {"success": True}

@router.get("")
async def get_tasks(
    current_operator = Depends(get_current_operator),
    db: AsyncSession = Depends(get_async_db),
):

    operator_id = current_operator["operator_id"]

    rows = await get_operator_tasks(
        db,
        operator_id=operator_id,
    )

    return rows