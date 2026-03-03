# app/services/risk_hybrid_utils.py
import json
from datetime import datetime
from typing import Any, Dict, Tuple

WEEKDAY_MAP = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}

# 질병 룰(예시)
DISEASE_RULES = {"ALD": 5, "DEP": 4, "HTN": 2, "DM": 3, "COPD": 4, "OTHER": 3}

LEVEL_SCORE01 = {"normal": 0.20, "watch": 0.50, "alert": 0.75, "emergency": 0.95}


def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def parse_config(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return {}


def time_in_range(start_hhmm: str, end_hhmm: str, now_time) -> bool:
    """자정 넘어가는 일정(23:00~02:00) 처리"""
    start = datetime.strptime(start_hhmm, "%H:%M").time()
    end = datetime.strptime(end_hhmm, "%H:%M").time()
    if start <= end:
        return start <= now_time <= end
    return (now_time >= start) or (now_time <= end)


def is_on_outing(days_of_week_json: Dict[str, Any], now: datetime) -> Tuple[bool, str]:
    """
    JSON 예:
    {"routine":{"outings":[{"days":["TUE"],"label":"산책","schedule":[{"start":"10:00","end":"11:00"}]}]}}
    """
    day_str = WEEKDAY_MAP[now.weekday()]
    cur_time = now.time()

    outings = (days_of_week_json.get("routine") or {}).get("outings") or []
    for o in outings:
        if day_str not in (o.get("days") or []):
            continue
        for sch in (o.get("schedule") or []):
            s = sch.get("start")
            e = sch.get("end")
            if not s or not e:
                continue
            if time_in_range(s, e, cur_time):
                return True, o.get("label", "outing")
    return False, ""


def disease_alpha(days_of_week_json: Dict[str, Any]) -> float:
    d_score = 0
    for d in (days_of_week_json.get("health") or {}).get("diseases") or []:
        if d.get("is_active"):
            d_score += DISEASE_RULES.get(d.get("code"), 3)
    # 점수당 5% 증폭(예시)
    return 1.0 + (d_score * 0.05)