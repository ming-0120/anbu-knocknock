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


def disease_alpha(cfg) -> float:
    """
    cfg 예시:
    {
      "health": {"diseases": ["DM"]},
      "routine": {...}
    }

    - diseases: list[str] 질병 코드 목록
    - 질병이 여러 개면 가장 큰 가중치를 적용(또는 곱/합 등 정책 선택 가능)
    """
    if not isinstance(cfg, dict):
        return 1.0

    health = cfg.get("health")
    if not isinstance(health, dict):
        return 1.0

    diseases = health.get("diseases")
    if not isinstance(diseases, list):
        return 1.0

    # 빈 값/문자열 아닌 값 제거
    disease_codes = [x for x in diseases if isinstance(x, str) and x.strip()]
    if not disease_codes:
        return 1.0

    # 정책: 질병 코드별 alpha (예시는 임시값. 너 정책에 맞게 조정)
    ALPHA_BY_CODE = {
        "DM": 1.10,   # Diabetes Mellitus
        "HTN": 1.05,  # Hypertension
        "CVD": 1.08,
    }

    # 정책 1) 가장 큰 alpha 하나만 적용 (권장: 과도한 폭증 방지)
    alpha = 1.0
    for code in disease_codes:
        alpha = max(alpha, float(ALPHA_BY_CODE.get(code, 1.0)))

    return alpha