import random
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.models.call_log import CallLog
from app.models.call_summary import CallSummary


router = APIRouter(
    prefix="/api/calls",
    tags=["calls"]
)


# 샘플 녹음 목록
CALL_SAMPLES = [
    "/calls/sample_call_1.mp3",
    "/calls/sample_call_2.mp3",
    "/calls/sample_call_3.mp3",
]


# -------------------------------------------------------
# 1. 통화 시작
# -------------------------------------------------------

@router.post("/start")
async def start_call():
    """
    가짜 통화 시작
    녹음 파일 URL 반환
    """

    recording_url = random.choice(CALL_SAMPLES)

    return {
        "recording_url": recording_url
    }


# -------------------------------------------------------
# 2. 통화 종료 → call_logs 저장
# -------------------------------------------------------

@router.post("/end")
async def end_call(
    resident_id: int,
    operator_id: int,
    duration_sec: int,
    recording_url: str,
    db: AsyncSession = Depends(get_db)
):
    """
    통화 종료 후 call_logs 저장
    """

    call = CallLog(
        resident_id=resident_id,
        operator_id=operator_id,
        duration_sec=duration_sec,
        outcome="connected",
        recording_url=recording_url,
        created_at=datetime.now(UTC)
    )

    db.add(call)
    await db.flush()

    return {
        "call_id": call.call_id
    }


# -------------------------------------------------------
# 3. 상담 요약 생성 + call_summaries 저장
# -------------------------------------------------------

@router.post("/summarize")
async def summarize_call(
    call_id: int,
    text: str,
    db: AsyncSession = Depends(get_db)
):
    """
    상담 텍스트 요약
    """

    # 간단한 요약 로직 (LLM 연결 전 임시)
    summary = text[:120]

    row = CallSummary(
        call_id=call_id,
        stt_text=text,
        summary_text=summary,
        model_name="mock",
        processed_at=datetime.utcnow()
    )

    db.add(row)

    return {
        "summary": summary
    }


# -------------------------------------------------------
# 4. 특정 resident 통화 기록 조회
# -------------------------------------------------------

@router.get("/resident/{resident_id}")
async def get_resident_calls(
    resident_id: int,
    db: AsyncSession = Depends(get_db)
):

    stmt = (
        select(
            CallLog.call_id,
            CallLog.duration_sec,
            CallLog.outcome,
            CallLog.created_at,
            CallSummary.summary_text
        )
        .join(
            CallSummary,
            CallSummary.call_id == CallLog.call_id,
            isouter=True
        )
        .where(CallLog.resident_id == resident_id)
        .order_by(CallLog.created_at.desc())
    )

    result = await db.execute(stmt)

    rows = result.all()

    calls = []

    for row in rows:
        calls.append({
            "call_id": row.call_id,
            "duration_sec": row.duration_sec,
            "outcome": row.outcome,
            "created_at": row.created_at,
            "summary": row.summary_text
        })

    return calls