from sqlalchemy import text
from datetime import datetime

from app.services.stt_service import speech_to_text
from app.services.llm_service import summarize_text


async def process_call_summary(db, call_id: int):

    # 1 통화 녹음 조회
    res = await db.execute(
        text("""
        SELECT recording_url
        FROM call_logs
        WHERE call_id=:id
        """),
        {"id": call_id}
    )

    row = res.fetchone()

    if not row:
        raise Exception("call not found")

    recording_url = row[0]

    # 2 STT 실행
    stt_text = speech_to_text(recording_url)

    # 3 LLM 요약
    summary_text = summarize_text(stt_text)

    # 4 DB 저장
    await db.execute(
        text("""
        INSERT INTO call_summaries
        (call_id, stt_text, summary_text, model_name, processed_at)
        VALUES
        (:call_id, :stt, :summary, :model, :time)
        """),
        {
            "call_id": call_id,
            "stt": stt_text,
            "summary": summary_text,
            "model": "gpt-4.1",
            "time": datetime.utcnow()
        }
    )

    await db.commit()

    return {
        "stt_text": stt_text,
        "summary": summary_text
    }


async def get_call_summary(db, call_id: int):

    res = await db.execute(
        text("""
        SELECT summary_text
        FROM call_summaries
        WHERE call_id=:id
        ORDER BY processed_at DESC
        LIMIT 1
        """),
        {"id": call_id}
    )

    row = res.fetchone()

    if not row:
        return None

    return row[0]