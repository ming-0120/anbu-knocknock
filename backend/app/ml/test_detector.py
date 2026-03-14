import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.models.daily_feature import DailyFeature
from app.ml.train_model import build_df, MODEL_DIR

async def evaluate(resident_id):

    model = joblib.load(MODEL_DIR / f"model_{resident_id}.pkl")
    scaler = joblib.load(MODEL_DIR / f"scaler_{resident_id}.pkl")
    meta = json.loads((MODEL_DIR / f"meta_{resident_id}.json").read_text())

    async with AsyncSessionLocal() as db:

        stmt = select(DailyFeature).where(
            DailyFeature.resident_id == resident_id
        )

        rows = (await db.execute(stmt)).scalars().all()

    df = build_df(rows)

    X = scaler.transform(df)

    scores = model.decision_function(X)

    print("samples:", len(scores))
    print("min:", np.min(scores))
    print("max:", np.max(scores))
    print("mean:", np.mean(scores))

    p01 = meta["score_p01"]
    p03 = meta["score_p03"]
    p10 = meta.get("score_p10")

    print("cutoffs:", p01, p03, p10)

    emergency = np.sum(scores < p01)
    alert = np.sum((scores >= p01) & (scores < p03))
    watch = np.sum((scores >= p03) & (scores < p10))

    print("emergency:", emergency)
    print("alert:", alert)
    print("watch:", watch)

import asyncio

async def main():
    await evaluate(5000)   # resident_id 하나 넣기

if __name__ == "__main__":
    asyncio.run(main())