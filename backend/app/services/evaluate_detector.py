import os
import asyncio
import joblib
import numpy as np
import pandas as pd

from collections import defaultdict
from datetime import datetime, timedelta
from sklearn.metrics import precision_score, recall_score, f1_score
from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.models.hourly_feature import HourlyFeature
from app.models.risk_score import RiskScore

# =========================
# 설정
# =========================
MODEL_DIR = "app/ml/saved_models"


# =========================
# detector 로직 (그대로 유지)
# =========================

def calculate_asymptotic_score(anomaly_intensity, sensitivity=1.0):
    MAX_CAP = 0.95
    k = 25.0 * sensitivity
    return float(MAX_CAP * (1 - np.exp(-k * max(0, anomaly_intensity))))

def decide_level(risk_score):
    if risk_score >= 0.75:
        return "emergency"
    if risk_score >= 0.50:
        return "alert"
    if risk_score >= 0.25:
        return "watch"
    return "normal"

def detect_single(model, scaler, row):
    df = pd.DataFrame([{
        "x1_motion_count": row["x1"],
        "x2_door_count": row["x2"],
        "x3_avg_interval": np.log1p(row["x3"]),
        "x4_night_motion_count": row["x4"],
        "x5_first_motion_min": row["x5"],
        "x6_last_motion_min": row["x6"],
        "is_daytime": row["is_daytime"]
    }])

    X = scaler.transform(df)
    raw_score = float(model.decision_function(X)[0])

    intensity = 0.05 - raw_score
    risk_score = calculate_asymptotic_score(intensity)
    level = decide_level(risk_score)

    return raw_score, risk_score, level


# =========================
# 평가 로직
# =========================

async def evaluate():
    async with AsyncSessionLocal() as db:

        print("\n===== EVALUATION START =====\n")

        # ------------------------
        # 1. 시간 범위 맞추기 (detector 기준)
        # ------------------------
        now = datetime.now()
        cutoff = now - timedelta(hours=2)

        # ------------------------
        # 2. RiskScore 조회
        # ------------------------
        risk_rows = (await db.execute(
            select(RiskScore).where(RiskScore.scored_at >= cutoff)
        )).scalars().all()

        # 🔥 핵심: (resident_id + 시간) 기준 매핑
        risk_map = {}
        for r in risk_rows:
            key = (
                r.resident_id,
                r.scored_at.replace(minute=0, second=0, microsecond=0)
            )
            risk_map[key] = r.level

        print(f"RiskScore 개수: {len(risk_map)}")

        # ------------------------
        # 3. HourlyFeature 조회
        # ------------------------
        rows = (await db.execute(
            select(HourlyFeature).where(HourlyFeature.target_hour >= cutoff)
        )).scalars().all()

        if not rows:
            print("데이터 없음")
            return

        print(f"평가 대상 데이터: {len(rows)}")

        # ------------------------
        # 4. 모델 캐싱
        # ------------------------
        model_cache = {}
        scaler_cache = {}

        all_preds = []
        all_labels = []

        per_user_preds = defaultdict(list)
        per_user_labels = defaultdict(list)

        matched = 0

        # ------------------------
        # 5. 평가 루프
        # ------------------------
        for r in rows:
            resident_id = r.resident_id

            # 모델 캐싱
            if resident_id not in model_cache:
                model_path = os.path.join(MODEL_DIR, f"resident_{resident_id}_model.pkl")
                scaler_path = os.path.join(MODEL_DIR, f"resident_{resident_id}_scaler.pkl")

                if not os.path.exists(model_path):
                    continue

                model_cache[resident_id] = joblib.load(model_path)
                scaler_cache[resident_id] = joblib.load(scaler_path)

            model = model_cache[resident_id]
            scaler = scaler_cache[resident_id]

            # feature 구성
            x1 = float(r.x1_motion_count or 0)
            x2 = float(r.x2_door_count or 0)
            x3 = float(getattr(r, "x3_avg_interval", 0) or 0)
            x4 = float(getattr(r, "x4_night_motion_count", 0) or 0)
            x5 = float(getattr(r, "x5_first_motion_min", 0) or 0)
            x6 = float(getattr(r, "x6_last_motion_min", 0) or 0)

            hour = r.target_hour.hour
            is_daytime = 1.0 if 6 <= hour <= 22 else 0.0

            row_data = {
                "x1": x1,
                "x2": x2,
                "x3": x3,
                "x4": x4,
                "x5": x5,
                "x6": x6,
                "is_daytime": is_daytime
            }

            # detector 실행
            raw, risk, level = detect_single(model, scaler, row_data)

            pred = 1 if level in ["alert", "emergency"] else 0

            # 🔥 핵심: 시간 기준 매칭
            feature_time = r.target_hour.replace(minute=0, second=0, microsecond=0)
            key = (resident_id, feature_time)

            level_gt = risk_map.get(key, "normal")

            if key in risk_map:
                matched += 1

            label = 1 if level_gt in ["alert", "emergency"] else 0

            all_preds.append(pred)
            all_labels.append(label)

            per_user_preds[resident_id].append(pred)
            per_user_labels[resident_id].append(label)

        # ------------------------
        # 6. 디버깅 출력
        # ------------------------
        print("\n===== 디버깅 =====")
        print("총 데이터:", len(all_labels))
        print("label=1 개수:", sum(all_labels))
        print("pred=1 개수:", sum(all_preds))
        print("매칭 개수:", matched)

        if sum(all_labels) == 0:
            print("❌ 라벨 전부 0 → 여전히 매칭 문제")
            return

        # ------------------------
        # 7. 전체 성능
        # ------------------------
        precision = precision_score(all_labels, all_preds, zero_division=0)
        recall = recall_score(all_labels, all_preds, zero_division=0)
        f1 = f1_score(all_labels, all_preds, zero_division=0)

        print("\n===== 전체 결과 =====")
        print(f"Precision: {precision:.4f}")
        print(f"Recall: {recall:.4f}")
        print(f"F1: {f1:.4f}")

        # ------------------------
        # 8. 사용자별 성능
        # ------------------------
        print("\n===== 사용자별 F1 =====")

        for rid in per_user_preds:
            if len(set(per_user_labels[rid])) < 2:
                continue

            f1_user = f1_score(per_user_labels[rid], per_user_preds[rid])
            print(f"Resident {rid}: F1={f1_user:.4f}")

        print("\n===== EVALUATION END =====\n")


# =========================
# 실행
# =========================

if __name__ == "__main__":
    try:
        asyncio.run(evaluate())
    except RuntimeError:
        pass