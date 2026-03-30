import json
import asyncio
import multiprocessing as mp
from datetime import datetime, timezone, date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
from sqlalchemy import select
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from app.db.database import AsyncSessionLocal, async_engine
from app.models.daily_feature import DailyFeature

MODEL_DIR = Path("app/ml/saved_models")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

BASE_CONTAMINATION = 0.05
MIN_SAMPLES = 30


def _is_weekend(d):
    return 1 if d.weekday() >= 5 else 0


def build_df(features):

    rows = []

    for f in features:

        x1 = float(f.x1_motion_count or 0)
        x2 = float(f.x2_door_count or 0)
        x3 = float(f.x3_avg_interval or 0)
        x4 = float(f.x4_night_motion_count or 0)
        x5 = float(f.x5_first_motion_min or 0)
        x6 = float(f.x6_last_motion_min or 0)

        x7 = x4 / (x1 + 1)
        x8 = x1 / (x3 + 1)
        x9 = _is_weekend(f.target_date)
        
        # 추가 feature
        x10 = x1 - x4
        
        # 활동 시간
        x11 = max(0, x6 - x5)
        rows.append([
            x1,x2,x3,x4,x5,x6,
            x7,x8,x9,
            x10,
            x11
        ])

    df = pd.DataFrame(rows, columns=[
        "x1","x2","x3","x4","x5","x6",
        "x7","x8","x9",
        "x10_day_night_gap",
        "x11_night_ratio"
    ])

    df = df.replace([np.inf,-np.inf],np.nan).dropna()

    df["x3"] = np.log1p(df["x3"])
    df["x5"] = np.log1p(df["x5"])

    return df


def train_one(args):

    resident_id, features = args

    if len(features) < MIN_SAMPLES:
        return

    df = build_df(features)

    if len(df) < MIN_SAMPLES:
        return

    scaler = StandardScaler()
    X = scaler.fit_transform(df)

    contamination = max(0.02, min(0.1, 30 / len(df)))

    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=42
    )

    model.fit(X)

    scores = model.decision_function(X)

    p01 = float(np.quantile(scores,0.01))
    p03 = float(np.quantile(scores,0.03))
    p10 = float(np.quantile(scores,0.10))

    meta = {
        "resident_id":resident_id,
        "trained_at":datetime.now(timezone.utc).isoformat(),
        "score_p01":p01,
        "score_p03":p03,
        "score_p10":p10,
        "n_samples":len(df),
        "feature_cols": df.columns.tolist()
    }

    joblib.dump(model, MODEL_DIR / f"model_{resident_id}.pkl")
    joblib.dump(scaler, MODEL_DIR / f"scaler_{resident_id}.pkl")

    (MODEL_DIR / f"meta_{resident_id}.json").write_text(
        json.dumps(meta,ensure_ascii=False,indent=2),
        encoding="utf-8"
    )

    return resident_id


async def load_features():

    async with AsyncSessionLocal() as db:

        stmt = select(DailyFeature).where(
            DailyFeature.target_date >= date.today() - timedelta(days=365)
        )

        rows = (await db.execute(stmt)).scalars().all()

        grouped = {}

        for r in rows:
            grouped.setdefault(r.resident_id,[]).append(r)

        return grouped


async def main():

    grouped = await load_features()

    print("resident count:", len(grouped))

    args = [(rid,features) for rid,features in grouped.items()]

    cpu = mp.cpu_count()

    print("cpu:", cpu)

    with mp.Pool(cpu) as pool:

        results = pool.map(train_one, args)

    print("trained:", len([r for r in results if r]))


if __name__ == "__main__":

    asyncio.run(main())