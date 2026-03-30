from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.alert import Alert


async def create_alert_if_needed(
    db: AsyncSession,
    *,
    resident_id: int,
    risk_id: int,
    risk_level: str,
    summary: str | None = None,
):

    # 위험 단계가 아니면 alert 생성 안함
    if risk_level not in ("alert", "emergency"):
        return None

    # 이미 최근 alert이 있는지 확인 (중복 방지)
    stmt = (
        select(Alert)
        .where(Alert.resident_id == resident_id)
        .order_by(Alert.created_at.desc())
        .limit(1)
    )

    last_alert = await db.scalar(stmt)

    if last_alert and last_alert.status == "open":
        return last_alert

    alert = Alert(
        resident_id=resident_id,
        risk_id=risk_id,
        status="open",
        summary=summary or "위험 패턴 감지",
    )

    db.add(alert)
    await db.flush()

    return alert