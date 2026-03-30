import joblib
import numpy as np
import pandas as pd
from pathlib import Path


MODEL_DIR = Path("app/ml/saved_models")

FEATURE_COLS = [
    "x1_motion_count",
    "x2_door_count",
    "x3_avg_interval"
]


def load_model(resident_id):

    model = joblib.load(MODEL_DIR / f"resident_{resident_id}_model.pkl")
    scaler = joblib.load(MODEL_DIR / f"resident_{resident_id}_scaler.pkl")

    return model, scaler


def build_test_data(mean_motion, mean_door, mean_interval):

    # 정상 데이터 (평균 근처)
    normal = [
        {
            "x1_motion_count": mean_motion * 0.8,
            "x2_door_count": mean_door,
            "x3_avg_interval": mean_interval * 0.9
        },
        {
            "x1_motion_count": mean_motion,
            "x2_door_count": mean_door,
            "x3_avg_interval": mean_interval
        },
        {
            "x1_motion_count": mean_motion * 1.2,
            "x2_door_count": mean_door + 0.1,
            "x3_avg_interval": mean_interval * 1.1
        }
    ]

    # 위험 데이터 (활동 급감)
    risk = [
        {
            "x1_motion_count": 0,
            "x2_door_count": 0,
            "x3_avg_interval": mean_interval * 5
        },
        {
            "x1_motion_count": 1,
            "x2_door_count": 0,
            "x3_avg_interval": mean_interval * 4
        },
        {
            "x1_motion_count": 0,
            "x2_door_count": 0,
            "x3_avg_interval": mean_interval * 6
        }
    ]

    df_normal = pd.DataFrame(normal)
    df_risk = pd.DataFrame(risk)

    # train preprocessing
    df_normal["x3_avg_interval"] = np.log1p(df_normal["x3_avg_interval"])
    df_risk["x3_avg_interval"] = np.log1p(df_risk["x3_avg_interval"])

    return df_normal, df_risk


def run_test(resident_id, mean_motion, mean_door, mean_interval):

    model, scaler = load_model(resident_id)

    df_normal, df_risk = build_test_data(
        mean_motion,
        mean_door,
        mean_interval
    )

    X_normal = scaler.transform(df_normal[FEATURE_COLS])
    X_risk = scaler.transform(df_risk[FEATURE_COLS])

    score_normal = model.decision_function(X_normal)
    score_risk = model.decision_function(X_risk)

    print("\n===== NORMAL SCORE =====")
    print(score_normal)

    print("\n===== RISK SCORE =====")
    print(score_risk)

    normal_mean = np.mean(score_normal)
    risk_mean = np.mean(score_risk)

    print("\nnormal mean:", normal_mean)
    print("risk mean:", risk_mean)

    if risk_mean < normal_mean:
        print("\n✔ 모델이 위험을 정상보다 더 이상치로 판단함")
    else:
        print("\n❌ 모델이 위험을 제대로 구분하지 못함")


if __name__ == "__main__":

    resident_id = 300

    # 실제 DB 평균값 사용
    mean_motion = 5.8623
    mean_door = 0.0909
    mean_interval = 14.579765969892508

    run_test(
        resident_id,
        mean_motion,
        mean_door,
        mean_interval
    )