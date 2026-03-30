from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.database import get_db
from openai import OpenAI
import os
from dotenv import load_dotenv
from app.services.audio_service import get_random_recording

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

router = APIRouter(prefix="/api/call")

# 🔥 backend 루트 기준 경로 (핵심)
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RECORDINGS_DIR = os.path.join(BACKEND_DIR, "recordings")


# =========================
# Request Models
# =========================

class CallStartReq(BaseModel):
    resident_id: int
    operator_id: int


class CallEndReq(BaseModel):
    call_id: int
    duration_sec: int
    outcome: str


class CallSummaryReq(BaseModel):
    call_id: int


# =========================
# Call Start
# =========================

@router.post("/start")
async def start_call(body: CallStartReq, db: Session = Depends(get_db)):
    recording_path = get_random_recording()

    q = text("""
        INSERT INTO call_logs
        (
            resident_id,
            operators_id,
            duration_sec,
            outcome,
            recording_url,
            created_at
        )
        VALUES
        (
            :rid,
            :oid,
            0,
            'connected',
            NULL,
            NOW()
        )
    """)

    res = db.execute(q, {
        "rid": body.resident_id,
        "oid": body.operator_id
    })

    call_id = res.lastrowid
    db.commit()

    return {
        "call_id": call_id,
        "recording_url": recording_path
    }


# =========================
# Latest Call
# =========================

@router.get("/latest/{resident_id}")
async def get_latest_call(resident_id: int, db: Session = Depends(get_db)):

    q = text("""
        SELECT call_id
        FROM call_logs
        WHERE resident_id = :rid
        ORDER BY created_at DESC
        LIMIT 1
    """)

    res = db.execute(q, {"rid": resident_id})
    row = res.fetchone()

    if not row:
        return {"call_id": None}

    return {"call_id": row[0]}


# =========================
# Call Summary 조회
# =========================

@router.get("/summary/{call_id}")
async def get_summary(call_id: int, db: Session = Depends(get_db)):

    q = text("""
        SELECT summary_text
        FROM call_summaries
        WHERE call_id = :cid
        LIMIT 1
    """)

    res = db.execute(q, {"cid": call_id})
    row = res.fetchone()

    if not row:
        return {"summary": None}

    return {"summary": row[0]}


# =========================
# Call End
# =========================

@router.post("/end")
async def end_call(body: CallEndReq, db: Session = Depends(get_db)):

    recording_path = get_random_recording()

    q = text("""
        UPDATE call_logs
        SET
            duration_sec = :duration,
            outcome = :outcome,
            recording_url = :recording
        WHERE call_id = :cid
    """)

    db.execute(q, {
        "duration": body.duration_sec,
        "outcome": body.outcome,
        "recording": recording_path,
        "cid": body.call_id
    })

    db.commit()

    return {
        "status": "ended",
        "recording_url": recording_path
    }


# =========================
# Summary 생성 (녹음 → STT → 요약)
# =========================

@router.post("/summary")
async def generate_summary(body: CallSummaryReq, db: Session = Depends(get_db)):

    # 1. 이미 요약 존재 여부 확인
    q = text("""
        SELECT summary_text
        FROM call_summaries
        WHERE call_id = :cid
        LIMIT 1
    """)

    res = db.execute(q, {"cid": body.call_id})
    row = res.fetchone()

    if row:
        return {"summary": row[0]}

    # 2. 녹음 경로 조회
    q = text("""
        SELECT recording_url
        FROM call_logs
        WHERE call_id = :cid
    """)

    res = db.execute(q, {"cid": body.call_id})
    row = res.fetchone()

    if not row:
        return {"error": "call not found"}

    db_path = row[0]

    # 🔥 경로 변환 (핵심)
    filename = os.path.basename(db_path)
    recording_path = os.path.join(RECORDINGS_DIR, filename)
    recording_path = os.path.abspath(recording_path)

    # 🔥 디버깅 로그 (필수)
    print("DB path:", db_path)
    print("Resolved path:", recording_path)
    print("Exists:", os.path.exists(recording_path))

    if not recording_path or not os.path.exists(recording_path):
        return {"error": "recording file not found"}

    # 3. STT
    with open(recording_path, "rb") as f:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=f
        )

    stt_text = transcript.text

    # 4. 요약
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """
                            너는 상담 요약 전문가다.

                            다음 통화 내용을 읽고:
                            - 핵심 증상
                            - 상태 변화
                            - 특이사항

                            만 간단히 2~3줄로 요약해라.
                            불필요한 대화 내용은 제거하라.
                            """
            },
            {
                "role": "user",
                "content": stt_text
            }
        ]
    )

    summary = resp.choices[0].message.content

    # 5. 저장
    q = text("""
        INSERT INTO call_summaries
        (
            call_id,
            stt_text,
            summary_text,
            model_name,
            processed_at
        )
        VALUES
        (
            :cid,
            :stt,
            :summary,
            :model,
            NOW()
        )
    """)

    db.execute(q, {
        "cid": body.call_id,
        "stt": stt_text,
        "summary": summary,
        "model": "gpt-4o-mini"
    })

    db.commit()

    return {"summary": summary}