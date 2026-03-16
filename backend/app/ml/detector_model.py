import os
import json
import asyncio
import joblib
import numpy as np
import pandas as pd

from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.dialects.mysql import insert

from app.db.database import AsyncSessionLocal
from app.models.hourly_feature import HourlyFeature
from app.models.resident_setting import ResidentSetting
from app.models.resident_baseline import ResidentBaseline
from app.models.risk_score import RiskScore
from app.models.alert import Alert


BASE_DIR = os.path.dirname(__file__)
MODEL_DIR = os.path.join(BASE_DIR, "saved_models")


DAY_MAP = {
    "MON":0,"TUE":1,"WED":2,"THU":3,
    "FRI":4,"SAT":5,"SUN":6
}


def get_disease_weight(diseases):
    if not diseases:
        return 1.0
    if "DM" in diseases:
        return 1.15
    if "HTN" in diseases:
        return 1.1
    return 1.0


def is_outing_time(routine, now):
    if not routine:
        return False
    weekday = now.weekday()
    now_time = now.strftime("%H:%M")
    for o in routine.get("outings", []):
        days = [DAY_MAP.get(d, -1) for d in o.get("days", [])]
        if weekday not in days:
            continue
        for s in o.get("schedule", []):
            if s["start"] <= now_time <= s["end"]:
                return True
    return False

# ✨ [수정] 95% 상한선 점근선 보정 함수 추가
def calculate_asymptotic_score(anomaly_intensity, sensitivity=1.0):
    """
    anomaly_intensity: 값이 클수록 위험 (0.05 - 최종 anomaly 점수)
    k: 감도 조절 상수. 8.0을 기준으로 알람이 잦으면 낮추고, 안 울리면 높이세요.
    """
    MAX_CAP = 0.95  # 상한선 95%
    k = 25.0 * sensitivity 
    
    # 지수 함수를 이용해 0.95에 수렴하게 만듦
    score = MAX_CAP * (1 - np.exp(-k * max(0, anomaly_intensity)))
    
    return round(float(score), 4)

def decide_level(risk_score):
    if risk_score >= 0.75: # 80 -> 75 (Emergency)
        return "emergency"
    if risk_score >= 0.50: # 60 -> 50 (Alert)
        return "alert"
    if risk_score >= 0.25: # 40 -> 25 (Watch)
        return "watch"
    return "normal"


def generate_summary(level, outing, has_model):
    if level == "emergency":
        if outing:
            return "외출 시간 활동 이상"
        if not has_model:
            return "활동 급감 (Baseline 기반)"
        return "개인 패턴 대비 활동 급감"
    if level == "alert":
        if outing:
            return "외출 패턴 변화 감지"
        if not has_model:
            return "활동 감소 (Baseline 기반)"
        return "개인 패턴 대비 활동 감소"
    return "정상 패턴"


async def run_batch():
    async with AsyncSessionLocal() as db:
        print("\n========== DETECTOR START (95% ASYMPTOTIC MODEL) ==========\n")
        
        now = datetime.now()
        cutoff = now - timedelta(hours=2)

        stmt = select(HourlyFeature).where(HourlyFeature.target_hour >= cutoff)
        rows = (await db.execute(stmt)).scalars().all()

        if not rows:
            print("no hourly data")
            return

        print("Target rows to detect:", len(rows))
        records = []

        for r in rows:
            resident_id = r.resident_id

            setting = (await db.execute(
                select(ResidentSetting).where(ResidentSetting.resident_id == resident_id)
            )).scalar_one_or_none()

            baseline = (await db.execute(
                select(ResidentBaseline).where(ResidentBaseline.resident_id == resident_id)
            )).scalar_one_or_none()

            sensitivity = 1.0
            alpha = 1.0
            w_outing = 1.0
            w_baseline = 1.0
            outing_now = False

            if setting:
                sensitivity = float(setting.sensitivity_weight or 1.0)
                if setting.days_of_week:
                    profile = setting.days_of_week
                    diseases = profile.get("health", {}).get("diseases", [])
                    routine = profile.get("routine", {})
                    
                    alpha = get_disease_weight(diseases)
                    outing_now = is_outing_time(routine, now)
                    
                    if outing_now and (r.x1_motion_count or 0) < 3:
                        w_outing = 0.3

            model_path = os.path.join(MODEL_DIR, f"resident_{resident_id}_model.pkl")
            scaler_path = os.path.join(MODEL_DIR, f"resident_{resident_id}_scaler.pkl")
            
            has_model = os.path.exists(model_path) and os.path.exists(scaler_path)
            raw_score = 0.0

            x1 = float(r.x1_motion_count or 0)
            x2 = float(r.x2_door_count or 0)
            x3 = float(getattr(r, "x3_avg_interval", 0) or 0)
            x4 = float(getattr(r, "x4_night_motion_count", 0) or 0)
            x5 = float(getattr(r, "x5_first_motion_min", 0) or 0)
            x6 = float(getattr(r, "x6_last_motion_min", 0) or 0)
            
            hour = r.target_hour.hour
            is_daytime = 1.0 if 6 <= hour <= 22 else 0.0

            if has_model:
                try:
                    model = joblib.load(model_path)
                    scaler = joblib.load(scaler_path)

                    df = pd.DataFrame([{
                        "x1_motion_count": x1,
                        "x2_door_count": x2,
                        "x3_avg_interval": np.log1p(x3),
                        "x4_night_motion_count": x4,
                        "x5_first_motion_min": x5,
                        "x6_last_motion_min": x6,
                        "is_daytime": is_daytime
                    }])

                    X = scaler.transform(df)
                    raw_score = float(model.decision_function(X)[0])

                except Exception as e:
                    print("model error:", resident_id, e)
                    has_model = False

            if baseline and baseline.motion_mean > 0:
                expected = baseline.motion_mean / 24.0
                if x1 >= expected * 0.7:
                    w_baseline = 0.4
                elif x1 < expected * 0.3:
                    w_baseline = 1.5
                elif x1 < expected * 0.7:
                    w_baseline = 1.2

            if has_model:
                if w_baseline == 1.5 and raw_score > -0.05:
                    raw_score = -0.07
                elif w_baseline == 1.2 and raw_score > -0.05:
                    raw_score = -0.06
                elif w_baseline == 0.4 and raw_score < 0:
                    raw_score = 0.05
            else:
                if w_baseline == 1.5:
                    raw_score = -0.10
                elif w_baseline == 1.2:
                    raw_score = -0.06
                else:
                    raw_score = 0.05

            anomaly = raw_score * alpha * sensitivity * w_outing * w_baseline

            records.append({
                "resident_id":resident_id,
                "feature_id":r.feature_id,
                "score":anomaly,
                "raw_score":raw_score,
                "outing":outing_now,
                "has_model":has_model,
                "sensitivity": sensitivity
            })

        # ✨ [수정] 상대평가(Min-Max) 로직 제거 및 절대평가 점근선 방식 적용
        for rec in records:            
            # 위험 강도 계산: 모델 점수가 낮을수록(임계값 0.05 기준) 위험 강도가 높아짐
            intensity = 0.05 - rec["score"]
            
            # 절대평가 기반 95% 상한선 점수 도출
            risk_score = calculate_asymptotic_score(intensity, sensitivity=rec["sensitivity"])
            
            level = decide_level(risk_score)
            summary = generate_summary(level, rec["outing"], rec["has_model"])

            reason_codes_dict = {
                "mode": "personal_asymptotic_detector",
                "summary": summary,
                "raw_score": rec["raw_score"],
                "final_anomaly": rec["score"],
                "normalized_score": float(risk_score),
                "outing": rec["outing"],
                "has_model": rec["has_model"]
            }
            reason_codes_json = json.dumps(reason_codes_dict, ensure_ascii=False)

            insert_stmt = insert(RiskScore).values(
                resident_id=rec["resident_id"],
                feature_id=rec["feature_id"],
                s_base=rec["raw_score"],
                score=float(risk_score),
                level=level,
                reason_codes=reason_codes_json,
                scored_at=now
            )

            upsert = insert_stmt.on_duplicate_key_update(
                s_base=insert_stmt.inserted.s_base,
                score=insert_stmt.inserted.score,
                level=insert_stmt.inserted.level,
                reason_codes=insert_stmt.inserted.reason_codes,
                scored_at=insert_stmt.inserted.scored_at
            )

            await db.execute(upsert)

            risk_id = (await db.execute(
                select(RiskScore.risk_id).where(
                    RiskScore.feature_id == rec["feature_id"]
                )
            )).scalar_one()

            if level in ["alert","emergency"]:
                exist = (await db.execute(
                    select(Alert.alert_id).where(Alert.risk_id == risk_id)
                )).scalar_one_or_none()

                if not exist:
                    await db.execute(
                        insert(Alert).values(
                            resident_id=rec["resident_id"],
                            risk_id=risk_id,
                            operators_id=1,
                            status="open",
                            summary=summary,
                            created_at=now
                        )
                    )
                else:
                    await db.execute(
                        update(Alert)
                        .where(Alert.risk_id == risk_id)
                        .values(summary=summary)
                    )

        await db.commit()
        print("detector finished (asymptotic score applied)")

async def main():
    await run_batch()

if __name__ == "__main__":
    asyncio.run(main())