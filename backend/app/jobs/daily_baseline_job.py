# app/jobs/daily_baseline_job.py
import json
from datetime import datetime, timezone, date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.models.daily_feature import DailyFeature
from app.models.risk_score import RiskScore
from app.models.resident_setting import ResidentSetting
from app.services.risk_utils import LEVEL_SCORE01, clamp01, parse_config

MODEL_DIR = Path("app/ml/saved_models")


def level_from_daily_raw(raw_score: float, meta: dict) -> str:
    p01 = float(meta["score_p01"])
    p03 = float(meta["score_p03"])
    p10 = float(meta["score_p10"])

    if raw_score < p01:
        return "emergency"
    if raw_score < p03:
        return "alert"
    if raw_score < p10:
        return "watch"
    return "normal"


async def upsert_baseline_for_resident(db: AsyncSession, df_row: DailyFeature) -> None:
    resident_id = int(df_row.resident_id)
    feature_id = int(df_row.feature_id)

    model_path = MODEL_DIR / f"model_{resident_id}.pkl"
    scaler_path = MODEL_DIR / f"scaler_{resident_id}.pkl"
    meta_path = MODEL_DIR / f"meta_{resident_id}.json"

    if not (model_path.exists() and scaler_path.exists() and meta_path.exists()):
        # 모델이 없으면 스킵(학습/저장 선행 필요)
        return

    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    # daily 피처 6개로 추론
    current_features = {
        "x1": df_row.x1_motion_count,
        "x2": df_row.x2_door_count,
        "x3": df_row.x3_avg_interval,
        "x4": df_row.x4_night_motion_count,
        "x5": df_row.x5_first_motion_min,
        "x6": df_row.x6_last_motion_min,
    }

    cols = meta.get("feature_cols", ["x1", "x2", "x3", "x4", "x5", "x6"])
    X = pd.DataFrame([current_features], columns=cols).replace([np.inf, -np.inf], np.nan).fillna(0)

    # meta에 정의된 전처리 적용
    pp = meta.get("preprocess", {})
    clip_cfg = pp.get("clip", {})
    tf_cfg = pp.get("transform", {})

    for k, (lo, hi) in clip_cfg.items():
        if k in X.columns:
            X[k] = X[k].clip(float(lo), float(hi))
    for k, t in tf_cfg.items():
        if k in X.columns and t == "log1p":
            X[k] = np.log1p(X[k].astype(float))

    Xs = scaler.transform(X)
    raw = float(model.decision_function(Xs)[0])

    level = level_from_daily_raw(raw, meta)
    s_base = float(LEVEL_SCORE01[level])

    now_utc = datetime.now(timezone.utc)

    # risk_scores upsert: feature_id 기준 1행을 유지(권장)
    existing = (await db.execute(select(RiskScore).where(RiskScore.feature_id == feature_id))).scalar_one_or_none()
    reason = {
        "mode": "daily_baseline",
        "raw_score": round(raw, 6),
        "decision": level,
        "mapped_s_base": round(s_base, 4),
    }

    if existing is None:
        db.add(
            RiskScore(
                feature_id=feature_id,
                s_base=round(s_base, 4),
                score=round(s_base, 4),
                level=level,
                reason_codes=reason,
                scored_at=now_utc.replace(tzinfo=None),
            )
        )
    else:
        existing.s_base = round(s_base, 4)
        existing.score = round(s_base, 4)
        existing.level = level
        existing.reason_codes = reason
        existing.scored_at = now_utc.replace(tzinfo=None)


async def run_daily_baseline(target_date: date | None = None) -> None:
    # target_date 지정 없으면 오늘(로컬) 기준
    if target_date is None:
        target_date = datetime.now().date()

    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(DailyFeature).where(DailyFeature.target_date == target_date)
            )
        ).scalars().all()

        for r in rows:
            await upsert_baseline_for_resident(db, r)

        await db.commit()


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_daily_baseline())