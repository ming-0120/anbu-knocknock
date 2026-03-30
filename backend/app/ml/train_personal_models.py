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
        # 1. 전체 거주자 ID 조회
        res = await db.execute(text("SELECT resident_id FROM residents"))
        residents = res.fetchall()
        
        count = 0
        columns = [
            "x1_motion_count", "x2_door_count", "x3_avg_interval", 
            "x4_night_motion_count", "x5_first_motion_min", "x6_last_motion_min", 
            "is_daytime"
        ]

        for row in residents:
            rid = row[0]
            stmt = select(HourlyFeature).where(HourlyFeature.resident_id == rid)
            features = (await db.execute(stmt)).scalars().all()
            
            # 최소 72시간(3일) 이상의 데이터가 있어야 패턴 학습 가능
            if len(features) < 72:
                continue
                
            data = []
            for f in features:
                x1 = float(f.x1_motion_count or 0)
                x2 = float(f.x2_door_count or 0)
                x3 = float(getattr(f, "x3_avg_interval", 0) or 0)
                x4 = float(getattr(f, "x4_night_motion_count", 0) or 0)
                x5 = float(getattr(f, "x5_first_motion_min", 0) or 0)
                x6 = float(getattr(f, "x6_last_motion_min", 0) or 0)
                
                # 낮/밤 구분 (06시~22시: 낮)
                hour = f.target_hour.hour
                is_daytime = 1.0 if 6 <= hour <= 22 else 0.0
                
                # 데이터 구성 (x3은 로그 변환으로 스케일 안정화)
                data.append([x1, x2, np.log1p(x3), x4, x5, x6, is_daytime])
            
            df = pd.DataFrame(data, columns=columns)
            
            # 2. 스케일링 및 모델 훈련
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(df)
            
            model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
            model.fit(X_scaled)
            
            # 3. 개인별 파일 저장
            joblib.dump(model, os.path.join(MODEL_DIR, f"resident_{rid}_model.pkl"))
            joblib.dump(scaler, os.path.join(MODEL_DIR, f"resident_{rid}_scaler.pkl"))
            count += 1
            
        print(f"✅ 총 {count}명의 개인 전용 모델(7 Features)이 갱신되었습니다.")

if __name__ == "__main__":
    asyncio.run(train_all())