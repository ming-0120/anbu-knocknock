# app/db/base.py
from app.db.session import Base  # Base 가져오기
from app.models.sensor_event import SensorEvent  # 모든 모델들 나열
# 다른 모델이 있다면 여기에 추가: from app.models.resident import Resident