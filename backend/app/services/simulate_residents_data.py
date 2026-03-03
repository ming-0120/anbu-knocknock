import pandas as pd
from datetime import datetime, timedelta
import random

START_DATE = datetime(2026, 2, 10, 0, 0, 0)
END_DATE = datetime(2026, 2, 26, 23, 59, 59)
TOTAL_RESIDENTS = 29

events = []

def add_event(device_id, event_type, current_time):
    microsecond = random.randint(0, 999999)
    event_time = current_time.replace(microsecond=microsecond)
    events.append({
        'device_id': device_id,
        'event_type': event_type,
        'event_value': 1.0,
        'event_at': event_time.strftime('%Y-%m-%d %H:%M:%S.%f')
    })

def simulate_door_activity(door_id, time_obj):
    # 문 열림 발생 후 5~15초 뒤 문 닫힘
    add_event(door_id, 'door_open', time_obj)
    add_event(door_id, 'door_close', time_obj + timedelta(seconds=random.randint(5, 15)))

current_day = START_DATE
while current_day <= END_DATE:
    is_weekend = current_day.weekday() >= 5

    for resident_id in range(1, TOTAL_RESIDENTS + 1):
        motion_id = resident_id * 2 - 1
        door_id = resident_id * 2
        
        # --- [고의적 이상(Anomaly) 주입] ---
        # 8번 환자: 2월 22일 이후 집 안에서 쓰러짐 (문 열림 없음, 모션 없음)
        if resident_id == 8 and current_day >= datetime(2026, 2, 22):
            continue 
        # 16번 환자: 2월 20일 외출 후 미귀가 (외출 후 영구적인 센서 무반응)
        if resident_id == 16 and current_day >= datetime(2026, 2, 20):
            if current_day == datetime(2026, 2, 20):
                simulate_door_activity(door_id, current_day + timedelta(hours=10)) # 오전 10시 외출
            continue

        # --- [그룹 1: 직장인 패턴 (1~10번)] ---
        if 1 <= resident_id <= 10:
            if not is_weekend: # 평일 출퇴근
                # 아침 기상 및 출근 준비
                wake_time = current_day + timedelta(hours=7, minutes=random.randint(0, 30))
                for _ in range(random.randint(5, 10)):
                    add_event(motion_id, 'motion', wake_time + timedelta(minutes=random.randint(0, 60)))
                
                # 08:30 ~ 09:00 출근
                go_out = current_day + timedelta(hours=8, minutes=random.randint(30, 59))
                simulate_door_activity(door_id, go_out)
                
                # 18:00 ~ 19:00 퇴근
                come_home = current_day + timedelta(hours=18, minutes=random.randint(0, 59))
                simulate_door_activity(door_id, come_home)
                
                # 저녁 활동
                for _ in range(random.randint(15, 30)):
                    add_event(motion_id, 'motion', come_home + timedelta(minutes=random.randint(10, 240)))
            else: # 주말
                # 주말 기상
                wake_time = current_day + timedelta(hours=9, minutes=random.randint(0, 59))
                for _ in range(random.randint(10, 20)):
                    add_event(motion_id, 'motion', wake_time + timedelta(minutes=random.randint(0, 120)))
                
                # 종교 활동자 (2, 4, 7, 10번)의 외출
                if resident_id in [2, 4, 7, 10]:
                    rel_out = current_day + timedelta(hours=9, minutes=random.randint(30, 59))
                    simulate_door_activity(door_id, rel_out)
                    rel_in = current_day + timedelta(hours=12, minutes=random.randint(0, 30))
                    simulate_door_activity(door_id, rel_in)

        # --- [그룹 2: 자택 위주 어르신 (11~20번)] ---
        elif 11 <= resident_id <= 20:
            # 새벽 5~6시 기상
            wake_time = current_day + timedelta(hours=random.randint(5, 6), minutes=random.randint(0, 59))
            
            # 하루 종일 간헐적인 활동 (거동 불편 등 고려하여 빈도를 낮춤)
            for _ in range(random.randint(20, 40)):
                add_event(motion_id, 'motion', wake_time + timedelta(minutes=random.randint(0, 840))) # 낮 14시간 동안
                
            # 가벼운 산책/장보기 (하루 1회 정도)
            if random.random() > 0.3: # 70% 확률로 외출
                out_time = current_day + timedelta(hours=random.randint(14, 16))
                simulate_door_activity(door_id, out_time)
                simulate_door_activity(door_id, out_time + timedelta(minutes=random.randint(30, 90)))

            # 수면제/우울증약 복용 환자 (19번) - 야간 뒤척임(모션) 아예 없음
            if resident_id != 19:
                for _ in range(random.randint(1, 3)): # 야간 화장실 등
                    add_event(motion_id, 'motion', current_day + timedelta(hours=random.randint(2, 4)))

        # --- [그룹 3: 야간 근무 및 특이 패턴 (21~29번)] ---
        else:
            # 오후 14시 출근 (21번)
            if resident_id == 21 and not is_weekend:
                go_out = current_day + timedelta(hours=13, minutes=random.randint(30, 59))
                simulate_door_activity(door_id, go_out)
                come_home = current_day + timedelta(hours=23, minutes=random.randint(30, 59))
                simulate_door_activity(door_id, come_home)
            else:
                # 불규칙한 활동
                wake_time = current_day + timedelta(hours=random.randint(8, 11))
                for _ in range(random.randint(15, 35)):
                    add_event(motion_id, 'motion', wake_time + timedelta(minutes=random.randint(0, 600)))

    current_day += timedelta(days=1)

df = pd.DataFrame(events)
df['event_at'] = pd.to_datetime(df['event_at'])
df = df.sort_values(by='event_at').reset_index(drop=True)
df.to_csv('sensor_events_advanced.csv', index=False)
print(f"✅ 총 {len(df)}건의 정교한 시계열 데이터가 생성되었습니다.")