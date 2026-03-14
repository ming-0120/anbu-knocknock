from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_async_db
from app.services.process_call_summary import process_call_summary

router = APIRouter()
@router.post("/call-summary")
async def create_call_summary(
    call_id: int,
    stt_text: str,
    db: AsyncSession = Depends(get_async_db)
):
    result = await process_call_summary(
        db=db,
        call_id=call_id,
        stt_text=stt_text
    )

    return {
        "summary_id": result.summary_id,
        "summary": result.summary_text
    }