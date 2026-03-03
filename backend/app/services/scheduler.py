import joblib
import os
from datetime import datetime, timedelta
from app.db.database import SessionLocal
from app.models.sensor_event import SensorEvent
from app.models.risk_score import RiskScore
from sqlalchemy import func

MODEL_DIR = "app/ml/saved_models"

async def analyze_hourly_patterns():
    now = datetime.now()
    print(f"\n[{now.strftime('%Y-%m-%d %H:%M:%S')}] 🤖 AI 이상 탐지 스케줄러 가동 중...")
    
    db = SessionLocal()
    try:
        # 1. 최근 1시간 동안의 움직임 데이터 가져오기 (이전과 동일)
        one_hour_ago = now - timedelta(hours=1)
        hourly_stats = db.query(
            SensorEvent.sensor_id, 
            func.count(SensorEvent.event_id).label('motion_count')
        ).filter(
            SensorEvent.event_at >= one_hour_ago
        ).group_by(SensorEvent.sensor_id).all()

        scores_to_insert = []
        current_hour = now.hour
        current_day = now.weekday()

        # 2. 센서별로 AI 평가 진행
        for stat in hourly_stats:
            sensor_id = stat.sensor_id
            motion_count = stat.motion_count
            
            model_path = f"{MODEL_DIR}/model_sensor_{sensor_id}.pkl"
            
            # ----------------------------------------------------
            # 🚀 AI 모델 예측 로직
            # ----------------------------------------------------
            if os.path.exists(model_path):
                # 저장된 뇌(모델) 불러오기
                model = joblib.load(model_path)
                
                # AI에게 물어보기: "지금(이 시간, 이 요일) 움직임이 이 정도인데 정상이야?"
                # X_new 포맷: [[hour, day_of_week, motion_count]]
                prediction = model.predict([[current_hour, current_day, motion_count]])
                anomaly_score = model.decision_function([[current_hour, current_day, motion_count]])[0]
                
                # prediction 결과: 1(정상), -1(비정상)
                # anomaly_score: 음수일수록 비정상(위험)에 가까움. 이를 0~1 사이 점수로 변환 (공모전 시각화용)
                
                # 음수(-0.5 등)를 위험한 점수(0.9 등)로, 양수(0.1 등)를 안전한 점수(0.1 등)로 매핑
                calculated_score = 0.5 - (anomaly_score * 0.5) 
                
                # 🌟 DB ENUM 규격: 'normal', 'watch', 'alert', 'emergency'
            if prediction[0] == -1: 
                # AI가 이상하다고 판단했을 때: 'alert' (warning 대신 사용)
                risk_level = "alert"     
            elif calculated_score > 0.8:
                # 매우 높은 점수: 'emergency'
                risk_level = "emergency" 
            elif calculated_score > 0.6:
                # 중간 정도: 'watch'
                risk_level = "watch"     
            else:
                # 평온함: 'normal'
                risk_level = "normal"    
            
            # 공모전 어필용 빵빵한 JSON 데이터 (XAI: 설명가능한 AI 컨셉)
            reason_dict = {
                "algorithm": "IsolationForest",
                "ai_anomaly_score": round(anomaly_score, 4),
                "motion_count": motion_count,
                "hour": current_hour,
                "day_of_week": current_day
            }
            # NumPy 타입을 일반 파이썬 타입으로 변환 (에러 방지용)
            safe_score = float(calculated_score)

            scores_to_insert.append(
                RiskScore(
                    feature_id=sensor_id,
                    s_base=round(safe_score, 4),
                    score=round(safe_score, 4),
                    level=risk_level,  # 이제 ENUM에 있는 단어만 들어갑니다!
                    reason_codes=reason_dict,
                    scored_at=now
                )
            )

            # ----------------------------------------------------
            
        if scores_to_insert:
            db.bulk_save_objects(scores_to_insert)
            db.commit()
            print(f"✅ AI가 {len(scores_to_insert)}건의 데이터 분석을 완료하고 risk_scores에 저장했습니다.")

    except Exception as e:
        db.rollback()
        print(f"❌ 스케줄러(AI) 실행 중 에러 발생: {e}")
    finally:
        db.close()
        
if __name__ == "__main__":
    import asyncio
    print("🚀 스케줄러 수동 테스트 (AI 예측) 시작!")
    asyncio.run(analyze_hourly_patterns())