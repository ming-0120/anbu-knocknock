from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.call_summary import CallSummary

async def save_call_summary(
    db: AsyncSession,
    call_id: int,
    stt_text: str,
    summary_text: str,
    model_name: str
):

    item = CallSummary(
        call_id=call_id,
        stt_text=stt_text,
        summary_text=summary_text,
        model_name=model_name,
        processed_at=datetime.utcnow()
    )

    db.add(item)

    await db.commit()

    return item