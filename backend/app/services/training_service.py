# backend/app/services/training_service.py
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from app.services.scoring import FeatureRow

MODEL_PATH = os.getenv("MODEL_STATE_PATH", "model_weights/model_state.json")

def train_14d(training_rows: List[FeatureRow]) -> None:
    # TODO: 여기서 14일 데이터로 학습 파라미터 산출
    # 예: 평균/표준편차/베이스라인 등
    model_state: Dict[str, Any] = {
        "version": "v1",
        "trained_on_rows": len(training_rows),
    }

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    with open(MODEL_PATH, "w", encoding="utf-8") as f:
        json.dump(model_state, f, ensure_ascii=False)

def load_latest_model_state() -> Dict[str, Any]:
    if not os.path.exists(MODEL_PATH):
        # 학습 전이면 빈 상태 리턴(또는 예외)
        return {"version": "v1", "trained_on_rows": 0}

    with open(MODEL_PATH, "r", encoding="utf-8") as f:
        return json.load(f)