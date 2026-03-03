import json
from datetime import datetime, timezone, date
from pathlib import Path
from typing import List, Any, Dict, Optional

import numpy as np
import pandas as pd
import joblib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from app.models.resident_setting import ResidentSetting
from app.models.daily_feature import DailyFeature
from app.db.database import AsyncSessionLocal, async_engine

MODEL_DIR = Path("app/ml/saved_models")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

BASE_CONTAMINATION = 0.05
MIN_SAMPLES = 60


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _is_weekend(d: date) -> int:
    # Monday=0 ... Sunday=6
    return 1 if d.weekday() >= 5 else 0


async def _get_sensitivity_weight(resident_id: int, db: AsyncSession) -> float:
    stmt = select(ResidentSetting).where(ResidentSetting.resident_id == resident_id)
    setting = (await db.execute(stmt)).scalar_one_or_none()
    if not setting or setting.sensitivity_weight is None:
        return 1.0
    try:
        return float(setting.sensitivity_weight)
    except Exception:
        return 1.0


def _build_df(features: List[DailyFeature]) -> pd.DataFrame:
    """
    x1~x6 + 파생 x7,x8 + x9_is_weekend
    - x7 = x4/(x1+1)
    - x8 = x1/(x3+1)   (x3 raw avg_interval 기준)
    - x9 = is_weekend (0/1)
    """
    rows = []
    for f in features:
        x1 = float(f.x1_motion_count or 0)
        x2 = float(f.x2_door_count or 0)
        x3 = float(f.x3_avg_interval or 0)
        x4 = float(f.x4_night_motion_count or 0)
        x5 = float(f.x5_first_motion_min or 0)
        x6 = float(f.x6_last_motion_min or 0)

        x7 = x4 / (x1 + 1.0)
        x8 = x1 / (x3 + 1.0)
        x9 = float(_is_weekend(f.target_date))  # 0/1

        rows.append(
            {
                "x1": x1,
                "x2": x2,
                "x3": x3,
                "x4": x4,
                "x5": x5,
                "x6": x6,
                "x7": x7,
                "x8": x8,
                "x9": x9,
            }
        )
    return pd.DataFrame(rows)


def _preprocess_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    - x3/x5: clip(0~1440) 후 log1p
    - x6/x7/x8: clip(0~1440)
    - x9: 0/1 (clip 0~1)
    """
    df = df.replace([np.inf, -np.inf], np.nan).dropna()

    for col in ["x3", "x5", "x6", "x7", "x8"]:
        df[col] = df[col].clip(0.0, 1440.0)

    df["x9"] = df["x9"].clip(0.0, 1.0)

    df["x3"] = np.log1p(df["x3"])
    df["x5"] = np.log1p(df["x5"])

    return df


def _save_artifacts(resident_id: int, model, scaler, meta: dict) -> None:
    joblib.dump(model, MODEL_DIR / f"model_{resident_id}.pkl")
    joblib.dump(scaler, MODEL_DIR / f"scaler_{resident_id}.pkl")
    (MODEL_DIR / f"meta_{resident_id}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def train_resident_model(resident_id: int, db: AsyncSession) -> None:
    stmt = (
        select(DailyFeature)
        .where(DailyFeature.resident_id == resident_id)
        .order_by(DailyFeature.target_date.desc())
        .limit(365)
    )
    features = (await db.execute(stmt)).scalars().all()

    if len(features) < MIN_SAMPLES:
        print(f"⚠️ {resident_id}번: 데이터 부족으로 학습 스킵 (n={len(features)})")
        return

    df = _build_df(features)
    df = _preprocess_df(df)
    if len(df) < MIN_SAMPLES:
        print(f"⚠️ {resident_id}번: 전처리 후 데이터 부족 (n={len(df)})")
        return

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df)

    model = IsolationForest(
        n_estimators=400,
        contamination=BASE_CONTAMINATION,
        random_state=42,
        max_features=0.6,
    )
    model.fit(X_scaled)

    scores = model.decision_function(X_scaled)
    base_threshold = float(np.quantile(scores, BASE_CONTAMINATION))
    score_p01 = float(np.quantile(scores, 0.01))
    score_p03 = float(np.quantile(scores, 0.03))
    score_p05 = float(np.quantile(scores, 0.05))
    score_p10 = float(np.quantile(scores, 0.10))
    score_p50 = float(np.quantile(scores, 0.50))
    score_p95 = float(np.quantile(scores, 0.95))
    score_p99 = float(np.quantile(scores, 0.99))
    score_p20 = float(np.quantile(scores, 0.20))
    score_mean = float(np.mean(scores))
    score_std = float(np.std(scores))

    sensitivity_weight = await _get_sensitivity_weight(resident_id, db)
    effective_threshold = _clamp(base_threshold * sensitivity_weight, score_p01, score_p99)

    meta = {
        "version": "v3_single_with_is_weekend",
        "resident_id": resident_id,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "n_samples": int(len(df)),
        "base_contamination": float(BASE_CONTAMINATION),
        "base_threshold": base_threshold,
        "effective_threshold": float(effective_threshold),
        "sensitivity_weight": float(sensitivity_weight),
        "score_p01": score_p01,
        "score_p03": score_p03,
        "score_p05": score_p05,
        "score_p10": score_p10,
        "score_p50": score_p50,
        "score_p95": score_p95,
        "score_p99": score_p99,
        "score_p20": score_p20,
        "score_mean": score_mean,
        "score_std": score_std,
        "feature_cols": ["x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8", "x9"],
        "preprocess": {
            "clip": {
                "x3": [0.0, 1440.0],
                "x5": [0.0, 1440.0],
                "x6": [0.0, 1440.0],
                "x7": [0.0, 1440.0],
                "x8": [0.0, 1440.0],
                "x9": [0.0, 1.0],
            },
            "transform": {
                "x3": "log1p",
                "x5": "log1p",
            },
            "derived": {
                "x7": "x4/(x1+1)",
                "x8": "x1/(x3+1)  # x3 raw avg_interval before log",
                "x9": "is_weekend(target_date) in {0,1}",
            },
        },
    }

    _save_artifacts(resident_id, model, scaler, meta)

    print(
        f"✅ {resident_id}번 모델 업데이트 | n={len(df)} | "
        f"base_threshold={base_threshold:.6f} | effective_threshold={effective_threshold:.6f}"
    )


async def train_all_residents() -> None:
    async with AsyncSessionLocal() as db:
        stmt = select(DailyFeature.resident_id).distinct()
        resident_ids = (await db.execute(stmt)).scalars().all()
        for r_id in resident_ids:
            await train_resident_model(r_id, db)


if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(train_all_residents())
    finally:
        try:
            asyncio.run(async_engine.dispose())
        except Exception:
            pass