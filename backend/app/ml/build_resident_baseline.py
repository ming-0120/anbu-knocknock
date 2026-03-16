import asyncio
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import select, delete, text
from app.db.database import AsyncSessionLocal
from app.models.daily_feature import DailyFeature
from app.models.resident_baseline import ResidentBaseline
from app.models.alert import Alert
from app.models.resident_setting import ResidentSetting

async def aggregate_hourly_to_daily(db):
    """시간별 데이터를 일별 데이터로 합산하는 전처리 단계"""
    print("Step 0: 시간별 데이터를 일별 데이터로 합산 중...")
    # 기존 일별 데이터 초기화
    await db.execute(delete(DailyFeature))
    
    # hourly_features를 일 단위로 그룹화하여 DailyFeature에 삽입
    await db.execute(text("""
        INSERT INTO daily_features (
            resident_id, target_date, x1_motion_count, x4_night_motion_count, 
            x5_first_motion_min, x6_last_motion_min, computed_at
        )
        SELECT 
            resident_id, 
            DATE(target_hour) as target_date,
            SUM(x1_motion_count),
            SUM(x4_night_motion_count),
            MIN(x5_first_motion_min),
            MAX(x6_last_motion_min),
            NOW()
        FROM hourly_features
        GROUP BY resident_id, DATE(target_hour)
    """))
    await db.flush()

async def main():
    async with AsyncSessionLocal() as db:
        # 1. 전처리: 일별 데이터 생성
        await aggregate_hourly_to_daily(db)
    
        # 2. ✨ 모든 주민의 민감도 가중치(sensitivity_weight) 가져오기
        settings_stmt = select(ResidentSetting.resident_id, ResidentSetting.sensitivity_weight)
        settings_result = await db.execute(settings_stmt)
        # {주민ID: 가중치} 형태의 딕셔너리로 변환 (기본값 1.0)
        weight_map = {row.resident_id: float(row.sensitivity_weight or 1.0) for row in settings_result.all()}

        # 3. DailyFeature 데이터 조회
        stmt = select(DailyFeature)
        rows = (await db.execute(stmt)).scalars().all()
        
        data = []
        for r in rows:
            x1 = float(r.x1_motion_count or 0)
            x4 = float(r.x4_night_motion_count or 0)
            activity_span = max(0, (r.x6_last_motion_min or 0) - (r.x5_first_motion_min or 0))
            data.append({
                "resident_id": r.resident_id,
                "motion": x1, "night_motion": x4, "activity_span": activity_span
            })

        if not data:
            print("❌ Error: 합산된 일별 데이터가 없습니다.")
            return

        df = pd.DataFrame(data)

        # 4. 그룹화 및 통계치 계산
        grouped = df.groupby("resident_id").agg(
            motion_mean=("motion","mean"), motion_std=("motion","std"),
            night_mean=("night_motion","mean"), night_std=("night_motion","std"),
            span_mean=("activity_span","mean"), span_std=("activity_span","std")
        ).reset_index()

        # 5. 기존 베이스라인 삭제 후 갱신
        await db.execute(delete(ResidentBaseline))

        objs = []
        for _, r in grouped.iterrows():
            rid = int(r.resident_id)
            
            # ✨ [핵심 수정] DB에서 가져온 개인별 가중치 적용
            # 가중치가 1.1, 1.2로 커질수록 sensitivity_factor는 0.9, 0.8로 작아짐
            user_weight = weight_map.get(rid, 1.0)
            sensitivity_factor = 1.0 / user_weight 
            
            objs.append(
                ResidentBaseline(
                    resident_id=rid,
                    motion_mean=float(r.motion_mean or 0),
                    # 표준편차에 가중치 반영: 범위가 좁아질수록 이상 탐지가 잘 됨
                    motion_std=max(1, float(r.motion_std or 1)) * sensitivity_factor,
                    night_mean=float(r.night_mean or 0),
                    night_std=max(1, float(r.night_std or 1)) * sensitivity_factor,
                    span_mean=float(r.span_mean or 0),
                    span_std=max(1, float(r.span_std or 1)) * sensitivity_factor
                )
            )

        db.add_all(objs)
        await db.commit()

    print(f"✅ Baseline updated with dynamic weights for {len(grouped)} residents.")

if __name__ == "__main__":
    asyncio.run(main())