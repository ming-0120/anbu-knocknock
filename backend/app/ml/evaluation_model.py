import asyncio
import pandas as pd

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from app.core.config import get_settings


# --------------------------------------
# DB 설정
# --------------------------------------

settings = get_settings()

engine = create_async_engine(settings.ASYNC_DATABASE_URL, echo=False)

async_session = sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)


# --------------------------------------
# hourly_features 조회
# --------------------------------------

async def load_hourly_features(resident_id: int):

    async with async_session() as db:

        result = await db.execute(text("""
        SELECT
            feature_id,
            resident_id,
            target_hour,
            x1_motion_count,
            x2_door_count,
            x3_avg_interval,
            x4_night_motion_count,
            x5_first_motion_min,
            x6_last_motion_min
        FROM hourly_features
        WHERE resident_id = :resident_id
        ORDER BY target_hour
        """), {"resident_id": resident_id})

        rows = result.fetchall()

        df = pd.DataFrame(rows, columns=[
            "feature_id",
            "resident_id",
            "target_hour",
            "x1_motion_count",
            "x2_door_count",
            "x3_avg_interval",
            "x4_night_motion_count",
            "x5_first_motion_min",
            "x6_last_motion_min"
        ])

        return df


# --------------------------------------
# risk score 조회
# --------------------------------------
async def load_risk_scores(resident_id):

    async with async_session() as db:

        result = await db.execute(text("""
        SELECT
            r.feature_id,
            r.level,
            r.score
        FROM risk_scores r
        JOIN hourly_features h
        ON r.feature_id = h.feature_id
        WHERE h.resident_id = :resident_id
        """), {"resident_id": resident_id})

        rows = result.fetchall()

        df = pd.DataFrame(rows, columns=[
            "feature_id",
            "level",
            "score"
        ])

        return df


# --------------------------------------
# prediction 변환
# --------------------------------------

def convert_prediction(level):

    if level in ("alert", "emergency"):
        return 1

    return 0


# --------------------------------------
# 테스트용 label 생성
# --------------------------------------

def generate_label(df):

    # 단순 rule 기반 label
    # motion이 매우 적으면 이상 상황

    df["label"] = (df["x1_motion_count"] < 3).astype(int)

    return df


# --------------------------------------
# 모델 평가
# --------------------------------------

def evaluate(df):

    y_true = df["label"]
    y_pred = df["pred"]

    TP = ((y_true == 1) & (y_pred == 1)).sum()
    FP = ((y_true == 0) & (y_pred == 1)).sum()
    FN = ((y_true == 1) & (y_pred == 0)).sum()

    precision = TP / (TP + FP + 1e-6)
    recall = TP / (TP + FN + 1e-6)

    f1 = 2 * precision * recall / (precision + recall + 1e-6)

    print("\n===== MODEL EVALUATION =====\n")

    print("TP:", TP)
    print("FP:", FP)
    print("FN:", FN)

    print("precision:", round(precision, 4))
    print("recall:", round(recall, 4))
    print("F1:", round(f1, 4))


# --------------------------------------
# 메인 실행
# --------------------------------------

async def main():

    resident_id = 179

    print("\n===== LOAD HOURLY FEATURES =====\n")

    df_features = await load_hourly_features(resident_id)

    print("hourly rows:", len(df_features))

    print("\n===== LOAD RISK SCORES =====\n")

    df_scores = await load_risk_scores(resident_id)

    print("risk rows:", len(df_scores))

    print("\n===== MERGE DATA =====\n")

    df = df_features.merge(
        df_scores,
        on="feature_id",
        how="left"
    )

    df["pred"] = df["level"].apply(convert_prediction)

    df = generate_label(df)

    evaluate(df)


# --------------------------------------

if __name__ == "__main__":

    asyncio.run(main())