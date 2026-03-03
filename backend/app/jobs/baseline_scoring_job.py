import asyncio
import json
from datetime import datetime, date, time, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.models.daily_feature import DailyFeature
from app.models.risk_score import RiskScore
from app.models.resident_setting import ResidentSetting

MODEL_DIR = Path("app/ml/saved_models")

DISEASE_RULES = {"ALD": 5, "DEP": 4, "HTN": 2, "DM": 3, "COPD": 4, "OTHER": 3}
WEEKDAY_MAP = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}

LEVEL_SCORE = {"normal": 0.20, "watch": 0.50, "alert": 0.75, "emergency": 0.95}


def _parse_config(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return {}


def _time_in_range(start_hhmm: str, end_hhmm: str, now_time) -> bool:
    start = datetime.strptime(start_hhmm, "%H:%M").time()
    end = datetime.strptime(end_hhmm, "%H:%M").time()
    if start <= end:
        return start <= now_time <= end
    return (now_time >= start) or (now_time <= end)


async def get_resident_weights(resident_id: int, db: AsyncSession):
    stmt = select(ResidentSetting).where(ResidentSetting.resident_id == resident_id)
    setting = (await db.execute(stmt)).scalar_one_or_none()

    if not setting:
        return 1.0, 1.0, 1.0

    config = _parse_config(setting.days_of_week)

    now = datetime.now()
    current_time = now.time()
    current_weekday_str = WEEKDAY_MAP[now.weekday()]

    d_score = 0
    diseases = (config.get("health") or {}).get("diseases") or []

    for d in diseases:
        # 케이스1) dict: {"code": "...", "is_active": true/false}
        if isinstance(d, dict):
            if d.get("is_active"):
                code = d.get("code") or "OTHER"
                d_score += DISEASE_RULES.get(code, DISEASE_RULES["OTHER"])
            continue

        # 케이스2) str: "DEP" 처럼 코드만 들어온 경우 -> 활성으로 간주
        if isinstance(d, str):
            code = d.strip() or "OTHER"
            d_score += DISEASE_RULES.get(code, DISEASE_RULES["OTHER"])
            continue

        # 케이스3) 그 외 타입은 무시
        continue

    alpha_disease = 1 + (d_score * 0.05)

    w_outing = 1.0
    for o in config.get("routine", {}).get("outings", []):
        if current_weekday_str not in (o.get("days") or []):
            continue
        for sch in (o.get("schedule") or []):
            s = sch.get("start")
            e = sch.get("end")
            if not s or not e:
                continue
            if _time_in_range(s, e, current_time):
                w_outing = 0.5
                break
        if w_outing != 1.0:
            break

    s_weight = float(setting.sensitivity_weight) if setting.sensitivity_weight else 1.0
    return float(alpha_disease), float(w_outing), float(s_weight)


def _level_from_raw_score(raw_score: float, meta: Dict[str, Any]) -> str:
    # meta에 필수로 있어야 함
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


async def upsert_risk_score(
    db: AsyncSession,
    feature_id: int,
    s_base: float,
    score: float,
    level: str,
    reason_codes: Dict[str, Any],
    scored_at: datetime,
):
    # feature_id로 기존 row가 있는지 확인
    exists_stmt = select(RiskScore).where(RiskScore.feature_id == feature_id).limit(1)
    existing = (await db.execute(exists_stmt)).scalars().first()

    if existing:
        upd = (
            update(RiskScore)
            .where(RiskScore.feature_id == feature_id)
            .values(
                s_base=float(s_base),
                score=float(score),
                level=level,
                reason_codes=reason_codes,
                scored_at=scored_at,
            )
        )
        await db.execute(upd)
    else:
        db.add(
            RiskScore(
                feature_id=feature_id,
                s_base=float(s_base),
                score=float(score),
                level=level,
                reason_codes=reason_codes,
                scored_at=scored_at,
            )
        )


async def baseline_scoring(target_date: date, scored_hour: int = 4):
    """
    daily_features(target_date)를 읽어서 risk_scores를 채운다.
    - resident 모델 파일이 없으면 스킵(989까지만 학습된 상태 고려)
    - feature_id 기준 upsert
    """
    scored_at = datetime.combine(target_date, time(scored_hour, 0)).replace(tzinfo=timezone.utc)

    async with AsyncSessionLocal() as db:
        stmt = select(DailyFeature).where(DailyFeature.target_date == target_date)
        daily_rows = (await db.execute(stmt)).scalars().all()

        if not daily_rows:
            print(f"⚠️ daily_features가 없습니다: target_date={target_date}")
            return

        upserted = 0
        skipped_no_model = 0
        skipped_bad_meta = 0

        for f in daily_rows:
            resident_id = int(f.resident_id)
            feature_id = int(f.feature_id)

            model_path = MODEL_DIR / f"model_{resident_id}.pkl"
            scaler_path = MODEL_DIR / f"scaler_{resident_id}.pkl"
            meta_path = MODEL_DIR / f"meta_{resident_id}.json"

            if not (model_path.exists() and scaler_path.exists() and meta_path.exists()):
                skipped_no_model += 1
                continue

            try:
                model = joblib.load(model_path)
                scaler = joblib.load(scaler_path)
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"⚠️ model/scaler/meta 로드 실패: resident_id={resident_id} err={e}")
                skipped_no_model += 1
                continue

            # detector가 기대하는 x1~x6로 매핑
            current_features = {
                "x1": float(f.x1_motion_count),
                "x2": float(f.x2_door_count),
                "x3": float(f.x3_avg_interval),
                "x4": float(f.x4_night_motion_count),
                "x5": float(f.x5_first_motion_min),
                "x6": float(f.x6_last_motion_min),
            }

            # 전처리 + raw_score
            feature_cols = meta.get("feature_cols", ["x1", "x2", "x3", "x4", "x5", "x6"])
            df = pd.DataFrame([current_features], columns=feature_cols)
            df = df.replace([np.inf, -np.inf], np.nan).fillna(0)

            pp = meta.get("preprocess", {})
            clip_cfg = pp.get("clip", {})
            tf_cfg = pp.get("transform", {})

            for k, bounds in clip_cfg.items():
                if k in df.columns and isinstance(bounds, (list, tuple)) and len(bounds) == 2:
                    lo, hi = bounds
                    df[k] = df[k].clip(float(lo), float(hi))

            for k, t in tf_cfg.items():
                if k in df.columns and t == "log1p":
                    df[k] = np.log1p(df[k].astype(float))

            try:
                X_scaled = scaler.transform(df)
                raw_score = float(model.decision_function(X_scaled)[0])
            except Exception as e:
                print(f"⚠️ 추론 실패: resident_id={resident_id} err={e}")
                skipped_no_model += 1
                continue

            # (옵션) 룰 게이트: x6>=720이면 emergency 고정
            x6 = float(current_features.get("x6", 0))
            if x6 >= 720:
                level = "emergency"
                s_base_val = 1.0
                mode = "rule_gate"
            else:
                try:
                    level = _level_from_raw_score(raw_score, meta)
                except Exception as e:
                    skipped_bad_meta += 1
                    print(f"⚠️ meta 분위수 키 누락/오류: resident_id={resident_id} err={e}")
                    continue
                s_base_val = float(LEVEL_SCORE[level])
                mode = "quantile_cutoff"

            # 가중치(질병/외출/민감도) — 기존 detector와 동일하게 계산
            alpha, w_out, s_weight = await get_resident_weights(resident_id, db)

            # 현재 detector는 s_weight를 실제 점수에 반영하지 않았으므로 동일하게 둠(원하면 곱해도 됨)
            s_final_val = min(1.0, float(s_base_val) * float(alpha) * float(w_out))

            reason = {
                "mode": mode,
                "resident_id": resident_id,
                "raw_score": round(raw_score, 6),
                "alpha_disease": round(alpha, 2),
                "w_outing": round(w_out, 2),
                "sensitivity": round(s_weight, 2),
            }

            await upsert_risk_score(
                db=db,
                feature_id=feature_id,
                s_base=float(s_base_val),
                score=float(s_final_val),
                level=level,
                reason_codes=reason,
                scored_at=scored_at,
            )
            upserted += 1

        await db.commit()
        print(
            f"✅ baseline scoring 완료: target_date={target_date} "
            f"upserted={upserted} skipped_no_model={skipped_no_model} skipped_bad_meta={skipped_bad_meta}"
        )


if __name__ == "__main__":
    # 오늘 날짜로 하고 싶으면 date.today()로 바꾸면 됨
    asyncio.run(baseline_scoring(target_date=date(2026, 3, 3), scored_hour=4))