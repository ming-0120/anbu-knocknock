import argparse
import asyncio
import pandas as pd

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from app.core.config import get_settings
from app.ml.evaluation_model import (
    convert_prediction,
    generate_label,
    evaluate
)


settings = get_settings()

engine = create_async_engine(settings.ASYNC_DATABASE_URL, echo=False)

async_session = sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)


async def load_hourly_features(resident_id):

    async with async_session() as db:

        result = await db.execute(text("""
        SELECT
            feature_id,
            resident_id,
            target_hour,
            x1_motion_count,
            x2_door_count,
            x3_avg_interval,
            x4_night_motion_count
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
            "x4_night_motion_count"
        ])

        return df


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


async def validate(resident_id):

    print("\n===== LOAD HOURLY FEATURES =====")

    df_features = await load_hourly_features(resident_id)

    print("hourly rows:", len(df_features))

    print("\n===== LOAD RISK SCORES =====")

    df_scores = await load_risk_scores(resident_id)

    print("risk rows:", len(df_scores))

    print("\n===== MERGE DATA =====")

    df = df_features.merge(
        df_scores,
        on="feature_id",
        how="left"
    )

    df["pred"] = df["level"].apply(
        lambda x: convert_prediction(x) if pd.notna(x) else 0
    )

    df = generate_label(df)

    result = evaluate(df)

    print("\n===== MODEL EVALUATION =====\n")

    print("TP:", result["TP"])
    print("FP:", result["FP"])
    print("FN:", result["FN"])

    print("precision:", round(result["precision"], 4))
    print("recall:", round(result["recall"], 4))
    print("F1:", round(result["f1"], 4))


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--resident-id",
        type=int,
        required=True
    )

    args = parser.parse_args()

    asyncio.run(validate(args.resident_id))


if __name__ == "__main__":
    main()