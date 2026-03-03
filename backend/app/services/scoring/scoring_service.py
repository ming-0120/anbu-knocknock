from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, TypedDict


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
    score: float
    level: str
    reason_codes: Dict[str, Any]
    scored_at: datetime


def compute_scores_14d(
    training_rows: List[FeatureRow],
    target_rows: List[FeatureRow],
) -> List[RiskScoreRow]:
    raise NotImplementedError("Implement model scoring here")