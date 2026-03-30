import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal, async_engine
from app.models.daily_feature import DailyFeature

MODEL_DIR = Path("app/ml/saved_models")

# ===== 설정 =====
RESIDENT_ID = 5
LIMIT_DAYS = 30

SYNTH_TOTAL = 200
SYNTH_RISK_RATIO = 0.20
RANDOM_SEED = 42

RULE_GATE_X6 = 720.0
# ==============

LEVELS = ["normal", "watch", "alert", "emergency"]
LEVEL_TO_RANK = {"normal": 0, "watch": 1, "alert": 2, "emergency": 3}


def _is_weekend_date(d) -> bool:
    return d.weekday() >= 5

def _suffix_for_date(d) -> str:
    return "we" if _is_weekend_date(d) else "wd"

def _load_artifacts(resident_id: int, suffix: str):
    model_path = MODEL_DIR / f"model_{resident_id}_{suffix}.pkl"
    scaler_path = MODEL_DIR / f"scaler_{resident_id}_{suffix}.pkl"
    meta_path = MODEL_DIR / f"meta_{resident_id}_{suffix}.json"
    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return model, scaler, meta

def _daily_to_row(f: DailyFeature) -> Dict[str, float]:
    x1 = float(f.x1_motion_count)
    x2 = float(f.x2_door_count)
    x3 = float(f.x3_avg_interval)
    x4 = float(f.x4_night_motion_count)
    x5 = float(f.x5_first_motion_min)
    x6 = float(f.x6_last_motion_min)
    x7 = x4 / (x1 + 1.0)
    x8 = x1 / (x3 + 1.0)
    return {"x1": x1, "x2": x2, "x3": x3, "x4": x4, "x5": x5, "x6": x6, "x7": x7, "x8": x8}

def _preprocess_df(df: pd.DataFrame, meta: Dict[str, Any]) -> pd.DataFrame:
    df = df.replace([np.inf, -np.inf], np.nan).fillna(0)

    pp = meta.get("preprocess", {})
    clip_cfg = pp.get("clip", {})
    tf_cfg = pp.get("transform", {})

    for k, bounds in clip_cfg.items():
        if k in df.columns and isinstance(bounds, (list, tuple)) and len(bounds) == 2:
            lo, hi = bounds
            df[k] = df[k].clip(float(lo), float(hi))

    for k, t in tf_cfg.items():
        if k in df.columns and t == "log1p":
            df[k] = np.log1p(df[k].astype(float))

    return df

def _raw_scores(model, scaler, meta: Dict[str, Any], rows: List[Dict[str, float]]) -> np.ndarray:
    cols = meta.get("feature_cols", ["x1","x2","x3","x4","x5","x6","x7","x8"])
    df = pd.DataFrame(rows, columns=cols)
    df = _preprocess_df(df, meta)
    X = scaler.transform(df)
    return model.decision_function(X)

def _level_from_meta_quantiles(raw_score: float, meta: Dict[str, Any]) -> str:
    p01 = float(meta["score_p01"])
    p03 = float(meta["score_p03"])
    p10 = float(meta["score_p10"])

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
        counts[lv] += 1
    ratios = {k: (counts[k] / n * 100.0) if n else 0.0 for k in LEVELS}
    return {"n": n, "counts": counts, "ratios_percent": ratios}

def _expected_counts(n: int) -> Dict[str, float]:
    return {"emergency": n*0.01, "alert": n*0.02, "watch": n*0.07, "normal": n*0.90}

def _print_dist(title: str, meta: Dict[str, Any], raw: np.ndarray, levels: List[str], rule_gate_count: int) -> None:
    summ = _summarize_levels(levels)
    exp = _expected_counts(summ["n"])
    diffs = {k: summ["counts"][k] - exp[k] for k in LEVELS}

    print("\n" + "=" * 100)
    print(title)
    print(f"cutoffs: p01={meta.get('score_p01')} p03={meta.get('score_p03')} p10={meta.get('score_p10')}")
    print(f"raw_score stats: min={float(np.min(raw)):.6f} max={float(np.max(raw)):.6f} mean={float(np.mean(raw)):.6f} std={float(np.std(raw)):.6f}")
    print(f"n(model-eval only, x6<{RULE_GATE_X6})={summ['n']}  rule_gate(x6>={RULE_GATE_X6})={rule_gate_count}")
    print("counts =", summ["counts"])
    print("ratios(%) =", {k: round(v, 2) for k, v in summ["ratios_percent"].items()})
    print("expected_counts =", {k: round(v, 2) for k, v in exp.items()})
    print("diff(observed-expected) =", {k: round(v, 2) for k, v in diffs.items()})

@dataclass
class SynthSample:
    x: Dict[str, float]
    y_true: int  # 0 normal, 1 risk
    is_rule_gate: int  # 0/1

def _bootstrap_normal(base_rows: List[Dict[str, float]], rng: np.random.Generator) -> Dict[str, float]:
    base = base_rows[int(rng.integers(0, len(base_rows)))]
    x = dict(base)

    for k in ["x1","x2","x4"]:
        v = float(x[k])
        noise = rng.normal(0.0, max(1.0, 0.15 * max(v, 1.0)))
        x[k] = max(0.0, v + noise)

    for k in ["x3","x5","x6"]:
        v = float(x[k])
        noise = rng.normal(0.0, 0.10 * max(v, 10.0))
        x[k] = float(np.clip(v + noise, 0.0, 1440.0))

    # 파생치 재계산
    x["x7"] = float(x["x4"]) / (float(x["x1"]) + 1.0)
    x["x8"] = float(x["x1"]) / (float(x["x3"]) + 1.0)
    return x

def _make_risky(x: Dict[str, float], rng: np.random.Generator, mode: str) -> Tuple[Dict[str, float], int]:
    y = dict(x)
    is_rule = 0

    if mode == "inactive_long":  # 모델이 잡아야 하는 위험(룰게이트 미사용)
        y["x1"] = max(0.0, y["x1"] * 0.05)
        y["x2"] = max(0.0, y["x2"] * 0.10)
        y["x4"] = max(0.0, y["x4"] * 0.05)
        y["x3"] = float(np.clip(y["x3"] * 4.0, 0.0, 1440.0))
        y["x5"] = float(np.clip(y["x5"] + 300.0, 0.0, 1440.0))
        y["x6"] = float(np.clip(max(y["x6"], 500.0) + rng.uniform(80.0, 200.0), 0.0, RULE_GATE_X6 - 1.0))

    elif mode == "night_activity_weird":
        y["x4"] = y["x4"] + rng.uniform(30.0, 120.0)
        y["x3"] = float(np.clip(y["x3"] * rng.uniform(0.2, 0.6), 0.0, 1440.0))
        y["x6"] = float(np.clip(y["x6"] + rng.uniform(100.0, 300.0), 0.0, RULE_GATE_X6 - 1.0))

    elif mode == "door_anomaly":
        if rng.random() < 0.5:
            y["x2"] = 0.0
        else:
            y["x2"] = y["x2"] + rng.uniform(15.0, 50.0)
        y["x1"] = max(0.0, y["x1"] * rng.uniform(0.3, 0.8))
        y["x6"] = float(np.clip(y["x6"] + rng.uniform(150.0, 350.0), 0.0, RULE_GATE_X6 - 1.0))

    elif mode == "rule_gate_emergency":  # 룰게이트 위험(모델 평가에서 분리)
        is_rule = 1
        y["x1"] = 0.0
        y["x2"] = 0.0
        y["x4"] = 0.0
        y["x3"] = float(np.clip(y["x3"] * 6.0, 0.0, 1440.0))
        y["x5"] = float(np.clip(y["x5"] + 400.0, 0.0, 1440.0))
        y["x6"] = float(np.clip(RULE_GATE_X6 + rng.uniform(0.0, 600.0), RULE_GATE_X6, 1440.0))

    # clip + 파생치
    for k in ["x1","x2","x4"]:
        y[k] = float(max(0.0, y[k]))
    for k in ["x3","x5","x6"]:
        y[k] = float(np.clip(y[k], 0.0, 1440.0))
    y["x7"] = float(y["x4"]) / (float(y["x1"]) + 1.0)
    y["x8"] = float(y["x1"]) / (float(y["x3"]) + 1.0)

    return y, is_rule

def _confusion_and_metrics(y_true: List[int], y_pred: List[int]) -> Dict[str, Any]:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)

    denom_p = tp + fp
    denom_r = tp + fn
    precision = tp / denom_p if denom_p > 0 else 0.0
    recall = tp / denom_r if denom_r > 0 else 0.0
    denom_f1 = precision + recall
    f1 = (2 * precision * recall / denom_f1) if denom_f1 > 0 else 0.0

    # FPR/FNR도 같이
    denom_fpr = fp + tn
    denom_fnr = fn + tp
    fpr = fp / denom_fpr if denom_fpr > 0 else 0.0
    fnr = fn / denom_fnr if denom_fnr > 0 else 0.0

    return {
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "precision": precision, "recall": recall, "f1": f1,
        "fpr": fpr, "fnr": fnr,
        "denom_p": denom_p, "denom_r": denom_r, "denom_fpr": denom_fpr, "denom_fnr": denom_fnr,
    }

def _print_metrics(title: str, m: Dict[str, Any], total: int, pos: int) -> None:
    print("\n" + "=" * 100)
    print(title)
    print(f"total={total} positive(risk)={pos} negative(normal)={total-pos}")
    print(f"confusion: tp={m['tp']} fp={m['fp']} tn={m['tn']} fn={m['fn']}")
    print(f"precision = tp/(tp+fp) = {m['tp']}/({m['tp']}+{m['fp']}) = {m['precision']:.4f} (denom={m['denom_p']})")
    print(f"recall    = tp/(tp+fn) = {m['tp']}/({m['tp']}+{m['fn']}) = {m['recall']:.4f} (denom={m['denom_r']})")
    print(f"f1        = 2PR/(P+R)  = {m['f1']:.4f}")
    print(f"FPR       = fp/(fp+tn) = {m['fp']}/({m['fp']}+{m['tn']}) = {m['fpr']:.4f} (denom={m['denom_fpr']})")
    print(f"FNR       = fn/(fn+tp) = {m['fn']}/({m['fn']}+{m['tp']}) = {m['fnr']:.4f} (denom={m['denom_fnr']})")

async def _fetch_daily(resident_id: int, db: AsyncSession) -> List[DailyFeature]:
    stmt = (
        select(DailyFeature)
        .where(DailyFeature.resident_id == resident_id)
        .order_by(DailyFeature.target_date.desc())
        .limit(LIMIT_DAYS)
    )
    return (await db.execute(stmt)).scalars().all()

async def evaluate_resident(resident_id: int) -> None:
    # 1) DB 로드
    async with AsyncSessionLocal() as db:
        feats = await _fetch_daily(resident_id, db)

    if not feats:
        print(f"⚠️ resident={resident_id}: daily_features 없음")
        return

    # 2) 평일/주말 분리 재투입 검증 (rule-gate 분리)
    for suffix in ["wd", "we"]:
        model, scaler, meta = _load_artifacts(resident_id, suffix)
        subset = [f for f in feats if _suffix_for_date(f.target_date) == suffix]

        rows_model = []
        rule_gate = 0
        for f in subset:
            row = _daily_to_row(f)
            if row["x6"] >= RULE_GATE_X6:
                rule_gate += 1
            else:
                rows_model.append(row)

        if not rows_model:
            print(f"\n[re-score] resident={resident_id} split={suffix}: 모델평가 대상(x6<{RULE_GATE_X6}) 없음, rule_gate={rule_gate}")
            continue

        raw = _raw_scores(model, scaler, meta, rows_model)
        levels = [_level_from_meta_quantiles(float(s), meta) for s in raw]

        _print_dist(
            title=f"[1) 재투입 분포 검증] resident={resident_id} split={suffix}",
            meta=meta,
            raw=raw,
            levels=levels,
            rule_gate_count=rule_gate,
        )

    # 3) 합성 8:2 평가 (rule-gate 포함/제외 둘 다)
    rng = np.random.default_rng(RANDOM_SEED)

    # 합성 base는 전체 feats에서 부트스트랩
    base_rows = [_daily_to_row(f) for f in feats]

    n_total = int(SYNTH_TOTAL)
    n_risk = int(round(n_total * SYNTH_RISK_RATIO))
    n_norm = n_total - n_risk

    # 위험 모드 구성: rule-gate 비율을 너무 크게 하지 않도록 10%로 제한
    risk_modes = (
        ["inactive_long"] * 6 +
        ["night_activity_weird"] * 2 +
        ["door_anomaly"] * 1 +
        ["rule_gate_emergency"] * 1
    )

    synth: List[SynthSample] = []

    for _ in range(n_norm):
        x = _bootstrap_normal(base_rows, rng)
        synth.append(SynthSample(x=x, y_true=0, is_rule_gate=0))

    for i in range(n_risk):
        base = _bootstrap_normal(base_rows, rng)
        mode = risk_modes[i % len(risk_modes)]
        x, is_rule = _make_risky(base, rng, mode)
        synth.append(SynthSample(x=x, y_true=1, is_rule_gate=is_rule))

    rng.shuffle(synth)

    # split 선택: 합성은 “오늘이 평일인지/주말인지”가 없으니
    # 운영 관점에서는 둘 중 하나로 고정 평가하면 왜곡됨.
    # => 여기서는 wd 모델로 평가(대표) + 필요하면 we도 한 번 더 돌리면 됨.
    for suffix in ["wd", "we"]:
        model, scaler, meta = _load_artifacts(resident_id, suffix)

        rows = [s.x for s in synth]
        raw = _raw_scores(model, scaler, meta, rows)

        # 룰게이트는 모델 판단이 아니라 정책이므로 분리
        levels = []
        for i, s in enumerate(synth):
            if s.x["x6"] >= RULE_GATE_X6:
                levels.append("emergency")
            else:
                levels.append(_level_from_meta_quantiles(float(raw[i]), meta))

        # threshold별 위험 판정
        def pred(thr: str) -> List[int]:
            thr_rank = LEVEL_TO_RANK[thr]
            return [1 if LEVEL_TO_RANK[lv] >= thr_rank else 0 for lv in levels]

        # (A) 전체(룰 포함) 지표
        y_true_all = [s.y_true for s in synth]
        for thr in ["watch", "alert", "emergency"]:
            m = _confusion_and_metrics(y_true_all, pred(thr))
            _print_metrics(
                title=f"[2-A) 합성 평가(룰 포함)] resident={resident_id} split={suffix} threshold={thr}+",
                m=m, total=n_total, pos=n_risk
            )

        # (B) 룰 제외(모델이 실제로 판단해야 하는 영역) 지표
        idx = [i for i, s in enumerate(synth) if s.x["x6"] < RULE_GATE_X6]
        y_true_nr = [y_true_all[i] for i in idx]

        if idx:
            for thr in ["watch", "alert", "emergency"]:
                y_pred_nr = [pred(thr)[i] for i in idx]
                m = _confusion_and_metrics(y_true_nr, y_pred_nr)
                _print_metrics(
                    title=f"[2-B) 합성 평가(룰 제외, x6<{RULE_GATE_X6})] resident={resident_id} split={suffix} threshold={thr}+",
                    m=m, total=len(idx), pos=sum(y_true_nr)
                )

        # 레벨 분포
        summ = _summarize_levels(levels)
        print("\n" + "=" * 100)
        print(f"[합성 레벨 분포] resident={resident_id} split={suffix}")
        print(f"n={summ['n']} counts={summ['counts']} ratios(%)={ {k: round(v,2) for k,v in summ['ratios_percent'].items()} }")

async def _amain():
    print(f"MODEL_DIR={MODEL_DIR.resolve()}")
    print(f"resident_id={RESIDENT_ID} LIMIT_DAYS={LIMIT_DAYS} SYNTH_TOTAL={SYNTH_TOTAL} risk_ratio={SYNTH_RISK_RATIO} RULE_GATE_X6={RULE_GATE_X6}")
    await evaluate_resident(RESIDENT_ID)

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(_amain())
    finally:
        try:
            asyncio.run(async_engine.dispose())
        except Exception:
            pass