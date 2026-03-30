from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operator import Operator


async def get_operator_by_email(
    db: AsyncSession,
    email: str
):

    stmt = select(Operator).where(
        Operator.email == email
    )

    result = await db.execute(stmt)

    return result.scalar_one_or_none()