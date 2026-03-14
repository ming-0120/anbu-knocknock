import asyncio
import joblib
import numpy as np
import pandas as pd

from datetime import date, timedelta
from pathlib import Path

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.models.daily_feature import DailyFeature


MODEL_DIR = Path("app/ml/saved_models")
MODEL_DIR.mkdir(parents=True, exist_ok=True)


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


        rows.append([
            x1, x2, x3, x4, x5, x6
        ])

    df = pd.DataFrame(rows, columns=[
        "x1_motion_count",
        "x2_door_count",
        "x3_avg_interval",
        "x4_night_motion_count",
        "x5_first_motion_min",
        "x6_last_motion_min"
    ])

    df = df.replace([np.inf, -np.inf], np.nan).dropna()
    
    df["x3_avg_interval"] = np.log1p(df["x3_avg_interval"])    
    df["x5_first_motion_min"] = np.log1p(df["x5_first_motion_min"])

    return df


async def main():

    async with AsyncSessionLocal() as db:

        stmt = select(DailyFeature).where(
            DailyFeature.target_date >= date.today() - timedelta(days=365)
        )

        rows = (await db.execute(stmt)).scalars().all()

    df = build_df(rows)

    print("training rows:", len(df))

    scaler = StandardScaler()
    X = scaler.fit_transform(df)

    model = IsolationForest(
        n_estimators=300,
        contamination=0.05,
        random_state=42,
        n_jobs=-1
    )

    model.fit(X)

    joblib.dump(model, MODEL_DIR / "global_model.pkl")
    joblib.dump(scaler, MODEL_DIR / "global_scaler.pkl")

    print("global model saved")


if __name__ == "__main__":
    asyncio.run(main())