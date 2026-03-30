from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, desc, func, insert, select

from app.models.operator_task import OperatorTask
from app.models.resident import Resident
from app.models.alert import Alert
from app.models.alert_action import AlertAction
from app.models.risk_score import RiskScore
from app.models.daily_feature import DailyFeature
from app.models.hourly_feature import HourlyFeature
from app.models.resident_setting import ResidentSetting # 모델명 확인 필요
async def create_operator_task(
    db: AsyncSession,
    alert_id:int,
    resident_id: int,
    operator_id: int,
):

    task = OperatorTask(
        alert_id=alert_id,
        resident_id=resident_id,
        operator_id=operator_id,
        status="assigned",
        

    )

    db.add(task)
    await db.flush()

    return task

# -------------------------------
# 나이 계산
# -------------------------------
def calc_age(reg_no: str | None):
    if not reg_no:
        return None

    # 🔥 핵심: 전처리
    reg_no = str(reg_no).strip().replace("-", "")

    if len(reg_no) < 7:
        return None

    try:
        yy = int(reg_no[:2])
        mm = int(reg_no[2:4])
        dd = int(reg_no[4:6])
        gender_code = int(reg_no[6])
    except Exception as e:
        print("❌ 파싱 실패:", reg_no, e)
        return None

    if gender_code in (1, 2):
        year = 1900 + yy
    elif gender_code in (3, 4):
        year = 2000 + yy
    else:
        return None

    today = date.today()
    return today.year - year - ((today.month, today.day) < (mm, dd))

async def get_operator_tasks(db: AsyncSession, operator_id: int):

    from sqlalchemy import select, func
    import json

    # --------------------------------
    # resident별 최신 risk_score
    # --------------------------------
    latest_risk = (
        select(
            HourlyFeature.resident_id,
            RiskScore.score,
            RiskScore.reason_codes,
            func.row_number().over(
                partition_by=HourlyFeature.resident_id,
                order_by=RiskScore.feature_id.desc()
            ).label("rn")
        )
        .join(RiskScore, RiskScore.feature_id == HourlyFeature.feature_id)
        .subquery()
    )

    latest_risk_filtered = (
        select(
            latest_risk.c.resident_id,
            latest_risk.c.score,
            latest_risk.c.reason_codes
        )
        .where(latest_risk.c.rn == 1)
        .subquery()
    )

    # --------------------------------
    # 마지막 활동 시간
    # --------------------------------
    last_activity = (
        select(
            HourlyFeature.resident_id,
            func.max(HourlyFeature.target_hour).label("last_activity")
        )
        .where(HourlyFeature.x1_motion_count > 0)
        .group_by(HourlyFeature.resident_id)
        .subquery()
    )

    # --------------------------------
    # 메인 쿼리
    # --------------------------------
    stmt = (
        select(
            OperatorTask.task_id,
            OperatorTask.operator_id,
            OperatorTask.alert_id,

            Resident.resident_id,
            Resident.name,
            Resident.gu,
            Resident.address_main,
            Resident.phone,
            Resident.lat,
            Resident.lon,
            Resident.profile_image_url,
            Resident.resident_reg_no,

            latest_risk_filtered.c.score.label("risk_score"),
            latest_risk_filtered.c.reason_codes,

            last_activity.c.last_activity
        )
        .join(Resident, Resident.resident_id == OperatorTask.resident_id)

        # 최신 위험도
        .outerjoin(
            latest_risk_filtered,
            latest_risk_filtered.c.resident_id == Resident.resident_id
        )

        # 마지막 활동
        .outerjoin(
            last_activity,
            last_activity.c.resident_id == Resident.resident_id
        )

        .where(
            OperatorTask.operator_id == operator_id,
            OperatorTask.completed_at.is_(None)
        )
    )

    result = await db.execute(stmt)
    rows = result.all()

    # --------------------------------
    # 결과 변환 (🔥 핵심: reason_codes 포함)
    # --------------------------------
    data = []
    for r in rows:
        rc = r.reason_codes

        # JSON 문자열이면 파싱
        if isinstance(rc, str):
            try:
                rc = json.loads(rc)
            except:
                pass

        data.append({
            "task_id": r.task_id,
            "operator_id": r.operator_id,
            "alert_id": r.alert_id,

            "resident_id": r.resident_id,
            "name": r.name,
            "gu": r.gu,
            "address_main": r.address_main,
            "phone": r.phone,
            "lat": r.lat,
            "lon": r.lon,
            "profile_image_url": r.profile_image_url,
            "resident_reg_no": r.resident_reg_no,

            "risk_score": r.risk_score,
            "reason_codes": rc,  # 🔥 여기 추가

            "last_activity": r.last_activity,
        })

    return data

    # --------------------------------
    # 반환 직전 가공
    # --------------------------------
    result_list = []

    for row in rows:
        d = dict(row._mapping)

        reg_no = d.get("resident_reg_no")

        # 나이
        d["age"] = calc_age(reg_no)

        clean = str(reg_no).strip().replace("-", "")
        if len(clean) >= 7:
            try:
                gender_code = int(clean[6])
                d["gender"] = "남성" if gender_code in (1, 3) else "여성"
            except:
                d["gender"] = None

        result_list.append(d)

    return result_list

def _make_notes(memo: str | None):
    if not memo:
        return None
    return {"memo": memo}


async def create_alert_action(
    db: AsyncSession,
    *,
    alert_id: int,
    operators_id: int,
    action_type: str,
    result: str | None,
    memo: str | None,
):
    action = AlertAction(
        alert_id=alert_id,
        operators_id=operators_id,
        action_type=action_type,
        result=result,
        notes=_make_notes(memo),
    )
    db.add(action)
    await db.flush()

    return action


async def mark_alert_acknowledged_if_open(
    db: AsyncSession,
    *,
    alert_id: int,
    operator_id: int,
):
    result = await db.execute(
        select(Alert).where(Alert.alert_id == alert_id)
    )
    alert = result.scalar_one_or_none()

    if not alert:
        return None

    if alert.status == "open":
        alert.status = "acknowledged"

    if getattr(alert, "operators_id", None) in (None, 0):
        alert.operators_id = operator_id

    await db.flush()
    return alert


async def mark_operator_task_in_progress(
    db: AsyncSession,
    *,
    resident_id: int,
    operator_id: int,
):
    result = await db.execute(
        select(OperatorTask)
        .where(
            OperatorTask.resident_id == resident_id,
            OperatorTask.operator_id == operator_id,
            OperatorTask.completed_at.is_(None),
            OperatorTask.status.in_(["assigned", "pending", "open"])
        )
        .order_by(desc(OperatorTask.created_at))
        .limit(1)
    )
    task = result.scalar_one_or_none()

    if task:
        task.status = "in_progress"
        await db.flush()

    return task


async def close_alert_and_task(
    db: AsyncSession,
    alert_id: int,
    operator_id: int,
    result_value: str,
    task_type: str | None = None,
    description: str | None = None,
):
    alert_result = await db.execute(
        select(Alert).where(Alert.alert_id == alert_id)
    )
    alert = alert_result.scalar_one_or_none()

    if not alert:
        return None, None, None

    now = datetime.now()

    # 🔥 alert 상태 처리
    if result_value == "wrong_alarm":
        alert.status = "false_positive"
    else:
        alert.status = "resolved"

    alert.resolved_at = now

    # 🔥 result → task_type 자동 매핑
    TASK_TYPE_MAP = {
        "ok": "NORMAL",
        "wrong_alarm": "FALSE_ALARM",
        "needs_help": "HELP",
        "emergency": "EMERGENCY",
    }

    task_type = task_type or TASK_TYPE_MAP.get(result_value, "UNKNOWN")

    # 🔥 description fallback
    description = description or None

    # 🔥 action 저장
    close_action = AlertAction(
        alert_id=alert_id,
        operators_id=operator_id,
        action_type="close",
        result=result_value,
        notes=_make_notes(description),
    )
    db.add(close_action)
    await db.flush()

    # 🔥 기존 task 조회
    task_result = await db.execute(
        select(OperatorTask)
        .where(
            OperatorTask.resident_id == alert.resident_id,
            OperatorTask.operator_id == operator_id,
            OperatorTask.completed_at.is_(None),
        )
        .order_by(desc(OperatorTask.created_at))
        .limit(1)
    )
    task = task_result.scalar_one_or_none()

    if task:
        # 🔥 기존 task 업데이트
        task.status = "completed"
        task.completed_at = now
        task.task_type = task_type
        task.description = description

    else:
        # 🔥 task 없으면 새로 생성
        task = OperatorTask(
            resident_id=alert.resident_id,
            alert_id=alert.alert_id,
            operator_id=operator_id,
            status="completed",
            created_at=now,
            completed_at=now,
            task_type=task_type,
            description=description,
        )
        db.add(task)

    await db.flush()

    # 🔥 sensitivity_weight 업데이트
    setting_stmt = select(ResidentSetting).where(
        ResidentSetting.resident_id == alert.resident_id
    )
    setting = (await db.execute(setting_stmt)).scalar_one_or_none()

    if setting:
        setting.sensitivity_weight = (
            (setting.sensitivity_weight or Decimal("1.0")) + Decimal("0.1")
        )
        print(
            f"주민 ID {alert.resident_id}의 민감도 가중치가 {setting.sensitivity_weight}로 조정되었습니다."
        )

    await db.commit()

    return alert, task, close_action