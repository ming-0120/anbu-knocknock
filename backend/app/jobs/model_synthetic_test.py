# app/jobs/model_evaluation_job.py
#
# 목적:
# 1) (객관) 훈련 데이터 재투입 검증: daily_features를 모델에 다시 넣었을 때
#    quantile cut(p01/p03/p10) 기준 레벨 분포가 기대치(1/2/7/90%) 근처인지 확인
# 2) (객관) 합성 8:2 검증: 정상/위험 라벨이 있는 synthetic set을 만들어
#    watch+/alert+/emergency+ 기준 precision/recall/F1 및 confusion matrix 산출
#
# 주의:
# - DB에 RiskScore를 저장하지 않음(평가 전용)
# - train_model.py가 만든 MODEL_DIR/model_{id}.pkl, scaler_{id}.pkl, meta_{id}.json 필요
#
# 실행:
#   python -m app.jobs.model_evaluation_job
#
# 설정:
#   RESIDENT_ID = 989  # 모델이 있는 resident_id로 변경

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.models.daily_feature import DailyFeature

MODEL_DIR = Path("app/ml/saved_models")

# ===== 설정 =====
RESIDENT_ID = 5          # ✅ 여기만 바꿔서 실행
LIMIT_DAYS = 365           # train_model과 동일하게 맞추는 게 좋음 (예: 365)
SYNTH_TOTAL = 200          # 합성 데이터 총 개수
SYNTH_RISK_RATIO = 0.20    # 8:2 -> 위험 20%
RANDOM_SEED = 42
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


def _daily_to_x1x6(f: DailyFeature) -> Dict[str, float]:
    # train_model.py에서 사용한 스키마와 동일하게 맞춤
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

    # clip
    for k, bounds in clip_cfg.items():
        if k in df.columns and isinstance(bounds, (list, tuple)) and len(bounds) == 2:
            lo, hi = bounds
            df[k] = df[k].clip(float(lo), float(hi))

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


def _level_from_quantiles(raw_score: float, meta: Dict[str, Any]) -> str:
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
        counts[lv] = counts.get(lv, 0) + 1

    # 비율(%) 계산은 “숫자 계산 과정”이 명확해야 하므로 그대로 보여줌
    ratios = {}
    for k in LEVELS:
        ratios[k] = (counts[k] / n) * 100.0 if n > 0 else 0.0

    return {"n": n, "counts": counts, "ratios_percent": ratios}


def _expected_counts_from_quantiles(n: int) -> Dict[str, float]:
    # 기대 비율: emergency 1%, alert 추가 2%(=3-1), watch 추가 7%(=10-3), normal 90%
    # 기대 "개수" = n * 비율
    return {
        "emergency": n * 0.01,
        "alert": n * 0.02,
        "watch": n * 0.07,
        "normal": n * 0.90,
    }


def _print_dist_check(tag: str, meta: Dict[str, Any], raw_scores: np.ndarray, levels: List[str]) -> None:
    print("\n" + "=" * 100)
    print(f"[1) 훈련/실데이터 재투입 검증] {tag}")
    print(f"cutoffs: p01={meta.get('score_p01')} p03={meta.get('score_p03')} p10={meta.get('score_p10')}")
    print(f"raw_score stats: min={float(np.min(raw_scores)):.6f} max={float(np.max(raw_scores)):.6f} "
          f"mean={float(np.mean(raw_scores)):.6f} std={float(np.std(raw_scores)):.6f}")

    summary = _summarize_levels(levels)
    exp = _expected_counts_from_quantiles(summary["n"])

    print(f"n={summary['n']}")
    print("counts =", summary["counts"])
    print("ratios(%) =", {k: round(v, 2) for k, v in summary["ratios_percent"].items()})

    # 기대 개수와의 차이도 계산(검증 가능하게 숫자 그대로)
    # diff = observed - expected
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
    # DB에서 정상분포를 추정하기 위한 간단한 bootstrap(임의 한 행 + 약간의 노이즈)
    base = rows[int(rng.integers(0, len(rows)))]
    x = dict(base)

    # 각 피처에 작은 노이즈(정상 범위 내) 추가
    # x1/x2/x4는 카운트: +/- 10~20% 수준
    for k in ["x1", "x2", "x4"]:
        v = float(x[k])
        noise = rng.normal(0.0, max(1.0, 0.15 * max(v, 1.0)))
        x[k] = max(0.0, v + noise)

    # x3/x5/x6는 분(min): +/- 5~15% 수준, 0~1440 clip
    for k in ["x3", "x5", "x6"]:
        v = float(x[k])
        noise = rng.normal(0.0, 0.10 * max(v, 10.0))
        x[k] = float(np.clip(v + noise, 0.0, 1440.0))
    x["x6"] = float(np.clip(x["x6"], 0.0, 719.0))
    return x


def _make_risky_from_normal(x: Dict[str, float], rng: np.random.Generator, mode: str) -> Dict[str, float]:
    # 위험 샘플을 여러 모드로 생성(정답 라벨=위험)
    y = dict(x)

    if mode == "inactive_long":  # 비활동 길게 (x6 증가 + 활동량 감소)
        y["x1"] = max(0.0, y["x1"] * 0.05)
        y["x2"] = max(0.0, y["x2"] * 0.10)
        y["x4"] = max(0.0, y["x4"] * 0.05)
        y["x3"] = float(np.clip(y["x3"] * 4.0, 0.0, 1440.0))
        y["x5"] = float(np.clip(y["x5"] + 300.0, 0.0, 1440.0))
        y["x6"] = float(np.clip(max(y["x6"], 500.0) + rng.uniform(80.0, 200.0), 0.0, 719.0))  # 룰게이트는 피함

    elif mode == "night_activity_weird":  # 야간활동 비정상 (x4 급증 + 기타 약간 이상)
        y["x4"] = y["x4"] + rng.uniform(30.0, 120.0)
        y["x3"] = float(np.clip(y["x3"] * rng.uniform(0.2, 0.6), 0.0, 1440.0))
        y["x6"] = float(np.clip(y["x6"] + rng.uniform(100.0, 300.0), 0.0, 719.0))

    elif mode == "door_anomaly":  # 문 이벤트 과다/과소 (x2 변화)
        # 과소/과다 랜덤
        if rng.random() < 0.5:
            y["x2"] = 0.0
        else:
            y["x2"] = y["x2"] + rng.uniform(15.0, 50.0)
        y["x1"] = max(0.0, y["x1"] * rng.uniform(0.3, 0.8))
        y["x6"] = float(np.clip(y["x6"] + rng.uniform(150.0, 350.0), 0.0, 719.0))

    elif mode == "rule_gate_emergency":  # 룰게이트 강제 emergency (x6 >= 720)
        y["x1"] = 0.0
        y["x2"] = 0.0
        y["x4"] = 0.0
        y["x3"] = float(np.clip(y["x3"] * 6.0, 0.0, 1440.0))
        y["x5"] = float(np.clip(y["x5"] + 400.0, 0.0, 1440.0))
        y["x6"] = float(np.clip(720.0 + rng.uniform(0.0, 600.0), 720.0, 1440.0))

    else:
        # 기본: inactive_long
        return _make_risky_from_normal(y, rng, "inactive_long")

    # 최종 clip
    y["x1"] = float(max(0.0, y["x1"]))
    y["x2"] = float(max(0.0, y["x2"]))
    y["x3"] = float(np.clip(y["x3"], 0.0, 1440.0))
    y["x4"] = float(max(0.0, y["x4"]))
    y["x5"] = float(np.clip(y["x5"], 0.0, 1440.0))
    y["x6"] = float(np.clip(y["x6"], 0.0, 1440.0))
    return y


def _level_for_eval(raw_score: float, meta: Dict[str, Any], x6: float) -> str:
    # 평가에서도 detector 정책과 동일하게: 룰게이트 우선
    if x6 >= 720.0:
        return "emergency"
    return _level_from_quantiles(raw_score, meta)


def _confusion_and_metrics(y_true: List[int], y_pred: List[int]) -> Dict[str, Any]:
    # y_true/y_pred: 0/1 (0=정상, 1=위험)
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)

    # precision = tp / (tp+fp)
    denom_p = tp + fp
    precision = tp / denom_p if denom_p > 0 else 0.0

    # recall = tp / (tp+fn)
    denom_r = tp + fn
    recall = tp / denom_r if denom_r > 0 else 0.0

    # f1 = 2PR / (P+R)
    denom_f1 = precision + recall
    f1 = (2 * precision * recall / denom_f1) if denom_f1 > 0 else 0.0

    return {
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _print_binary_eval(tag: str, metrics: Dict[str, Any], total: int, positive_total: int) -> None:
    print("\n" + "=" * 100)
    print(f"[2) 합성 8:2 객관 평가] {tag}")
    print(f"total={total}  positive(risk)={positive_total}  negative(normal)={total - positive_total}")
    print(f"confusion: tp={metrics['tp']} fp={metrics['fp']} tn={metrics['tn']} fn={metrics['fn']}")

    # 숫자 계산 과정이 검증 가능하도록 분모도 함께 출력
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


async def evaluate_resident(resident_id: int) -> None:
    model, scaler, meta = _load_artifacts(resident_id)

    async with AsyncSessionLocal() as db:
        base_rows = await _fetch_daily_rows(resident_id, db, LIMIT_DAYS)

    if len(base_rows) == 0:
        print(f"⚠️ resident_id={resident_id}: daily_features 없음")
        return

    # ---- 1) 훈련/실데이터 재투입 검증 ----
    raw = _raw_scores(model, scaler, meta, base_rows)
    levels = [_level_for_eval(float(s), meta, float(base_rows[i]["x6"])) for i, s in enumerate(raw)]
    _print_dist_check(f"resident_id={resident_id} (daily_features re-score)", meta, raw, levels)

    # ---- 2) 합성 8:2 객관 평가 ----
    rng = np.random.default_rng(RANDOM_SEED)

    n_total = int(SYNTH_TOTAL)
    n_risk = int(round(n_total * SYNTH_RISK_RATIO))
    n_norm = n_total - n_risk

    synth: List[SynthSample] = []

    # 정상 샘플
    for _ in range(n_norm):
        x = _bootstrap_normal_from_db(base_rows, rng)
        synth.append(SynthSample(x=x, y_true=0))

    # 위험 샘플: 여러 모드를 섞어서 생성
    risk_modes = ["inactive_long", "night_activity_weird", "door_anomaly"]
    for i in range(n_risk):
        base = _bootstrap_normal_from_db(base_rows, rng)
        mode = risk_modes[i % len(risk_modes)]
        x = _make_risky_from_normal(base, rng, mode)
        synth.append(SynthSample(x=x, y_true=1))

    # 섞기
    rng.shuffle(synth)

    # 예측: 임계는 "watch 이상"을 위험(1)으로 간주하는 등 다양한 컷으로 평가 가능
    # 여기서는 3가지 컷을 전부 계산해줌:
    #  - watch+ : watch/alert/emergency => 위험
    #  - alert+ : alert/emergency => 위험
    #  - emergency only : emergency => 위험
    rows = [s.x for s in synth]
    raw2 = _raw_scores(model, scaler, meta, rows)
    lv2 = [_level_for_eval(float(s), meta, float(rows[i]["x6"])) for i, s in enumerate(raw2)]

    y_true = [s.y_true for s in synth]
    split = len(synth) // 2
    idx_valid = list(range(0, split))
    idx_test = list(range(split, len(synth)))

    def eval_threshold(indices, thr):
        tp = tn = fp = fn = 0
        for i in indices:
            t = y_true[i]
            s = float(raw2[i])

            # raw_score가 작을수록 이상 → s < thr 이면 위험
            p = 1 if s < thr else 0

            if t == 1 and p == 1:
                tp += 1
            elif t == 0 and p == 0:
                tn += 1
            elif t == 0 and p == 1:
                fp += 1
            elif t == 1 and p == 0:
                fn += 1

        denom_p = tp + fp
        denom_r = tp + fn

        precision = tp / denom_p if denom_p > 0 else 0.0
        recall = tp / denom_r if denom_r > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        return {
            "tp": tp, "tn": tn, "fp": fp, "fn": fn,
            "precision": precision,
            "recall": recall,
            "f1": f1
        }

    # 2) VALID raw_score 기준 후보 threshold 생성 (분위수 기반)
    raw_valid = np.array([float(raw2[i]) for i in idx_valid])
    quantiles = [0.01, 0.03, 0.05, 0.07, 0.10, 0.15, 0.20, 0.25, 0.30]
    candidates = sorted({float(np.quantile(raw_valid, q)) for q in quantiles})

    best_thr = None
    best_f1 = -1.0
    best_metrics = None

    # 3) VALID에서 best F1 찾기
    for thr in candidates:
        m = eval_threshold(idx_valid, thr)
        if m["f1"] > best_f1:
            best_f1 = m["f1"]
            best_thr = thr
            best_metrics = m

    print("\n" + "=" * 100)
    print("[VALID threshold 탐색 결과]")
    print(f"best_thr={best_thr:.6f}")
    print(f"tp={best_metrics['tp']} fp={best_metrics['fp']} tn={best_metrics['tn']} fn={best_metrics['fn']}")
    print(f"precision={best_metrics['precision']:.4f} recall={best_metrics['recall']:.4f} f1={best_metrics['f1']:.4f}")

    # 4) TEST에서 고정 threshold로 최종 평가
    test_metrics = eval_threshold(idx_test, best_thr)

    print("\n" + "=" * 100)
    print("[TEST 최종 평가]")
    print(f"thr={best_thr:.6f}")
    print(f"tp={test_metrics['tp']} fp={test_metrics['fp']} tn={test_metrics['tn']} fn={test_metrics['fn']}")

    tp = test_metrics["tp"]
    fp = test_metrics["fp"]
    fn = test_metrics["fn"]

    print(f"precision = {tp}/({tp}+{fp}) = {test_metrics['precision']:.4f}")
    print(f"recall    = {tp}/({tp}+{fn}) = {test_metrics['recall']:.4f}")
    print(f"f1        = {test_metrics['f1']:.4f}")
    
    def pred_by_threshold(threshold_level: str) -> List[int]:
        thr_rank = LEVEL_TO_RANK[threshold_level]
        return [1 if LEVEL_TO_RANK[lv] >= thr_rank else 0 for lv in lv2]

    for thr in ["watch", "alert", "emergency"]:
        y_pred = pred_by_threshold(thr)
        metrics = _confusion_and_metrics(y_true, y_pred)
        _print_binary_eval(f"resident_id={resident_id} threshold={thr}+", metrics, n_total, n_risk)
    
    # cutoff 평가용: gate 제외
    idx = [i for i, r in enumerate(rows) if float(r["x6"]) < 720.0]
    y_true_ng = [y_true[i] for i in idx]
    lv2_ng = [lv2[i] for i in idx]

    def pred_by_threshold_ng(threshold_level: str) -> List[int]:
        thr_rank = LEVEL_TO_RANK[threshold_level]
        return [1 if LEVEL_TO_RANK[lv] >= thr_rank else 0 for lv in lv2_ng]

    for thr in ["watch", "alert", "emergency"]:
        y_pred_ng = pred_by_threshold_ng(thr)
        metrics_ng = _confusion_and_metrics(y_true_ng, y_pred_ng)
        _print_binary_eval(f"(non-gate only) resident_id={resident_id} threshold={thr}+",
                           metrics_ng, total=len(y_true_ng), positive_total=sum(y_true_ng))
    # 부가: 합성에서 레벨 분포도 출력
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