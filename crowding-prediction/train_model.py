"""
train_model.py

Train and compare pooled five-minute Wi-Fi crowding prediction models.

Input:
    data/processed/crowding_5min.csv

Outputs:
    models/ridge.joblib
    models/poisson.joblib
    models/random_forest.joblib

The model predicts the next observed five-minute count using calendar,
weather, sensor, time-of-day, and historical lag features.

Important:
    `session_number` is the class-session index. It is nullable on dates
    that do not count as class sessions; it is not a calendar week number.
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import PoissonRegressor, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


INPUT_FILE = Path("data/processed/crowding_5min.csv")
MODEL_DIR = Path("models")

LAG_MINUTES = [5, 15, 30, 60, 1440, 10080]

NUMERIC_FEATURES = [
    "temp_c",
    "rain_mm",
    "humidity",
    "wind_speed",
    "is_class_day",
    "session_number",
    "hour",
    "minute_of_day_sin",
    "minute_of_day_cos",
    *[f"count_lag_{minutes}m" for minutes in LAG_MINUTES],
]

CATEGORICAL_FEATURES = [
    "sensor_id",
    "weekday",
    "semester",
    "term",
    "phase",
    "day_reason",
]

TARGET = "count"


def add_historical_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add exact-time lags per sensor; missing timestamps remain missing."""
    result = df.copy()
    result["timestamp"] = pd.to_datetime(result["timestamp"])

    for lag_minutes in LAG_MINUTES:
        lagged = result[["sensor_id", "timestamp", TARGET]].copy()
        lagged["timestamp"] += pd.Timedelta(minutes=lag_minutes)
        lagged = lagged.rename(
            columns={TARGET: f"count_lag_{lag_minutes}m"}
        )

        result = result.merge(
            lagged,
            on=["sensor_id", "timestamp"],
            how="left",
            validate="one_to_one",
        )

    return result


def chronological_split(
    df: pd.DataFrame,
    test_fraction: float = 0.2,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split by unique timestamps so the test set is later in time."""
    timestamps = np.sort(df["timestamp"].dropna().unique())
    if len(timestamps) < 2:
        raise ValueError("At least two distinct timestamps are required.")

    split_index = max(1, int(len(timestamps) * (1 - test_fraction)))
    split_index = min(split_index, len(timestamps) - 1)
    cutoff = timestamps[split_index]

    train = df[df["timestamp"] < cutoff].copy()
    test = df[df["timestamp"] >= cutoff].copy()

    if train.empty or test.empty:
        raise ValueError("Chronological split produced an empty partition.")

    return train, test


def make_preprocessor() -> ColumnTransformer:
    """Create a fresh preprocessing pipeline for each estimator."""
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            (
                "onehot",
                OneHotEncoder(handle_unknown="ignore"),
            ),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("numeric", numeric_pipeline, NUMERIC_FEATURES),
            ("categorical", categorical_pipeline, CATEGORICAL_FEATURES),
        ],
        remainder="drop",
    )


def calculate_wape(actual: pd.Series, predicted: np.ndarray) -> float:
    denominator = np.abs(actual).sum()
    if denominator == 0:
        return float("nan")
    return float(np.abs(actual.to_numpy() - predicted).sum() / denominator)


def evaluate(
    name: str,
    actual: pd.Series,
    predicted: np.ndarray,
) -> dict[str, float | str]:
    return {
        "model": name,
        "MAE": float(mean_absolute_error(actual, predicted)),
        "RMSE": float(np.sqrt(mean_squared_error(actual, predicted))),
        "WAPE": calculate_wape(actual, predicted),
    }


def main() -> None:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Training data not found: {INPUT_FILE.resolve()}. "
            "Run prepare_data.py first."
        )

    df = pd.read_csv(INPUT_FILE, parse_dates=["timestamp"])

    required_columns = {
        TARGET,
        "timestamp",
        "sensor_id",
        *NUMERIC_FEATURES,
        *CATEGORICAL_FEATURES,
    }
    missing_columns = sorted(required_columns - set(df.columns))
    if missing_columns:
        raise ValueError(f"CSV is missing required columns: {missing_columns}")

    # Convert nullable numeric fields safely. Missing session numbers stay NaN.
    for column in NUMERIC_FEATURES:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df[TARGET] = pd.to_numeric(df[TARGET], errors="coerce")
    df = df.dropna(subset=[TARGET, "timestamp", "sensor_id"]).copy()
    df = df.sort_values(["sensor_id", "timestamp"]).reset_index(drop=True)

    df = add_historical_features(df)

    # Remove rows without the immediately previous five-minute observation.
    # This makes the task explicitly a one-step-ahead prediction.
    df = df.dropna(subset=["count_lag_5m"]).copy()

    train_df, test_df = chronological_split(df)

    X_train = train_df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y_train = train_df[TARGET]
    X_test = test_df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y_test = test_df[TARGET]

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    estimators = {
        "ridge": Ridge(alpha=1.0),
        "poisson": PoissonRegressor(alpha=0.5, max_iter=1000),
        "random_forest": RandomForestRegressor(
            n_estimators=300,
            min_samples_leaf=3,
            random_state=42,
            n_jobs=-1,
        ),
    }

    results = []

    # Persistence baseline: predict that the next count equals the latest count.
    baseline_prediction = test_df["count_lag_5m"].to_numpy()
    results.append(evaluate("persistence_5m", y_test, baseline_prediction))

    for model_name, estimator in estimators.items():
        pipeline = Pipeline(
            steps=[
                ("preprocessor", make_preprocessor()),
                ("model", estimator),
            ]
        )

        pipeline.fit(X_train, y_train)
        predictions = pipeline.predict(X_test)

        # Counts cannot be negative; clip regression predictions at zero.
        predictions = np.maximum(predictions, 0)

        results.append(evaluate(model_name, y_test, predictions))

        model_path = MODEL_DIR / f"{model_name}.joblib"
        joblib.dump(
            {
                "pipeline": pipeline,
                "numeric_features": NUMERIC_FEATURES,
                "categorical_features": CATEGORICAL_FEATURES,
                "target": TARGET,
                "session_feature": "session_number",
                "lag_minutes": LAG_MINUTES,
            },
            model_path,
        )
        print(f"Saved {model_name} model to {model_path}")

    results_df = pd.DataFrame(results).sort_values("MAE")
    print("\nOverall test performance:")
    print(results_df.to_string(index=False))

    # Per-sensor reporting helps reveal whether a pooled model works
    # consistently across all ten locations.
    best_name = results_df.iloc[0]["model"]
    if best_name == "persistence_5m":
        print(
            "\nThe persistence baseline performed best overall. "
            "The ML models have not yet demonstrated an improvement."
        )

    print("\nTest observations by sensor:")
    print(test_df.groupby("sensor_id").size().to_string())


if __name__ == "__main__":
    main()
