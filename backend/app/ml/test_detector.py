import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import joblib
import numpy as np
import pandas as pd

from app.ml.detector_model import detect_resident_risk
from app.ml.train_model import MODEL_DIR

FEATURE_COLS = ["x1", "x2", "x3", "x4", "x5", "x6"]


def _preprocess_like_detector(meta: dict, features: dict) -> pd.DataFrame:
    cols = meta.get("feature_cols", FEATURE_COLS)
    df = pd.DataFrame([features], columns=cols)
    df = df.replace([np.inf, -np.inf], np.nan).fillna(0)

    pp = meta.get("preprocess", {})
    clip_cfg = pp.get("clip", {})
    tf_cfg = pp.get("transform", {})

    # clip
    for k, (lo, hi) in clip_cfg.items():
        if k in df.columns:
            df[k] = df[k].clip(float(lo), float(hi))

    # transforms
    if tf_cfg.get("x3") == "log1p":
        df["x3"] = np.log1p(df["x3"].astype(float))
    if tf_cfg.get("x5") == "log1p":
        df["x5"] = np.log1p(df["x5"].astype(float))
    # x6 변환 없음

    return df


def _leaf_vector(model, X_scaled: np.ndarray) -> np.ndarray:
    leaf_ids = []
    if hasattr(model, "estimators_features_"):
        for est, feats in zip(model.estimators_, model.estimators_features_):
            leaf_ids.append(est.apply(X_scaled[:, feats])[0])
    else:
        for est in model.estimators_:
            leaf_ids.append(est.apply(X_scaled)[0])
    return np.array(leaf_ids, dtype=int)


async def run_scenarios():
    print("🚀 고독사 예방 시스템 위험도 산출 로직 테스트 시작\n")

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    # ✅ x6: 마지막 motion 이후 경과 분(예시 값)
    scenarios = [
        ("🟢 1. 정상 (활동 활발, 외출 정상)",
         {"x1": 350, "x2": 3, "x3": 60, "x4": 1, "x5": 420, "x6": 20}, 1.0),

        ("🟡 2. 주의 (평소보다 활동량 감소)",
         {"x1": 150, "x2": 1, "x3": 180, "x4": 0, "x5": 500, "x6": 120}, 1.0),

        ("🟠 3. 경고 (거의 움직임 없음)",
         {"x1": 15, "x2": 0, "x3": 360, "x4": 0, "x5": 720, "x6": 480}, 1.0),

        ("🔴 4. 위급 (하루 종일 무활동)",
         {"x1": 0, "x2": 0, "x3": 1440, "x4": 0, "x5": 1440, "x6": 900}, 1.0),

        ("🚨 5. 위급 + 질병 가중치",
         {"x1": 15, "x2": 0, "x3": 360, "x4": 0, "x5": 720, "x6": 480}, 1.25),
    ]

    model = joblib.load(MODEL_DIR / "model_1.pkl")
    scaler = joblib.load(MODEL_DIR / "scaler_1.pkl")
    meta = json.loads((MODEL_DIR / "meta_1.json").read_text(encoding="utf-8"))

    leaf_map = {}

    for name, features, alpha in scenarios:
        with patch("app.ml.detector_model.get_resident_weights", return_value=(alpha, 1.0, 1.0)):
            print(f"[{name}]")
            print(f"   ▶ 입력 데이터: {features}")

            await detect_resident_risk(
                resident_id=1,
                feature_id=999,
                current_features=features,
                db=mock_db,
            )

            added_score = mock_db.add.call_args[0][0]
            reasons = added_score.reason_codes or {}

            print(f"   ▶ raw_score: {reasons.get('raw_score', 'N/A')}")
            print(f"   ▶ threshold: {reasons.get('effective_threshold', 'N/A')}")
            print(f"   ▶ S_base: {added_score.s_base}점")
            print(f"   ▶ S_final: {added_score.score}점 (alpha={alpha})")
            print(f"   ▶ level: {added_score.level}")

            # leaf 비교용
            dfp = _preprocess_like_detector(meta, features)
            Xs = scaler.transform(dfp)
            leaf_vec = _leaf_vector(model, Xs)

            if name.startswith("🟡 2") or name.startswith("🟠 3") or name.startswith("🔴 4"):
                leaf_map[name] = leaf_vec
                print(f"   ▶ leaf_vec_hash: {hash(leaf_vec.tobytes())} (len={len(leaf_vec)})")

            print("-" * 60)

    print("\n🧩 [LEAF 비교: 2/3/4]")
    keys = list(leaf_map.keys())
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = keys[i], keys[j]
            same_all = np.array_equal(leaf_map[a], leaf_map[b])
            same_cnt = int(np.sum(leaf_map[a] == leaf_map[b]))
            print(f"   {a}  vs  {b}")
            print(f"     same_leaf_all?: {same_all}")
            print(f"     same_leaf_count: {same_cnt} / {len(leaf_map[a])}")

    print("\n[meta preprocess]")
    pp = meta.get("preprocess", {})
    print("feature_cols:", meta.get("feature_cols"))
    print("clip:", pp.get("clip"))
    print("transform:", pp.get("transform"))

    print("\n[preprocessed 비교: 2/3/4]")
    for name, features, _alpha in scenarios:
        if not (name.startswith("🟡 2") or name.startswith("🟠 3") or name.startswith("🔴 4")):
            continue
        dfp = _preprocess_like_detector(meta, features)
        print(f"\n[{name}]")
        print("preprocessed:", dfp.to_dict(orient="records")[0])

    print("\n[X_scaled 비교: 2/3/4]")
    for name, features, _alpha in scenarios:
        if not (name.startswith("🟡 2") or name.startswith("🟠 3") or name.startswith("🔴 4")):
            continue
        dfp = _preprocess_like_detector(meta, features)
        Xs = scaler.transform(dfp)
        print(f"\n[{name}]")
        print("X_scaled:", Xs[0])
        print("\n[scaler check]")
        print("mean len:", len(scaler.mean_), "mean:", scaler.mean_)
        print("scale len:", len(scaler.scale_), "scale:", scaler.scale_)


if __name__ == "__main__":
    asyncio.run(run_scenarios())