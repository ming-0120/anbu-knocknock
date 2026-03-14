import re
import uuid
import os
from datetime import date
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import asc, desc, select
from app.db.database import get_async_db
from app.deps.redis import get_redis
from app.schemas.dashboard import HighRiskReq, HighRiskResp, MapSummaryReq, MapSummaryResp, GuResidentsReq, GuResidentsResp
from app.services import dashboard_service
from app.models.resident import Resident  # 실제 경로로 수정
from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
import os
from pathlib import Path

from app.db.database import get_async_db
from app.models.resident_setting import ResidentSetting
from app.models.guardian import Guardian
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.post("/high-risk", response_model=HighRiskResp)
async def high_risk(
    body: HighRiskReq,
    db: AsyncSession = Depends(get_async_db),
    redis = Depends(get_redis),
):
    return await dashboard_service.get_high_risk(body, db, redis)

@router.post("/map-summary")
async def map_summary(
    body: MapSummaryReq,
    db: AsyncSession = Depends(get_async_db),
):
    return await dashboard_service.get_map_summary(body, db)

@router.post("/gu-residents")
async def gu_residents(
    body: GuResidentsReq,
    db: AsyncSession = Depends(get_async_db),
):
    return await dashboard_service.get_gu_residents(body, db)
def parse_rrn_7(rrn: str | None):
    """
    'YYMMDD-G' 또는 'YYMMDDG' 형태 지원
    return: (birth_date: date|None, age:int|None, gender:str)
      gender: 'male' | 'female' | 'unknown'
    """
    if not rrn:
        return None, None, "unknown"

    s = rrn.strip()
    m = re.match(r"^(\d{6})-?(\d{1})$", s)
    if not m:
        return None, None, "unknown"

    yymmdd, g = m.group(1), m.group(2)

    # century 추정 (한국 주민번호 관례)
    if g in ("1", "2", "5", "6"):
        century = 1900
    elif g in ("3", "4", "7", "8"):
        century = 2000
    elif g in ("9", "0"):
        century = 1800
    else:
        century = None

    gender = "unknown"
    if g in ("1", "3", "5", "7", "9"):
        gender = "male"
    elif g in ("2", "4", "6", "8", "0"):
        gender = "female"

    if century is None:
        return None, None, gender

    yy = int(yymmdd[0:2])
    mm = int(yymmdd[2:4])
    dd = int(yymmdd[4:6])
    year = century + yy

    try:
        birth = date(year, mm, dd)
    except ValueError:
        return None, None, gender

    today = date.today()

    # 만나이 계산: (올해-출생연도) - (생일 아직 안 지났으면 1)
    age = today.year - birth.year
    if (today.month, today.day) < (birth.month, birth.day):
        age -= 1

    return birth, age, gender


@router.get("/residents/{resident_id}")
async def get_resident_detail(resident_id: int, db: AsyncSession = Depends(get_async_db)):
    # 1) resident
    resident = (
        await db.execute(select(Resident).where(Resident.resident_id == resident_id))
    ).scalar_one_or_none()

    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")

    # 2) settings (0~1개)
    setting = (
        await db.execute(
            select(ResidentSetting).where(ResidentSetting.resident_id == resident_id)
        )
    ).scalar_one_or_none()

    # 3) guardian (대표 1명 선택: is_primary 우선 → priority 낮은 순 → 최신)
    guardian = (
        await db.execute(
            select(Guardian)
            .where(Guardian.resident_id == resident_id)
            .order_by(
                desc(Guardian.is_primary),
                asc(Guardian.priority),
                desc(Guardian.created_at),
            )
            .limit(1)
        )
    ).scalar_one_or_none()

    # 4) 주민번호 파생
    birth, age, gender = parse_rrn_7(getattr(resident, "resident_reg_no", None))

    return {
        # resident 기본
        "resident_id": resident.resident_id,
        "name": resident.name,
        "phone": resident.phone,
        "profile_image_url": resident.profile_image_url,  # 추가
        "address_main": resident.address_main,
        "address_detail": resident.address_detail,
        "diseases":resident.diseases,
        "disease_label":resident.disease_label,
        "medications":resident.medications,
        "living_alone_since":resident.living_alone_since,
        "birth_date": birth.isoformat() if birth else None,
        "age": age,
        "gender": gender,
        "profile_image_url": resident.profile_image_url,
        "note": resident.note,
        # settings
        "settings": None if not setting else {
            "resident_id": setting.resident_id,
            "sensitivity_weight": float(setting.sensitivity_weight) if setting.sensitivity_weight is not None else None,
            "alpha_factor": setting.alpha_factor,
            "sleep_start": str(setting.sleep_start) if setting.sleep_start else None,
            "sleep_end": str(setting.sleep_end) if setting.sleep_end else None,
            "no_activity_threshold_min": setting.no_activity_threshold_min,
            "emergency_sms_enabled": setting.emergency_sms_enabled,
            "days_of_week": setting.days_of_week,
            "updated_at": setting.updated_at.isoformat() if setting.updated_at else None,
        },

        # guardian (대표 1명)
        "guardian": None if not guardian else {
            "guardian_id": guardian.guardian_id,
            "name": guardian.name,
            "phone": guardian.phone,
            "guardian_type": guardian.guardian_type,
            "is_primary": bool(guardian.is_primary),
            "priority": guardian.priority,
        },
    }


UPLOAD_DIR = Path("uploads/profile")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.put("/residents/{resident_id}")
async def update_resident(
    resident_id: int,
    days_of_week: str = Form(None),
    address_main: str = Form(None),
    address_detail: str = Form(None),
    note: str = Form(None),
    sensitivity_weight: float = Form(None),
    sleep_start: str = Form(None),
    sleep_end: str = Form(None),
    profile_image: UploadFile = File(None),
    db: AsyncSession = Depends(get_async_db)
):

    # 1️⃣ resident 조회
    result = await db.execute(
        select(Resident).where(Resident.resident_id == resident_id)
    )
    resident = result.scalar_one_or_none()

    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")

    # 2️⃣ 주소 업데이트
    if address_main is not None:
        resident.address_main = address_main

    if address_detail is not None:
        resident.address_detail = address_detail

    if note is not None:
        resident.note = note

    # 3️⃣ 프로필 이미지 변경    
    if profile_image:
        ext = os.path.splitext(profile_image.filename)[1]
        filename = f"{resident_id}_{uuid.uuid4().hex}{ext}"
        file_path = UPLOAD_DIR / filename

        with open(file_path, "wb") as buffer:
            buffer.write(await profile_image.read())

        resident.profile_image_url = f"/uploads/profile/{filename}"

    # 4️⃣ settings 조회
    result = await db.execute(
        select(ResidentSetting).where(
            ResidentSetting.resident_id == resident_id
        )
    )
    settings = result.scalar_one_or_none()

    if settings:

        if sensitivity_weight is not None:
            settings.sensitivity_weight = sensitivity_weight

        if sleep_start is not None:
            settings.sleep_start = sleep_start

        if sleep_end is not None:
            settings.sleep_end = sleep_end

        if days_of_week:
            settings.days_of_week = json.loads(days_of_week)

    # 4️⃣ 이미지 저장
    await db.commit()

    return {"success": True}