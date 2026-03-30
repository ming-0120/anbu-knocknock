import os, json, asyncio, joblib
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert
from app.db.database import AsyncSessionLocal
from app.models.hourly_feature import HourlyFeature
from app.models.resident_setting import ResidentSetting
from app.models.resident_baseline import ResidentBaseline
from app.models.risk_score import RiskScore

BASE_DIR = os.path.dirname(__file__)
MODEL_DIR = os.path.join(BASE_DIR, "saved_models")

HIGH_RISK_TARGETS = [164, 167, 204, 230, 260]

def calculate_asymptotic_score(intensity, sensitivity=1.0):    
    k = 50.0 * sensitivity
    # 점수 상한선을 0.95로 둔 점근적 수식
    score = 0.95 * (1 - np.exp(-k * max(0, intensity)))
    return round(float(score), 4)

def decide_level(risk_score):
    if risk_score >= 0.75: return "emergency"
    if risk_score >= 0.50: return "alert"
    if risk_score >= 0.25: return "watch"
    return "normal"

async def run_batch():
    async with AsyncSessionLocal() as db:
        print(f"🚀 [DETECTOR] 외출 스케줄 및 건강 가중치 반영 배치 시작")
        now = datetime.now()
        
        # 최근 2시간 내의 특징 데이터 추출
        rows = (await db.execute(
            select(HourlyFeature).where(HourlyFeature.target_hour >= now - timedelta(hours=2))
        )).scalars().all()

        if not rows:
            print("처리할 새로운 특징 데이터가 없습니다.")
            return

        # 글로벌 모델 로드
        g_m_path = os.path.join(MODEL_DIR, "global_standard_model.pkl")
        g_s_path = os.path.join(MODEL_DIR, "global_standard_scaler.pkl")
        global_model = joblib.load(g_m_path) if os.path.exists(g_m_path) else None
        global_scaler = joblib.load(g_s_path) if os.path.exists(g_s_path) else None

        for r in rows:
            # 개인별 모델/스케일러 경로 확인
            p_m_path = os.path.join(MODEL_DIR, f"resident_{r.resident_id}_model.pkl")
            p_s_path = os.path.join(MODEL_DIR, f"resident_{r.resident_id}_scaler.pkl")
            
            curr_model = joblib.load(p_m_path) if os.path.exists(p_m_path) else global_model
            curr_scaler = joblib.load(p_s_path) if os.path.exists(p_s_path) else global_scaler

            # 설정 및 베이스라인 로드
            setting = (await db.execute(
                select(ResidentSetting).where(ResidentSetting.resident_id == r.resident_id)
            )).scalar_one_or_none()
            
            baseline = (await db.execute(
                select(ResidentBaseline).where(ResidentBaseline.resident_id == r.resident_id)
            )).scalar_one_or_none()
            
            sensitivity = float(setting.sensitivity_weight or 1.0) if setting else 1.0
            w_baseline = 1.0
            health_weight = 1.0  # 기본 건강 가중치
            is_scheduled_outing = False # 외출 여부 플래그

            # --- [핵심] days_of_week 컬럼 파싱 및 로직 적용 ---
            if setting and setting.days_of_week:
                try:
                    # JSON 문자열이거나 dict일 경우 처리
                    conf = setting.days_of_week
                    if isinstance(conf, str):
                        conf = json.loads(conf)
                    
                    # 1. 건강 상태 확인 (질환이 있으면 가중치 상향)
                    diseases = conf.get("health", {}).get("diseases", [])
                    if diseases:
                        health_weight = 1.25 # 질환 보유 시 위험 민감도 25% 증가
                    
                    # 2. 외출 스케줄 확인
                    day_of_week = r.target_hour.strftime('%a').upper() # 'MON', 'FRI' 등
                    curr_time_str = r.target_hour.strftime('%H:%M')
                    
                    outings = conf.get("routine", {}).get("outings", [])
                    for outing in outings:
                        if day_of_week in outing.get("days", []):
                            for sched in outing.get("schedule", []):
                                if sched["start"] <= curr_time_str <= sched["end"]:
                                    is_scheduled_outing = True
                                    break
                except Exception as e:
                    print(f"⚠️ JSON 파싱 오류 (ID: {r.resident_id}): {e}")

            # 3. 모델 기반 원시 점수(raw_score) 계산
            raw_score = 0.0
            if curr_model and curr_scaler:
                df = pd.DataFrame([{
                    "x1_motion_count": float(r.x1_motion_count or 0),
                    "x2_door_count": float(r.x2_door_count or 0),
                    "x3_avg_interval": np.log1p(float(getattr(r, "x3_avg_interval", 0) or 0)),
                    "x4_night_motion_count": float(getattr(r, "x4_night_motion_count", 0) or 0),
                    "x5_first_motion_min": float(getattr(r, "x5_first_motion_min", 0) or 0),
                    "x6_last_motion_min": float(getattr(r, "x6_last_motion_min", 0) or 0),
                    "is_daytime": 1.0 if 6 <= r.target_hour.hour <= 22 else 0.0
                }])
                raw_score = float(curr_model.decision_function(curr_scaler.transform(df))[0])

            # 4. 베이스라인(평소 활동량) 대비 가중치
            if baseline and baseline.motion_mean > 0:
                user_avg_per_hour = baseline.motion_mean / 24.0
                current_x1 = float(r.x1_motion_count or 0)
                if current_x1 < user_avg_per_hour * 0.3: w_baseline = 2.5
                elif current_x1 < user_avg_per_hour * 0.7: w_baseline = 1.8

            # 5. 최종 위험 점수 확정
            if is_scheduled_outing:
                # [수정] 외출 중일 때는 활동이 없어도 무조건 정상
                risk_score = 0.0
                level = "normal"
            else:
                # [수정] 일반 상황: 건강 가중치(health_weight)를 적용하여 강도 계산
                # raw_score는 활동이 적을수록 마이너스 값이 커지므로 뺄셈으로 강도 조절
                final_intensity = (0.05 - (raw_score * w_baseline)) * health_weight
                risk_score = calculate_asymptotic_score(final_intensity, sensitivity=sensitivity)
                
                # 초고위험군 예외 처리
                if r.resident_id in HIGH_RISK_TARGETS:
                    risk_score = max(risk_score, 0.92)
                
                level = decide_level(risk_score)

            # 6. 결과 저장 (Upsert)
            reason_json = json.dumps({
                "mode": "personal" if os.path.exists(p_m_path) else "global",
                "is_outing": is_scheduled_outing,
                "health_boost": health_weight > 1.0,
                "raw_score": round(raw_score, 4),
                "w_baseline": w_baseline
            }, ensure_ascii=False)

            stmt = insert(RiskScore).values(
                resident_id=r.resident_id,
                feature_id=r.feature_id,
                s_base=raw_score,
                score=risk_score,
                level=level,
                reason_codes=reason_json,
                scored_at=now
            )
            
            await db.execute(stmt.on_duplicate_key_update(
                score=stmt.inserted.score,
                level=stmt.inserted.level,
                s_base=stmt.inserted.s_base,
                reason_codes=stmt.inserted.reason_codes,
                scored_at=stmt.inserted.scored_at
            ))

        await db.commit()
        print(f"✅ 배치 완료: {len(rows)}건 처리 (days_of_week 기반 스케줄 반영됨)")

if __name__ == "__main__":
    asyncio.run(run_batch())