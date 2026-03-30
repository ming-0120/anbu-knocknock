from sqlalchemy import and_, case, select, func, desc, exists
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date

from app.models.resident import Resident
from app.models.guardian import Guardian
from app.models.risk_score import RiskScore
from app.models.operator_task import OperatorTask


_LEVEL_ORDER = {"normal": 0, "watch": 1, "alert": 2, "emergency": 3}


def _levels_from_min(min_level: str | None):
    if not min_level:
        return None

    m = min_level.lower()
    if m not in _LEVEL_ORDER:
        return None

    min_rank = _LEVEL_ORDER[m]
    return [k for k, v in _LEVEL_ORDER.items() if v >= min_rank]


# ------------------------------------------------
# 주민번호 → 나이 계산
# ------------------------------------------------
def parse_rrn_age(rrn: str) -> int | None:
    if not rrn or "-" not in rrn:
        return None

    try:
        front, back = rrn.split("-")

        yy = int(front[0:2])
        mm = int(front[2:4])
        dd = int(front[4:6])

        gender_code = int(back[0])

        if gender_code in (1, 2):
            year = 1900 + yy
        elif gender_code in (3, 4):
            year = 2000 + yy
        else:
            return None

        birth = date(year, mm, dd)
        today = date.today()

        age = today.year - birth.year
        if (today.month, today.day) < (birth.month, birth.day):
            age -= 1

        return age

    except Exception:
        return None


def is_senior(age: int | None) -> bool:
    return age is not None and age >= 65
# ------------------------------------------------
# HIGH RISK (좌측)
# ------------------------------------------------
async def query_high_risk(db: AsyncSession, since, limit: int, min_level: str | None):

    levels = _levels_from_min(min_level)

    # 최신 risk score (resident별 1개)
    latest = (
        select(
            RiskScore.resident_id,
            RiskScore.score,
            RiskScore.level,
            RiskScore.reason_codes,
            RiskScore.scored_at,
            func.row_number().over(
                partition_by=RiskScore.resident_id,
                order_by=RiskScore.scored_at.desc()
            ).label("rn"),
        )
        .subquery()
    )

    stmt = (
        select(
            Resident.resident_id,
            Resident.name,
            Resident.resident_reg_no,
            Resident.gu,
            Resident.phone,
            Resident.address_main,
            Resident.address_detail,
            Resident.lat,
            Resident.lon,
            Resident.note,
            Resident.profile_image_url,

            latest.c.score.label("risk_score"),
            latest.c.level.label("risk_level"),
            latest.c.reason_codes,
            latest.c.scored_at,

            Guardian.name.label("guardian_name"),
            Guardian.phone.label("guardian_phone"),
        )
        .join(Resident, Resident.resident_id == latest.c.resident_id)
        .outerjoin(
            Guardian,
            (Guardian.resident_id == Resident.resident_id) &
            (Guardian.is_primary == True)
        )
        .where(latest.c.rn == 1)        
        .where(latest.c.scored_at >= since)
        .where(
            ~exists().where(
                (OperatorTask.resident_id == Resident.resident_id)
                & (OperatorTask.status.in_(["pending", "in_progress"]))
            )
        )
        .order_by(desc(latest.c.score))
        .limit(limit)
    )

    if levels:
        stmt = stmt.where(latest.c.level.in_(levels))

    result = await db.execute(stmt)
    rows = result.mappings().all()

    data = []
    for r in rows:
        row = dict(r)
        rrn = row.get("resident_reg_no")

        # 1. 나이 계산
        age = parse_rrn_age(rrn)
        row["age"] = age
        
        # 2. 성별 추출 (추가된 부분)
        row["gender"] = parse_rrn_gender(rrn)
        
        # 3. 어르신 여부
        row["is_senior"] = is_senior(age)

        # 보안상 주민번호 제거
        row.pop("resident_reg_no", None)

        data.append(row)

    return data

# 성별 파싱 유틸리티 (필요 시 정의)
def parse_rrn_gender(rrn: str | None) -> str:
    if not rrn or "-" not in rrn:
        return "unknown"
    
    try:
        # 주민번호 뒷자리 첫 번째 숫자 확인
        gender_digit = rrn.split("-")[1][0]
        if gender_digit in ("1", "3", "5", "7"):
            return "(남)"
        elif gender_digit in ("2", "4", "6", "8"):
            return "(여)"
    except (IndexError, ValueError):
        pass
        
    return "unknown"


# ------------------------------------------------
# 지도 요약
# ------------------------------------------------
async def query_map_summary(db: AsyncSession, since, min_level: str | None):

    levels = _levels_from_min(min_level)

    latest = (
        select(
            RiskScore.resident_id,
            RiskScore.score,
            RiskScore.level,
            func.row_number().over(
                partition_by=RiskScore.resident_id,
                order_by=RiskScore.scored_at.desc()
            ).label("rn"),
        )
        .subquery()
    )

    stmt = (
        select(
            Resident.gu,
            func.count().label("high_risk_count"),
            func.max(latest.c.score).label("max_risk_score"),
        )
        .join(Resident, Resident.resident_id == latest.c.resident_id)
        .where(latest.c.rn == 1)
        .group_by(Resident.gu)
        .order_by(desc(func.count()))
    )

    if levels:
        stmt = stmt.where(latest.c.level.in_(levels))

    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


# ------------------------------------------------
# 구별 주민 조회 (우측)
# ------------------------------------------------
async def query_gu_residents(
    db: AsyncSession,
    gu: str,
    since,
    limit: int,
    min_level: str | None = None,
):

    levels = _levels_from_min(min_level)

    target_residents = (
        select(Resident.resident_id)
        .where(Resident.gu == gu)
        .cte("target_residents")
    )

    latest = (
        select(
            RiskScore.resident_id,
            RiskScore.score,
            RiskScore.level,
            RiskScore.scored_at,
            func.row_number().over(
                partition_by=RiskScore.resident_id,
                order_by=RiskScore.scored_at.desc()
            ).label("rn"),
        )
        .join(
            target_residents,
            RiskScore.resident_id == target_residents.c.resident_id
        )
        .subquery()
    )

    # 🔥 위험군 여부
    if levels:
        is_high_risk = latest.c.level.in_(levels)
    else:
        is_high_risk = False

    # 🔥 has_task (위험군 기준 포함)
    has_task_expr = case(
        (
            and_(
                is_high_risk,
                exists().where(OperatorTask.resident_id == Resident.resident_id)
            ),
            True
        ),
        (
            is_high_risk,
            False
        ),
        else_=None
    ).label("has_task")

    stmt = (
        select(
            Resident.resident_id,
            Resident.name,
            Resident.resident_reg_no,
            Resident.gu,
            Resident.phone,
            Resident.address_main,
            Resident.address_detail,
            Resident.lat,
            Resident.lon,

            latest.c.score.label("latest_risk_score"),
            latest.c.level.label("latest_risk_level"),
            latest.c.scored_at.label("latest_scored_at"),

            has_task_expr,
        )
        .join(target_residents, Resident.resident_id == target_residents.c.resident_id)

        .outerjoin(
            latest,
            (latest.c.resident_id == Resident.resident_id) &
            (latest.c.rn == 1)
        )
    )

    result = await db.execute(stmt)
    rows = result.mappings().all()

    data = []
    for r in rows:
        row = dict(r)

        age = parse_rrn_age(row.get("resident_reg_no"))
        row["age"] = age
        row["is_senior"] = is_senior(age)

        row.pop("resident_reg_no", None)

        data.append(row)

    return data