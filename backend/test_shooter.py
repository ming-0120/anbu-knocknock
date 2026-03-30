import urllib.request
import json
import datetime

url = "http://localhost:8000/sensor-events"

print("🔫 100발 연사 테스트 시작! (기본 모듈 사용)")

for i in range(1, 101):
    # 1. 쏠 데이터 준비
    data = {
        "sensor_id": 1,
        "event_type": "motion",
        "event_value": 1.0,
        "event_at": datetime.datetime.now().isoformat()
    }
    
    # 2. 파이썬 딕셔너리를 JSON 문자열로 바꾸고 바이트 코드로 변환 (필수 작업)
    json_data = json.dumps(data).encode('utf-8')
    
    # 3. 우편봉투(Request) 세팅: 주소, 내용물, 그리고 "이거 JSON이야" 하고 이름표(헤더) 붙이기
    req = urllib.request.Request(url, data=json_data, headers={'Content-Type': 'application/json'})
    
    # 4. 발사!
    try:
        with urllib.request.urlopen(req) as response:
            pass # 쐈으면 응답은 굳이 안 읽고 바로 다음 발 준비
    except Exception as e:
        print(f"❌ {i}번째 발사 실패: {e}")

print("✅ 발사 완료! 워커 터미널을 확인하세요.")