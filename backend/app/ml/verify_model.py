import joblib
import numpy as np

# 거주자 1번의 모델이 생성되었다고 가정
model_path = "app/ml/saved_models/model_resident_1.pkl"

try:
    model = joblib.load(model_path)
    
    # 가상의 상황 2개를 테스트합니다. (시간, 요일, 활동량)
    # [오후 2시(14), 화요일(1), 활동량 50회]
    test_normal = [[14, 1, 50]]
    # [오전 3시(3), 화요일(1), 활동량 100회] -> 새벽에 100회면 이상하겠죠?
    test_anomaly = [[3, 1, 100]]

    print(f"✅ 정상 예상 데이터 결과: {model.predict(test_normal)} (1이면 정상)")
    print(f"🚨 이상 예상 데이터 결과: {model.predict(test_anomaly)} (-1이면 비정상)")
    
    # 결정 점수 확인 (0보다 크면 정상, 작으면 이상치)
    print(f"📊 정상 데이터 점수: {model.decision_function(test_normal)}")
    print(f"📊 이상 데이터 점수: {model.decision_function(test_anomaly)}")

except Exception as e:
    print(f"❌ 검증 실패: {e}")