from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.call_service import process_call_summary, get_call_summary

router = APIRouter(prefix="/api/call")


@router.post("/process/{call_id}")
async def process_call(call_id: int, db: AsyncSession = Depends(get_db)):

    result = await process_call_summary(db, call_id)

    return result


@router.get("/summary/{call_id}")
async def summary(call_id: int, db: AsyncSession = Depends(get_db)):

    summary_text = await get_call_summary(db, call_id)

    return {
        "summary": summary_text
    }