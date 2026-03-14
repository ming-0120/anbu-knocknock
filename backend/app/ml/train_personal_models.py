import os
import asyncio
import joblib
import numpy as np
import pandas as pd
from sqlalchemy import select, text
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from app.db.database import AsyncSessionLocal
from app.models.hourly_feature import HourlyFeature

BASE_DIR = os.path.dirname(__file__)
MODEL_DIR = os.path.join(BASE_DIR, "saved_models")
os.makedirs(MODEL_DIR, exist_ok=True)

async def train_all():
    async with AsyncSessionLocal() as db:
        res = await db.execute(text("SELECT resident_id FROM residents"))
        residents = res.fetchall()
        
        count = 0
        for row in residents:
            rid = row[0]
            stmt = select(HourlyFeature).where(HourlyFeature.resident_id == rid)
            features = (await db.execute(stmt)).scalars().all()
            
            # 최소 72시간(3일) 이상의 데이터가 있어야 안정적인 패턴 학습 가능
            if len(features) < 72:
                continue
                
            data = []
            for f in features:
                # 1. 기본 3대장 지표 (활동량, 문열림, 리듬)
                x1 = float(f.x1_motion_count or 0)
                x2 = float(f.x2_door_count or 0)
                x3 = float(getattr(f, "x3_avg_interval", 0) or 0)
                
                # 2. 🔥 추가된 3대장 지표 (야간 움직임, 첫 움직임 시간, 마지막 움직임 시간)
                x4 = float(getattr(f, "x4_night_motion_count", 0) or 0)
                x5 = float(getattr(f, "x5_first_motion_min", 0) or 0)
                x6 = float(getattr(f, "x6_last_motion_min", 0) or 0)
                
                # 3. 🔥 낮/밤 인지 데이터
                hour = f.target_hour.hour
                is_daytime = 1.0 if 6 <= hour <= 22 else 0.0
                
                # 총 7개의 특징(Feature)으로 학습 데이터 구성
                data.append([x1, x2, np.log1p(x3), x4, x5, x6, is_daytime])
                
            # 컬럼명 7개로 확장
            columns = [
                "x1_motion_count", "x2_door_count", "x3_avg_interval", 
                "x4_night_motion_count", "x5_first_motion_min", "x6_last_motion_min", 
                "is_daytime"
            ]
            df = pd.DataFrame(data, columns=columns)
            
            # 데이터 스케일링 (정규화) - 단위가 다른 분(min)과 횟수(count)의 스케일을 맞춰줌
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(df)
            
            # IsolationForest 모델 훈련 (오염도 5% 기준)
            model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
            model.fit(X_scaled)
            
            # 개인별 모델과 스케일러를 pkl 파일로 저장
            joblib.dump(model, os.path.join(MODEL_DIR, f"resident_{rid}_model.pkl"))
            joblib.dump(scaler, os.path.join(MODEL_DIR, f"resident_{rid}_scaler.pkl"))
            count += 1
            
        print(f"✅ 총 {count}명의 개인 전용 모델(x1~x6 + is_daytime 탑재)이 갱신되었습니다.")

if __name__ == "__main__":
    asyncio.run(train_all())