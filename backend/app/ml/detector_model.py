import json
import joblib
import pandas as pd
import numpy as np
from datetime import datetime, timezone, date
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resident_setting import ResidentSetting
from app.models.risk_score import RiskScore
from app.models.daily_feature import DailyFeature  # ✅ feature_id -> target_date 조회용
from app.ml.train_model import MODEL_DIR  # MODEL_DIR 재사용

DISEASE_RULES = {"ALD": 5, "DEP": 4, "HTN": 2, "DM": 3, "COPD": 4, "OTHER": 3}
WEEKDAY_MAP = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}

def _parse_config(raw):
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
    for d in config.get("health", {}).get("diseases", []):
        # diseases가 str로 들어오는 케이스 방어
        if isinstance(d, dict) and d.get("is_active"):
            d_score += DISEASE_RULES.get(d.get("code"), 3)
    alpha_disease = 1 + (d_score * 0.05)

    w_outing = 1.0
    for o in config.get("routine", {}).get("outings", []):
        if current_weekday_str not in (o.get("days") or []):
            continue
        for sch in (o.get("schedule") or []):
            start = sch.get("start")
            end = sch.get("end")
            if not start or not end:
                continue
            if _time_in_range(start, end, current_time):
                w_outing = 0.5
                break
        if w_outing != 1.0:
            break

    s_weight = float(setting.sensitivity_weight) if setting.sensitivity_weight else 1.0
    return alpha_disease, w_outing, s_weight

def _is_weekend(d: date) -> float:
    return 1.0 if d.weekday() >= 5 else 0.0

async def _get_target_date_from_feature_id(feature_id: int, db: AsyncSession) -> date:
    stmt = select(DailyFeature.target_date).where(DailyFeature.feature_id == feature_id)
    return (await db.execute(stmt)).scalar_one()

async def detect_resident_risk(
    resident_id: int,
    feature_id: int,
    current_features: dict,
    db: AsyncSession,
    target_date: date | None = None,   # ✅ 없으면 feature_id로 조회
):
    try:
        if target_date is None:
            target_date = await _get_target_date_from_feature_id(feature_id, db)

        # 1) 파일 로드(통합 1모델)
        model = joblib.load(MODEL_DIR / f"model_{resident_id}.pkl")
        scaler = joblib.load(MODEL_DIR / f"scaler_{resident_id}.pkl")
        meta = json.loads((MODEL_DIR / f"meta_{resident_id}.json").read_text(encoding="utf-8"))

        # 2) x7,x8,x9 생성해서 current_features에 주입
        x1 = float(current_features.get("x1", 0))
        x3 = float(current_features.get("x3", 0))
        x4 = float(current_features.get("x4", 0))

        current_features = dict(current_features)
        current_features["x7"] = float(x4) / (float(x1) + 1.0)
        current_features["x8"] = float(x1) / (float(x3) + 1.0)
        current_features["x9"] = _is_weekend(target_date)

        # 3) 전처리 -> raw_score
        cols = meta.get("feature_cols", ["x1","x2","x3","x4","x5","x6","x7","x8","x9"])
        df = pd.DataFrame([current_features], columns=cols)
        df = df.replace([np.inf, -np.inf], np.nan).fillna(0)

        pp = meta.get("preprocess", {})
        clip_cfg = pp.get("clip", {})
        tf_cfg = pp.get("transform", {})

        for k, (lo, hi) in clip_cfg.items():
            if k in df.columns:
                df[k] = df[k].clip(float(lo), float(hi))

        for k, t in tf_cfg.items():
            if k in df.columns and t == "log1p":
                df[k] = np.log1p(df[k].astype(float))

        X_scaled = scaler.transform(df)
        raw_score = float(model.decision_function(X_scaled)[0])

        # 4) 가중치 조회
        alpha, w_out, s_weight = await get_resident_weights(resident_id, db)

        # 5) rule gate
        x6 = float(current_features.get("x6", 0))
        if x6 >= 720:
            level = "emergency"
            s_base_val = 100.0
            s_final_val = min(100.0, s_base_val * float(alpha) * float(w_out))

            reason_data = {
                "mode": "rule_gate",
                "rule_gate": {"rule": "x6>=720", "x6": x6},
                "alpha_disease": round(float(alpha), 2),
                "w_outing": round(float(w_out), 2),
                "sensitivity": round(float(s_weight), 2),
                "raw_score": round(float(raw_score), 6),
                "target_date": str(target_date),
                "x9_is_weekend": float(current_features["x9"]),
            }

            db.add(RiskScore(
                feature_id=feature_id,
                s_base=round(float(s_base_val), 6),
                score=round(float(s_final_val), 6),
                level=level,
                reason_codes=reason_data,
                scored_at=datetime.now(timezone.utc),
            ))
            await db.commit()
            return float(s_final_val)

        # 6) 분위수 컷
        p01 = float(meta["score_p01"])
        p03 = float(meta["score_p03"])
        p20 = float(meta["score_p20"])

        if raw_score < p01:
            level = "emergency"
        elif raw_score < p03:
            level = "alert"
        elif raw_score < p20:
            level = "watch"
        else:
            level = "normal"

        LEVEL_SCORE = {"normal": 20.0, "watch": 50.0, "alert": 75.0, "emergency": 95.0}
        s_base_val = float(LEVEL_SCORE[level])
        s_final_val = min(100.0, s_base_val * float(alpha) * float(w_out))

        # (선택) 민감도 반영을 실제 score에 쓰려면 아래처럼 곱해야 함
        # s_final_val = min(100.0, s_final_val * float(s_weight))

        reason_data = {
            "mode": "quantile_cutoff",
            "raw_score": round(float(raw_score), 6),
            "cutoffs": {"p01": round(p01, 6), "p03": round(p03, 6), "p20": round(p20, 6)},
            "decision": level,
            "alpha_disease": round(float(alpha), 2),
            "w_outing": round(float(w_out), 2),
            "sensitivity": round(float(s_weight), 2),
            "target_date": str(target_date),
            "x9_is_weekend": float(current_features["x9"]),
        }

        db.add(RiskScore(
            feature_id=feature_id,
            s_base=round(float(s_base_val), 6),
            score=round(float(s_final_val), 6),
            level=level,
            reason_codes=reason_data,
            scored_at=datetime.now(timezone.utc),
        ))
        await db.commit()
        return float(s_final_val)

    except Exception as e:
        print(f"⚠️ {resident_id}번 위험도 계산 중 에러: {e}")
        return 0.0