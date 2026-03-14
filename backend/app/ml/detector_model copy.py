import json
import joblib
import numpy as np
import pandas as pd
import time

from datetime import datetime, timedelta, timezone
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.mysql import insert as mysql_insert

from app.db.database import async_engine
from app.models.hourly_feature import HourlyFeature
from app.models.risk_score import RiskScore
from app.models.resident_setting import ResidentSetting
from app.models.operator_task import OperatorTask
from app.models.alert import Alert

from app.ml.train_model import MODEL_DIR


MODEL_CACHE = {}
SETTING_CACHE = {}

LEVEL_SCORE = {
    "normal": 0.2,
    "watch": 0.5,
    "alert": 0.75,
    "emergency": 0.95,
}


AsyncSessionMaker = sessionmaker(
    async_engine,
    expire_on_commit=False,
    class_=AsyncSession
)


def get_model(resident_id):

    if resident_id in MODEL_CACHE:
        return MODEL_CACHE[resident_id]

    model = joblib.load(MODEL_DIR / f"model_{resident_id}.pkl")
    scaler = joblib.load(MODEL_DIR / f"scaler_{resident_id}.pkl")
    meta = json.loads((MODEL_DIR / f"meta_{resident_id}.json").read_text())

    MODEL_CACHE[resident_id] = (model, scaler, meta)

    return MODEL_CACHE[resident_id]


async def load_settings(db, resident_ids):

    stmt = (
        select(
            ResidentSetting.resident_id,
            ResidentSetting.sensitivity_weight
        )
        .where(ResidentSetting.resident_id.in_(resident_ids))
    )

    rows = (await db.execute(stmt)).all()

    for r in rows:

        alpha = 1.0
        w_out = 1.0
        sensitivity = float(r.sensitivity_weight or 1)

        SETTING_CACHE[r.resident_id] = (alpha, w_out, sensitivity)


async def load_operator_status(db):

    stmt = (
        select(
            OperatorTask.resident_id,
            OperatorTask.status
        )
        .order_by(OperatorTask.created_at.desc())
    )

    rows = (await db.execute(stmt)).all()

    status_map = {}

    for r in rows:
        if r.resident_id not in status_map:
            status_map[r.resident_id] = r.status

    return status_map


def get_operator_factor(status):

    if status == "closed":
        return 0.8

    if status == "assigned":
        return 1.2

    if status == "in_progress":
        return 1.0

    return 1.0


def build_features(rows):

    data = defaultdict(list)

    for r in rows:
        data[r.resident_id].append(r)

    features = {}

    for rid, items in data.items():

        items.sort(key=lambda x: x.target_hour)

        latest_feature_id = items[-1].feature_id

        motion = np.array([i.x1_motion_count for i in items])
        door = np.array([i.x2_door_count for i in items])

        times = [i.target_hour for i in items]

        x1 = motion.sum()
        x2 = door.sum()
        x3 = motion.mean()

        night = [
            i.x1_motion_count
            for i in items
            if i.target_hour.hour < 6
        ]

        x4 = sum(night)

        first_motion = min(times).hour * 60
        last_motion = max(times).hour * 60

        features[rid] = {
            "feature_id": latest_feature_id,
            "x": np.array([
                x1,
                x2,
                x3,
                x4,
                first_motion,
                last_motion
            ])
        }

    return features


async def run_batch():

    start = time.time()

    print()
    print("========== DETECTOR START ==========")

    async with AsyncSessionMaker() as db:

        stmt = (
            select(HourlyFeature)
            .where(
                HourlyFeature.target_hour
                >= datetime.now(timezone.utc) - timedelta(hours=24)
            )
        )

        rows = (await db.execute(stmt)).scalars().all()

        if not rows:
            print("no hourly data")
            return

        features = build_features(rows)

        resident_ids = list(features.keys())

        total = len(resident_ids)
        processed = 0

        print("hourly rows:", len(rows))
        print("residents:", total)
        print()

        await load_settings(db, resident_ids)

        operator_status = await load_operator_status(db)

        stmt = select(Alert.resident_id).where(Alert.status == "open")

        open_alert = set((await db.execute(stmt)).scalars().all())

        risk_rows = []
        new_alerts = []

        now = datetime.now(timezone.utc)

        for rid in resident_ids:

            processed += 1

            model, scaler, meta = get_model(rid)

            alpha, w_out, sensitivity = SETTING_CACHE.get(
                rid,
                (1, 1, 1)
            )

            operator_factor = get_operator_factor(
                operator_status.get(rid)
            )

            feature_id = features[rid]["feature_id"]
            x = features[rid]["x"]

            x7 = x[3] / (x[0] + 1)
            x8 = x[0] / (x[2] + 1)
            x9 = 0
            x10 = x[0] - x[3]
            x11 = max(x[5] - x[4], 0)

            cols = meta["feature_cols"]

            X = pd.DataFrame(
                [[
                    x[0], x[1], x[2], x[3], x[4], x[5],
                    x7, x8, x9, x10, x11
                ]],
                columns=cols
            )

            X = scaler.transform(X)

            raw_score = model.decision_function(X)[0]

            p01 = meta["score_p01"]
            p03 = meta["score_p03"]
            p10 = meta["score_p10"]

            if raw_score < p01:
                decision = "emergency"
            elif raw_score < p03:
                decision = "alert"
            elif raw_score < p10:
                decision = "watch"
            else:
                decision = "normal"

            base = LEVEL_SCORE[decision]

            score = min(
                100,
                base * alpha * w_out * operator_factor
            )

            risk_rows.append({
                "feature_id": feature_id,
                "s_base": base,
                "score": score,
                "level": decision,
                "reason_codes": {
                    "raw_score": float(raw_score),
                    "decision": decision
                },
                "scored_at": now
            })

            if decision in ("alert", "emergency"):

                if rid not in open_alert:

                    new_alerts.append(
                        Alert(
                            resident_id=rid,
                            status="open",
                            summary="위험 패턴 감지",
                            created_at=now
                        )
                    )

                    open_alert.add(rid)

            if processed % 50 == 0 or processed == total:

                percent = round(processed / total * 100, 2)
                elapsed = round(time.time() - start, 2)

                print(
                    f"[PROGRESS] {processed}/{total} "
                    f"({percent}%) elapsed={elapsed}s"
                )

        insert_stmt = mysql_insert(RiskScore).values(risk_rows)

        update_stmt = insert_stmt.on_duplicate_key_update(

            s_base=insert_stmt.inserted.s_base,
            score=insert_stmt.inserted.score,
            level=insert_stmt.inserted.level,
            reason_codes=insert_stmt.inserted.reason_codes,
            scored_at=insert_stmt.inserted.scored_at
        )

        await db.execute(update_stmt)

        if new_alerts:
            db.add_all(new_alerts)

        await db.commit()

    end = time.time()

    print()
    print("========== COMPLETE ==========")
    print("processed:", total)
    print("time:", round(end - start, 2), "sec")
    print()


if __name__ == "__main__":

    import asyncio

    async def main():

        try:
            await run_batch()
        finally:
            await async_engine.dispose()

    asyncio.run(main())