import random
from datetime import datetime, timedelta
from app.db.database import SessionLocal
from app.models.resident import Resident  # (가정) resident 테이블에 해당하는 모델

def generate_and_insert_residents(num_samples=100):
    print(f"👷‍♂️ 대상자(Resident) 더미 데이터 {num_samples}개 추가 생성을 시작합니다...")
    
    # 1. 이름 풀(Pool) 확대 (동명이인 최소화)
    last_names = ['김', '이', '박', '최', '정', '강', '조', '윤', '장', '임', '한', '오', '서', '신', '권', '황', '안', '송', '전', '홍']
    first_names = ['영수', '순자', '영호', '정순', '영철', '영자', '미경', '성호', '은주', '상훈', 
                   '지훈', '민지', '현우', '서연', '도윤', '하윤', '민수', '지우', '지아', '준호',
                   '건우', '수진', '동현', '승민', '예은', '우진', '지윤', '수아', '시우', '유진']
    
    start_date = datetime(2026, 2, 15)
    end_date = datetime(2026, 2, 25)
    
    # DB 세션을 먼저 엽니다 (기존 데이터 조회를 위해)
    db = SessionLocal()
    
    try:
        # 2. DB에 이미 존재하는 개인정보 목록을 Set으로 가져옴 (조회 속도 최적화)
        existing_reg_nos = {r[0] for r in db.query(Resident.resident_reg_no).all()}
        existing_phones = {r[0] for r in db.query(Resident.phone).all()}
        
        residents_to_insert = []
        
        for _ in range(num_samples):
            # 3. 중복되지 않는 정보가 나올 때까지 무한 루프
            while True:
                name = random.choice(last_names) + random.choice(first_names)
                
                # 주민등록번호 생성 로직
                if random.random() < 0.1: # 10% 확률로 2000년대생
                    year = random.randint(0, 5)
                    gender_code = random.choice([3, 4])
                else: # 90% 확률로 고령층
                    year = random.randint(40, 69)
                    gender_code = random.choice([1, 2])
                    
                month = random.randint(1, 12)
                day = random.randint(1, 28)
                reg_no = f"{year:02d}{month:02d}{day:02d}-{gender_code}"
                
                # 전화번호 생성 로직
                phone = f"010-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"
                
                # 중복 검사: DB 데이터는 물론 이번 루프에서 방금 생성한 데이터와도 겹치지 않는지 확인
                if reg_no not in existing_reg_nos and phone not in existing_phones:
                    # 통과하면 Set에 추가하여 다음 번호가 이것과 겹치지 않게 방지
                    existing_reg_nos.add(reg_no)
                    existing_phones.add(phone)
                    break # 고유한 값 확인 완료, while 루프 탈출
            
            gu_list = ['강남구', '서초구', '송파구', '관악구', '동작구', '은평구', '마포구']
            address_main = f"서울특별시 {random.choice(gu_list)} 가짜도로명 {random.randint(1, 100)}길"
            zip_code = f"{random.randint(10000, 99999)}"
            address_detail = f"{random.randint(1, 10)}동 {random.randint(101, 1502)}호"
            
            time_between = end_date - start_date
            random_days = random.randrange(time_between.days)
            created_at = start_date + timedelta(days=random_days, hours=random.randint(9, 18))
            
            lat = round(random.uniform(37.4, 37.7), 6)
            lon = round(random.uniform(126.8, 127.1), 6)
            
            # ORM 모델 객체 생성
            resident = Resident(
                name=name,
                resident_reg_no=reg_no,
                phone=phone,
                address_main=address_main,
                zip_code=zip_code,
                address_detail=address_detail,
                created_at=created_at,
                lat=lat,
                lon=lon,
                profile_image_url=None
            )
            residents_to_insert.append(resident)

        # 일괄 삽입(Bulk Insert) 진행
        db.add_all(residents_to_insert)
        db.commit()
        print(f"✅ 성공적으로 {num_samples}명의 고유 데이터가 추가로 DB에 저장되었습니다!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ 데이터 삽입 중 오류가 발생했습니다: {e}")
    finally:
        db.close()

# 스크립트 직접 실행 시 작동 (100명으로 수정)
if __name__ == "__main__":
    generate_and_insert_residents(100)