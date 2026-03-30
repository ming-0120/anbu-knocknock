import random
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
# 본인의 프로젝트 구조에 맞게 Resident, ResidentSetting 모델을 임포트하세요
from app.db.database import SessionLocal, engine 
from app.models import Resident, ResidentSetting 

# 1. 질병별 가중치 설정
DISEASE_SCORES = {
    "HTN": 10, "DM": 15, "DEP": 25, "ALD": 20, "COPD": 15, "OTHER": 5
}

def calculate_weight(json_data):
    """JSON 데이터를 분석해 0.0 ~ 1.0 사이의 가중치를 반환"""
    score = 0
    diseases = json_data.get("health", {}).get("diseases", [])
    for d in diseases:
        score += DISEASE_SCORES.get(d, 0)
        
    outings = json_data.get("routine", {}).get("outings", [])
    if not outings:
        score += 40  # 활동 없음 가중치
    else:
        # 외출 빈도에 따른 차등 (주 5일 외출 시 점수 낮음)
        days_count = len(outings[0].get("days", []))
        score += max(0, (7 - days_count) * 5)
        
    return min(1.0, score / 100)

def run_seed():
    db = SessionLocal()
    try:
        # 1. 외래 키 체크 일시 해제 (Truncate를 위해 필요할 수 있음)
        db.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        
        # 2. MySQL용 Truncate 문법 (RESTART IDENTITY CASCADE 제거)
        db.execute(text("TRUNCATE TABLE resident_settings;"))
        
        # 3. 외래 키 체크 다시 설정
        db.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        
        db.commit()
        print("기존 데이터를 성공적으로 초기화했습니다.")

        # 3. 모든 입주민 불러오기
        residents = db.query(Resident).all()
        random.shuffle(residents)

        total = len(residents)
        high_risk_count = int(total * 0.2)

        for i, res in enumerate(residents):
            if i < high_risk_count:
                # --- 고위험군 (20%): 질병 있음, 외출 없음 ---
                diseases = [random.choice(["DEP", "ALD"])]
                outings = []
            else:
                # --- 저위험군 (80%): 경미한 질병 또는 건강, 정기 외출 ---
                diseases = random.sample(["HTN", "DM"], random.randint(0, 1))
                outings = [{
                    "type": "regular",
                    "label": "산책",
                    "days": random.sample(["MON", "TUE", "WED", "THU", "FRI"], 3),
                    "schedule": [{"start": "10:00", "end": "11:00"}]
                }]

            full_json = {
                "health": {"diseases": diseases},
                "routine": {"outings": outings}
            }
            
            weight = calculate_weight(full_json)

            # 4. 데이터 삽입
            new_setting = ResidentSetting(
                resident_id=res.resident_id,
                days_of_week=full_json,
                sensitivity_weight=weight
            )
            db.add(new_setting)

        db.commit()
        print(f"성공: {total}명 중 고위험 {high_risk_count}명 생성 완료.")

    except Exception as e:
        print(f"오류 발생: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    run_seed()