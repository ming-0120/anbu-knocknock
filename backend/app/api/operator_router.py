from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import bcrypt
from app.db.database import get_async_db, get_db
from app.services.operator_service import find_nearby_operators
from sqlalchemy import text
from app.deps.redis import get_redis
from app.auth.jwt_handler import create_access_token, get_current_operator
from app.auth.password import verify_password
from app.repositories.operator_repo import get_operator_by_email
from app.schemas.operator_schema import OperatorLogin
from datetime import datetime
from sqlalchemy import update
from app.models.operator import Operator
from app.websocket.manager import manager

router = APIRouter(prefix="/api/operators", tags=["operators"])


@router.get("/nearby")
async def get_nearby_operators_api(
    lat: float,
    lon: float,
    radius: float = 3,
    db: AsyncSession = Depends(get_async_db)
):

    operators = await find_nearby_operators(db, lat, lon, radius)

    return {
        "count": len(operators),
        "operators": operators
    }

@router.post("/login")
async def operator_login(
    body: OperatorLogin,
    db: AsyncSession = Depends(get_async_db)
):

    operator = await get_operator_by_email(db, body.email)

    if not operator:
        raise HTTPException(
            status_code=401,
            detail="invalid credentials"
        )

    if not verify_password(body.password, operator.password_hash):
        raise HTTPException(
            status_code=401,
            detail="invalid credentials"
        )

    token = create_access_token(
        {
            "operator_id": operator.operators_id,
            "role": operator.role
        }
    )    
    return {    
        "access_token": token,
        "name": operator.name,
        "role": operator.role
    }
@router.post("/heartbeat")
async def operator_heartbeat(
    current_user: dict = Depends(get_current_operator),
    db: AsyncSession = Depends(get_async_db)
):

    operator_id = current_user["operator_id"]

    redis = get_redis()

    key = f"operator:{operator_id}:online"

    # Redis online 상태 유지
    await redis.set(key, "1", ex=120)

    # DB last_seen 업데이트
    stmt = (
        update(Operator)
        .where(Operator.operators_id == operator_id)
        .values(last_seen=datetime.now())
    )

    await db.execute(stmt)
    await db.commit()
    await manager.send_to_dashboard({
        "type": "operator_update",
        "operator_id": operator_id,   
        "last_seen": datetime.now().isoformat()     
    })
    return {"status": "ok"}