from sqlalchemy import and_, case, select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date

from app.models.resident import Resident
from app.models.guardian import Guardian
from app.models.daily_feature import DailyFeature
from app.models.risk_score import RiskScore
from app.models.hourly_feature import HourlyFeature
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

    if age is None:
        return False

    return age >= 65


# ------------------------------------------------
# HIGH RISK 조회
# ------------------------------------------------
async def query_high_risk(
    db: AsyncSession,
    since,
    limit: int,
    min_level: str | None,
):

    levels = _levels_from_min(min_level)

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

            # risk
            RiskScore.score.label("risk_score"),
            RiskScore.level.label("risk_level"),
            RiskScore.reason_codes.label("reason_codes"),
            RiskScore.scored_at,

            # guardian
            Guardian.name.label("guardian_name"),
            Guardian.phone.label("guardian_phone"),
            Guardian.guardian_type,
            Guardian.priority,
        )
        .select_from(RiskScore)

        .join(
            Resident,
            Resident.resident_id == RiskScore.resident_id
        )

        .outerjoin(
            Guardian,
            (Guardian.resident_id == Resident.resident_id) &
            (Guardian.is_primary == True)
        )

        .where(RiskScore.scored_at >= since)

        .where(
            ~Resident.resident_id.in_(
                select(OperatorTask.resident_id)
            )
        )

        .order_by(desc(RiskScore.score))
        .limit(limit)
    )

    if levels:
        stmt = stmt.where(RiskScore.level.in_(levels))

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


# ------------------------------------------------
# 지도 요약
# ------------------------------------------------
async def query_map_summary(
    db: AsyncSession,
    since,
    min_level: str | None,
):

    levels = _levels_from_min(min_level)

    latest = (
        select(
            HourlyFeature.resident_id.label("resident_id"),
            RiskScore.score.label("score"),
            RiskScore.level.label("level"),
            RiskScore.scored_at.label("scored_at"),
            func.row_number()
            .over(
                partition_by=HourlyFeature.resident_id,
                order_by=RiskScore.scored_at.desc(),
            )
            .label("rn"),
        )
        .select_from(RiskScore)
        .join(HourlyFeature, HourlyFeature.feature_id == RiskScore.feature_id)
        .where(RiskScore.scored_at >= since)
        .subquery()
    )

    stmt = (
        select(
            Resident.gu.label("gu"),
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
# 구별 주민 조회
# ------------------------------------------------

async def query_gu_residents(
    db: AsyncSession,
    gu: str,
    limit: int,
    include_latest_score: bool = True,
):

    if not include_latest_score:

        stmt = (
            select(
                Resident.resident_id,
                Resident.name,
                Resident.resident_reg_no,
                Resident.phone,
                Resident.address_main,
                Resident.address_detail,
                Resident.gu,
                Resident.note
            )
            .where(Resident.gu == gu)
            .limit(limit)
        )

        result = await db.execute(stmt)

        rows = result.mappings().all()

        data = []

        for r in rows:

            row = dict(r)

            age = parse_rrn_age(row.get("resident_reg_no"))

            row["age"] = age
            row["is_senior"] = is_senior(age)

            row.pop("rrn", None)

            data.append(row)

        return data


    target_residents = (
        select(Resident.resident_id)
        .where(Resident.gu == gu)
        .order_by(Resident.resident_id)
        .limit(limit)
        .cte("target_residents")
    )


    latest_risk = (
        select(
            RiskScore.resident_id.label("resident_id"),
            RiskScore.score.label("score"),
            RiskScore.level.label("level"),
            RiskScore.scored_at.label("scored_at"),
            func.row_number()
            .over(
                partition_by=RiskScore.resident_id,
                order_by=RiskScore.scored_at.desc()
            )
            .label("rn"),
        )
        .join(
            target_residents,
            RiskScore.resident_id == target_residents.c.resident_id
        )
        .subquery()
    )


    stmt = (
        select(
            Resident.resident_id,
            Resident.name,
            Resident.resident_reg_no,
            Resident.phone,
            Resident.address_main,
            Resident.address_detail,
            Resident.gu,
            Resident.note,
            Resident.lat,
            Resident.lon,
            latest_risk.c.score.label("latest_risk_score"),
            latest_risk.c.level.label("latest_risk_level"),
            latest_risk.c.scored_at.label("latest_scored_at"),
        )
        .join(target_residents, Resident.resident_id == target_residents.c.resident_id)
        .outerjoin(
            latest_risk,
            (latest_risk.c.resident_id == Resident.resident_id) &
            (latest_risk.c.rn == 1)
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

        row.pop("rrn", None)

        data.append(row)

    return data


# ------------------------------------------------
# 요청 / 응답 레벨 매핑
# ------------------------------------------------

REQ_TO_DB_MIN_LEVEL = {
    "NORMAL": "normal",
    "WATCH": "watch",
    "WARNING": "alert",
    "DANGER": "alert",
    "EMERGENCY": "emergency",
}

DB_TO_RESP_LEVEL = {
    "normal": "NORMAL",
    "watch": "WATCH",
    "alert": "WARNING",
    "emergency": "EMERGENCY",
}

DB_LEVEL_ORDER = ["normal", "watch", "alert", "emergency"]