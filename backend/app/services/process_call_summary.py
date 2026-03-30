from sqlalchemy.ext.asyncio import AsyncSession

from app.services.call_summary_service import summarize_call_text
from app.services.call_summary_repository import save_call_summary


async def process_call_summary(
    db: AsyncSession,
    call_id: int,
    stt_text: str
):

    summary = await summarize_call_text(stt_text)

    result = await save_call_summary(
        db=db,
        call_id=call_id,
        stt_text=stt_text,
        summary_text=summary,
        model_name="gpt-4o-mini"
    )

    return result