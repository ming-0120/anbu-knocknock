import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.models.daily_feature import DailyFeature

MODEL_DIR = Path("app/ml/saved_models")

# ===== 설정 =====
RESIDENT_ID = 5
LIMIT_DAYS = 30
SYNTH_TOTAL = 200
SYNTH_RISK_RATIO = 0.20
RANDOM_SEED = 42

# 목표 분포(quantile) 기반 컷 강제 보정 옵션
AUTO_CALIBRATE_CUTOFFS = True
# True: p01/p03/p10 전부 재보정(각각 1%,3%,10%)
# False: p10만 재보정(Watch 비율만 맞추고, Alert/Emergency는 meta 그대로)
CALIBRATE_ALL = False
# ==============

LEVELS = ["normal", "watch", "alert", "emergency"]
LEVEL_TO_RANK = {"normal": 0, "watch": 1, "alert": 2, "emergency": 3}


def _load_artifacts(resident_id: int):
    model_path = MODEL_DIR / f"model_{resident_id}.pkl"
    scaler_path = MODEL_DIR / f"scaler_{resident_id}.pkl"
    meta_path = MODEL_DIR / f"meta_{resident_id}.json"

    if not model_path.exists():
        raise FileNotFoundError(f"missing: {model_path}")
    if not scaler_path.exists():
        raise FileNotFoundError(f"missing: {scaler_path}")
    if not meta_path.exists():
        raise FileNotFoundError(f"missing: {meta_path}")

    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return model, scaler, meta


def _dig(meta: Dict[str, Any], path: List[str]) -> Optional[Any]:
    cur: Any = meta
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _get_cut(meta: Dict[str, Any], key: str) -> float:
    """
    key: 'score_p01'/'score_p03'/'score_p10' 등
    1) meta 최상위
    2) meta['cutoffs'][key]
    3) meta['quantiles']에서 p01/p03/p10 대응
    """
    if key in meta:
        return float(meta[key])

    v = _dig(meta, ["cutoffs", key])
    if v is not None:
        return float(v)

    # quantiles fallback
    qmap = {
        "score_p01": ["quantiles", "p01"],
        "score_p03": ["quantiles", "p03"],
        "score_p05": ["quantiles", "p05"],
        "score_p10": ["quantiles", "p10"],
        "score_p20": ["quantiles", "p20"],
        "score_p50": ["quantiles", "p50"],
        "score_p95": ["quantiles", "p95"],
        "score_p99": ["quantiles", "p99"],
    }
    qp = qmap.get(key)
    if qp is not None:
        v2 = _dig(meta, qp)
        if v2 is not None:
            return float(v2)

    raise KeyError(key)


def _daily_to_x1x6(f: DailyFeature) -> Dict[str, float]:
    return {
        "x1": float(f.x1_motion_count),
        "x2": float(f.x2_door_count),
        "x3": float(f.x3_avg_interval),
        "x4": float(f.x4_night_motion_count),
        "x5": float(f.x5_first_motion_min),
        "x6": float(f.x6_last_motion_min),
    }


def _preprocess_df(df: pd.DataFrame, meta: Dict[str, Any]) -> pd.DataFrame:
    df = df.replace([np.inf, -np.inf], np.nan).fillna(0)

    pp = meta.get("preprocess", {})
    clip_cfg = pp.get("clip", {})
    tf_cfg = pp.get("transform", {})

    # clip (None-safe)
    for k, bounds in clip_cfg.items():
        if k in df.columns and isinstance(bounds, (list, tuple)) and len(bounds) == 2:
            lo, hi = bounds
            lo_f = float(lo) if lo is not None else None
            hi_f = float(hi) if hi is not None else None
            df[k] = df[k].clip(lo_f, hi_f)

    # transform
    for k, t in tf_cfg.items():
        if k in df.columns and t == "log1p":
            df[k] = np.log1p(df[k].astype(float))

    return df


def _raw_scores(model, scaler, meta: Dict[str, Any], rows: List[Dict[str, float]]) -> np.ndarray:
    cols = meta.get("feature_cols", ["x1", "x2", "x3", "x4", "x5", "x6"])
    df = pd.DataFrame(rows, columns=cols)
    df = _preprocess_df(df, meta)
    X = scaler.transform(df)
    return model.decision_function(X)


def _level_from_quantiles(raw_score: float, p01: float, p03: float, p10: float) -> str:
    if raw_score < p01:
        return "emergency"
    if raw_score < p03:
        return "alert"
    if raw_score < p10:
        return "watch"
    return "normal"


def _summarize_levels(levels: List[str]) -> Dict[str, Any]:
    n = len(levels)
    counts = {k: 0 for k in LEVELS}
    for lv in levels:
        counts[lv] = counts.get(lv, 0) + 1

    ratios = {}
    for k in LEVELS:
        ratios[k] = (counts[k] / n) * 100.0 if n > 0 else 0.0

    return {"n": n, "counts": counts, "ratios_percent": ratios}


def _expected_counts_from_quantiles(n: int) -> Dict[str, float]:
    return {
        "emergency": n * 0.01,
        "alert": n * 0.02,
        "watch": n * 0.07,
        "normal": n * 0.90,
    }


def _print_dist_check(tag: str, p01: float, p03: float, p10: float, raw_scores: np.ndarray, levels: List[str]) -> None:
    print("\n" + "=" * 100)
    print(f"[1) 훈련/실데이터 재투입 검증] {tag}")
    print(f"cutoffs: p01={p01} p03={p03} p10={p10}")
    print(
        f"raw_score stats: min={float(np.min(raw_scores)):.6f} max={float(np.max(raw_scores)):.6f} "
        f"mean={float(np.mean(raw_scores)):.6f} std={float(np.std(raw_scores)):.6f}"
    )

    summary = _summarize_levels(levels)
    exp = _expected_counts_from_quantiles(summary["n"])

    print(f"n={summary['n']}")
    print("counts =", summary["counts"])
    print("ratios(%) =", {k: round(v, 2) for k, v in summary["ratios_percent"].items()})

    diffs = {}
    for k in LEVELS:
        diffs[k] = summary["counts"][k] - exp[k]
    print("expected_counts (n*{0.90,0.07,0.02,0.01}) =", {k: round(v, 2) for k, v in exp.items()})
    print("diff(observed-expected) =", {k: round(v, 2) for k, v in diffs.items()})


@dataclass
class SynthSample:
    x: Dict[str, float]
    y_true: int  # 0=정상, 1=위험


def _bootstrap_normal_from_db(rows: List[Dict[str, float]], rng: np.random.Generator) -> Dict[str, float]:
    base = rows[int(rng.integers(0, len(rows)))]
    x = dict(base)

    for k in ["x1", "x2", "x4"]:
        v = float(x[k])
        noise = rng.normal(0.0, max(1.0, 0.15 * max(v, 1.0)))
        x[k] = max(0.0, v + noise)

    for k in ["x3", "x5", "x6"]:
        v = float(x[k])
        noise = rng.normal(0.0, 0.10 * max(v, 10.0))
        x[k] = float(np.clip(v + noise, 0.0, 1440.0))
    x["x6"] = float(np.clip(x["x6"], 0.0, 719.0))
    return x


def _make_risky_from_normal(x: Dict[str, float], rng: np.random.Generator, mode: str) -> Dict[str, float]:
    y = dict(x)

    if mode == "inactive_long":
        y["x1"] = max(0.0, y["x1"] * 0.05)
        y["x2"] = max(0.0, y["x2"] * 0.10)
        y["x4"] = max(0.0, y["x4"] * 0.05)
        y["x3"] = float(np.clip(y["x3"] * 4.0, 0.0, 1440.0))
        y["x5"] = float(np.clip(y["x5"] + 300.0, 0.0, 1440.0))
        y["x6"] = float(np.clip(max(y["x6"], 500.0) + rng.uniform(80.0, 200.0), 0.0, 719.0))

    elif mode == "night_activity_weird":
        y["x4"] = y["x4"] + rng.uniform(30.0, 120.0)
        y["x3"] = float(np.clip(y["x3"] * rng.uniform(0.2, 0.6), 0.0, 1440.0))
        y["x6"] = float(np.clip(y["x6"] + rng.uniform(100.0, 300.0), 0.0, 719.0))

    elif mode == "door_anomaly":
        if rng.random() < 0.5:
            y["x2"] = 0.0
        else:
            y["x2"] = y["x2"] + rng.uniform(15.0, 50.0)
        y["x1"] = max(0.0, y["x1"] * rng.uniform(0.3, 0.8))
        y["x6"] = float(np.clip(y["x6"] + rng.uniform(150.0, 350.0), 0.0, 719.0))

    elif mode == "rule_gate_emergency":
        y["x1"] = 0.0
        y["x2"] = 0.0
        y["x4"] = 0.0
        y["x3"] = float(np.clip(y["x3"] * 6.0, 0.0, 1440.0))
        y["x5"] = float(np.clip(y["x5"] + 400.0, 0.0, 1440.0))
        y["x6"] = float(np.clip(720.0 + rng.uniform(0.0, 600.0), 720.0, 1440.0))

    else:
        return _make_risky_from_normal(y, rng, "inactive_long")

    y["x1"] = float(max(0.0, y["x1"]))
    y["x2"] = float(max(0.0, y["x2"]))
    y["x3"] = float(np.clip(y["x3"], 0.0, 1440.0))
    y["x4"] = float(max(0.0, y["x4"]))
    y["x5"] = float(np.clip(y["x5"], 0.0, 1440.0))
    y["x6"] = float(np.clip(y["x6"], 0.0, 1440.0))
    return y


def _level_for_eval(raw_score: float, p01: float, p03: float, p10: float, x6: float) -> str:
    if x6 >= 720.0:
        return "emergency"
    return _level_from_quantiles(raw_score, p01, p03, p10)


def _confusion_and_metrics(y_true: List[int], y_pred: List[int]) -> Dict[str, Any]:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)

    denom_p = tp + fp
    precision = tp / denom_p if denom_p > 0 else 0.0

    denom_r = tp + fn
    recall = tp / denom_r if denom_r > 0 else 0.0

    denom_f1 = precision + recall
    f1 = (2 * precision * recall / denom_f1) if denom_f1 > 0 else 0.0

    return {"tp": tp, "tn": tn, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def _print_binary_eval(tag: str, metrics: Dict[str, Any], total: int, positive_total: int) -> None:
    print("\n" + "=" * 100)
    print(f"[2) 합성 8:2 객관 평가] {tag}")
    print(f"total={total}  positive(risk)={positive_total}  negative(normal)={total - positive_total}")
    print(f"confusion: tp={metrics['tp']} fp={metrics['fp']} tn={metrics['tn']} fn={metrics['fn']}")

    tp, fp, fn = metrics["tp"], metrics["fp"], metrics["fn"]
    denom_p = tp + fp
    denom_r = tp + fn
    print(f"precision = tp/(tp+fp) = {tp}/({tp}+{fp}) = {metrics['precision']:.4f}   (denom={denom_p})")
    print(f"recall    = tp/(tp+fn) = {tp}/({tp}+{fn}) = {metrics['recall']:.4f}   (denom={denom_r})")
    print(f"f1        = 2PR/(P+R)  = {metrics['f1']:.4f}")


async def _fetch_daily_rows(resident_id: int, db: AsyncSession, limit_days: int) -> List[Dict[str, float]]:
    stmt = (
        select(DailyFeature)
        .where(DailyFeature.resident_id == resident_id)
        .order_by(DailyFeature.target_date.desc())
        .limit(limit_days)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_daily_to_x1x6(r) for r in rows]

# ===== Recall 우선 캘리브레이션 설정 =====
RECALL_FIRST = True

# p10을 더 올려서(=watch 더 많이) 놓침을 줄이고 싶으면 True
ENABLE_WATCH_UPSHIFT = True

# p10 후보를 만들 때 사용할 시그마 방식: p10_candidate = mean - k*std
# k가 작을수록 후보가 커져서 watch가 늘어남(FN 감소 방향)
WATCH_SIGMA_K = 0.30  # 더 놓치지 않게: 0.10~0.25 / 덜 시끄럽게: 0.30~0.60


def _calibrate_cutoffs_from_raw(raw: np.ndarray, p01: float, p03: float, p10: float) -> Dict[str, float]:
    """
    Recall(놓치지 않기) 우선 캘리브레이션.

    - 기존 코드는 p10을 10% 분위수로 강제해 p10을 낮출 수 있었고, 이는 FN 증가를 유발.
    - 여기서는 p10 하향을 금지하고, 필요하면 p10을 '올리는' 방향만 허용.
    """
    raw = np.asarray(raw, dtype=float)
    mean = float(np.mean(raw))
    std = float(np.std(raw))

    # (참고용) 분위수 후보
    cand_q10 = float(np.quantile(raw, 0.10))

    # (선택) 시그마 기반 후보(상향 가능성이 큼)
    cand_sigma = float(mean - (WATCH_SIGMA_K * std)) if ENABLE_WATCH_UPSHIFT else cand_q10

    # ✅ 핵심: p10은 절대 낮추지 않는다 (Recall 보호)
    # - meta p10과 후보들 중 가장 큰 값으로
    new_p10 = max(float(p10), cand_q10, cand_sigma) if RECALL_FIRST else cand_q10

    # p03/p01은 기본적으로 meta 유지(레벨 구조 보존)
    new_p03 = float(p03)
    new_p01 = float(p01)

    # (원하면) CALIBRATE_ALL=True일 때도 하향 금지로만 허용
    if CALIBRATE_ALL:
        cand_p03 = float(np.quantile(raw, 0.03))
        cand_p01 = float(np.quantile(raw, 0.01))
        # 하향 금지
        new_p03 = max(new_p03, cand_p03)
        new_p01 = max(new_p01, cand_p01)

    # ✅ 단조성 보장 (p01 <= p03 <= p10)
    new_p03 = min(new_p03, new_p10)
    new_p01 = min(new_p01, new_p03)

    return {"p01": new_p01, "p03": new_p03, "p10": new_p10}

async def evaluate_resident(resident_id: int) -> None:
    model, scaler, meta = _load_artifacts(resident_id)

    # meta에서 컷오프 읽기(호환)
    p01 = _get_cut(meta, "score_p01")
    p03 = _get_cut(meta, "score_p03")
    p10 = _get_cut(meta, "score_p10")

    async with AsyncSessionLocal() as db:
        base_rows = await _fetch_daily_rows(resident_id, db, LIMIT_DAYS)

    if len(base_rows) == 0:
        print(f"⚠️ resident_id={resident_id}: daily_features 없음")
        return

    # ---- 1) 훈련/실데이터 재투입 검증 ----
    raw = _raw_scores(model, scaler, meta, base_rows)

    if AUTO_CALIBRATE_CUTOFFS:
        new = _calibrate_cutoffs_from_raw(raw, p01, p03, p10)
        print("\n" + "=" * 100)
        print("[AUTO_CALIBRATE_CUTOFFS]")
        print(f"before: p01={p01} p03={p03} p10={p10}")
        print(f"after : p01={new['p01']} p03={new['p03']} p10={new['p10']}")
        p01, p03, p10 = new["p01"], new["p03"], new["p10"]

    levels = [
        _level_for_eval(float(s), p01, p03, p10, float(base_rows[i]["x6"]))
        for i, s in enumerate(raw)
    ]
    _print_dist_check(f"resident_id={resident_id} (daily_features re-score)", p01, p03, p10, raw, levels)

    # ---- 2) 합성 8:2 객관 평가 ----
    rng = np.random.default_rng(RANDOM_SEED)

    n_total = int(SYNTH_TOTAL)
    n_risk = int(round(n_total * SYNTH_RISK_RATIO))
    n_norm = n_total - n_risk

    synth: List[SynthSample] = []

    for _ in range(n_norm):
        x = _bootstrap_normal_from_db(base_rows, rng)
        synth.append(SynthSample(x=x, y_true=0))

    risk_modes = ["inactive_long", "night_activity_weird", "door_anomaly", "rule_gate_emergency"]
    for i in range(n_risk):
        base = _bootstrap_normal_from_db(base_rows, rng)
        mode = risk_modes[i % len(risk_modes)]
        x = _make_risky_from_normal(base, rng, mode)
        synth.append(SynthSample(x=x, y_true=1))

    rng.shuffle(synth)

    rows = [s.x for s in synth]
    raw2 = _raw_scores(model, scaler, meta, rows)
    lv2 = [_level_for_eval(float(s), p01, p03, p10, float(rows[i]["x6"])) for i, s in enumerate(raw2)]
    y_true = [s.y_true for s in synth]

    def pred_by_threshold(threshold_level: str) -> List[int]:
        thr_rank = LEVEL_TO_RANK[threshold_level]
        return [1 if LEVEL_TO_RANK[lv] >= thr_rank else 0 for lv in lv2]

    for thr in ["watch", "alert", "emergency"]:
        y_pred = pred_by_threshold(thr)
        metrics = _confusion_and_metrics(y_true, y_pred)
        _print_binary_eval(f"resident_id={resident_id} threshold={thr}+", metrics, n_total, n_risk)

    # gate 제외 평가
    idx = [i for i, r in enumerate(rows) if float(r["x6"]) < 720.0]
    y_true_ng = [y_true[i] for i in idx]
    lv2_ng = [lv2[i] for i in idx]

    def pred_by_threshold_ng(threshold_level: str) -> List[int]:
        thr_rank = LEVEL_TO_RANK[threshold_level]
        return [1 if LEVEL_TO_RANK[lv] >= thr_rank else 0 for lv in lv2_ng]

    for thr in ["watch", "alert", "emergency"]:
        y_pred_ng = pred_by_threshold_ng(thr)
        metrics_ng = _confusion_and_metrics(y_true_ng, y_pred_ng)
        _print_binary_eval(
            f"(non-gate only) resident_id={resident_id} threshold={thr}+",
            metrics_ng,
            total=len(y_true_ng),
            positive_total=sum(y_true_ng),
        )

    print("\n" + "=" * 100)
    print("[합성 데이터 레벨 분포]")
    summ = _summarize_levels(lv2)
    print(f"n={summ['n']} counts={summ['counts']} ratios(%)={ {k: round(v,2) for k,v in summ['ratios_percent'].items()} }")


def main():
    print(f"MODEL_DIR={MODEL_DIR.resolve()}")
    print(f"resident_id={RESIDENT_ID}  LIMIT_DAYS={LIMIT_DAYS}  SYNTH_TOTAL={SYNTH_TOTAL}  risk_ratio={SYNTH_RISK_RATIO}")
    import asyncio
    asyncio.run(evaluate_resident(RESIDENT_ID))


if __name__ == "__main__":
    main()