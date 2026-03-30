from sqlalchemy import select, func
from app.models.operator import Operator
from app.models.operator_location import OperatorLocation

async def find_nearby_operators(db, lat, lon, radius=3):
    distance_expr = (
        6371 * func.acos(
            func.cos(func.radians(lat))
            * func.cos(func.radians(OperatorLocation.latitude))
            * func.cos(func.radians(OperatorLocation.longitude) - func.radians(lon))
            + func.sin(func.radians(lat))
            * func.sin(func.radians(OperatorLocation.latitude))
        )
    )

    stmt = (
        select(
            Operator.operators_id,
            Operator.name,
            Operator.last_seen,
            OperatorLocation.latitude,
            OperatorLocation.longitude,
            distance_expr.label("distance")
        )
        .join(
            OperatorLocation,
            Operator.operators_id == OperatorLocation.operators_id
        )
        .where(distance_expr <= radius)
        .order_by(distance_expr)
        .limit(10)
    )

    result = await db.execute(stmt)

    rows = result.mappings().all()

    operators = [
        {
            "operators_id": r["operators_id"],
            "name": r["name"],
            "last_seen": r["last_seen"],
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "distance": float(r["distance"]) if r["distance"] is not None else None
        }
        for r in rows
    ]

    return operators