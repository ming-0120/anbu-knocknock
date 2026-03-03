# backend/app/services/scoring_service.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, TypedDict


class FeatureRow(TypedDict):
    feature_id: int
    resident_id: int
    target_date: date
    x1_motion_count: int
    x2_door_count: int
    x3_avg_interval: float
    x4_night_motion_count: int
    x5_first_motion_min: int


class RiskScoreRow(TypedDict):
    feature_id: int
    s_base: float
    score: float  # (= S_final)
    level: str
    reason_codes: Dict[str, Any]
    scored_at: datetime


def compute_scores_14d(
    training_rows: List[FeatureRow],
    target_rows: List[FeatureRow],
) -> List[RiskScoreRow]:
    """
    최근 14일(training_rows)로 학습하고,
    target_rows(보통 어제 날짜)만 점수 산출해 RiskScoreRow 리스트로 반환.

    여기에는 DB 코드/SQL이 절대 들어가면 안 됨.
    """
    raise NotImplementedError("Implement model scoring here")