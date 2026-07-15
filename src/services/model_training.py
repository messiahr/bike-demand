"""Model training with MLFlow tracking and Optuna hyperparameter optimization."""

from __future__ import annotations

import logging
import math

import lightgbm as lgb
import mlflow
import optuna
import polars as pl
from mlflow.lightgbm import log_model
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error

from src.adapters.processed_data_repository import ProcessedDataRepository

logger = logging.getLogger(__name__)

TEST_WEEKS = 4
WEATHER_FEATURES = ["temp", "rhum", "prcp", "wspd", "pres"]
FEATURE_COLS = [
    "station_idx",
    "hour_of_day",
    "day_of_week",
    "month",
    "day_of_year",
    "hour_sin",
    "hour_cos",
    "dow_sin",
    "dow_cos",
    "month_sin",
    "month_cos",
    "is_weekend",
    "is_rush_hour",
    *WEATHER_FEATURES,
]


def prepare_features(merged: pl.LazyFrame) -> pl.DataFrame:
    """Aggregate trips to station-hour level and engineer features."""
    df = (
        merged.with_columns(pl.col("started_at").dt.truncate("1h").alias("hour"))
        .group_by("start_station_id", "hour")
        .agg(pl.len().alias("trip_count"), *WEATHER_FEATURES)
        .collect()
    )
    return create_features(df)


def create_features(df: pl.DataFrame) -> pl.DataFrame:
    """Add temporal, cyclical, and categorical features."""
    h = pl.col("hour")
    return df.with_columns(
        h.dt.hour().alias("hour_of_day"),
        h.dt.weekday().alias("day_of_week"),
        h.dt.month().alias("month"),
        h.dt.ordinal_day().alias("day_of_year"),
        (h.dt.weekday() >= 6).cast(pl.Int8).alias("is_weekend"),
        (pl.col("hour_of_day").is_between(7, 9) | pl.col("hour_of_day").is_between(16, 18))
        .cast(pl.Int8)
        .alias("is_rush_hour"),
        # encode with sine and cosine so the model knows the columns are cyclical
        (pl.col("hour_of_day") / 24 * math.tau).sin().alias("hour_sin"),
        (pl.col("hour_of_day") / 24 * math.tau).cos().alias("hour_cos"),
        (pl.col("day_of_week") / 7 * math.tau).sin().alias("dow_sin"),
        (pl.col("day_of_week") / 7 * math.tau).cos().alias("dow_cos"),
        (pl.col("month") / 12 * math.tau).sin().alias("month_sin"),
        (pl.col("month") / 12 * math.tau).cos().alias("month_cos"),
        # remove string overhead by converting
        pl.col("start_station_id").cast(pl.Categorical).to_physical().alias("station_idx"),
    )


def train_test_split_temporal(
    df: pl.DataFrame, test_weeks: int = TEST_WEEKS
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Time-based train/test split using the last N weeks as test."""
    cutoff = df["hour"].max() - pl.duration(weeks=test_weeks)
    return df.filter(pl.col("hour") <= cutoff), df.filter(pl.col("hour") > cutoff)


def objective(
    trial: optuna.Trial,
    x_train: pl.DataFrame,
    x_val: pl.DataFrame,
    y_train: pl.Series,
    y_val: pl.Series,
) -> float:
    """Optuna objective: train LightGBM with suggested params, log to MLFlow."""
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 100, 1000),
        "learning_rate": trial.suggest_float("learning_rate", 1e-3, 0.3, log=True),
        "max_depth": trial.suggest_int("max_depth", 3, 12),
        "num_leaves": trial.suggest_int("num_leaves", 15, 255),
        "min_child_samples": trial.suggest_int("min_child_samples", 5, 100),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
    }

    with mlflow.start_run(run_name=f"trial_{trial.number}", nested=True):
        mlflow.log_params(params)

        model = lgb.LGBMRegressor(**params, verbosity=-1, random_state=42)  # type: ignore[arg-type]
        model.fit(
            x_train,
            y_train,
            eval_set=[(x_val, y_val)],
            callbacks=[lgb.log_evaluation(period=0)],
        )

        preds = model.predict(x_val)
        metrics = {
            "rmse": float(root_mean_squared_error(y_val, preds)),
            "mae": float(mean_absolute_error(y_val, preds)),
            "r2": float(r2_score(y_val, preds)),
        }
        mlflow.log_metrics(metrics)

    return metrics["rmse"]


def _prepare_xy(df: pl.DataFrame) -> tuple[pl.DataFrame, pl.Series]:
    """Split a DataFrame into features and target."""
    return df.drop("hour").select(FEATURE_COLS), df["trip_count"]


def main() -> None:
    """Run Optuna hyperparameter search with MLFlow experiment tracking."""
    logging.basicConfig(level=logging.INFO)

    logger.info("Loading data...")
    processed = ProcessedDataRepository().data()

    logger.info("Preparing features...")
    df = prepare_features(processed)

    train_df, test_df = train_test_split_temporal(df)
    x_train, y_train = _prepare_xy(train_df)
    x_test, y_test = _prepare_xy(test_df)

    logger.info("Train: %d rows | Test: %d rows", len(train_df), len(test_df))

    mlflow.set_experiment("bike-demand")
    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=42))

    with mlflow.start_run(run_name="optuna_study"):
        logger.info("Starting Optuna optimization...")
        study.optimize(
            lambda trial: objective(trial, x_train, x_test, y_train, y_test),
            n_trials=50,
            show_progress_bar=True,
        )

        mlflow.log_metric("best_rmse", study.best_value)
        mlflow.log_metric("best_trial", study.best_trial.number)
        logger.info("Best trial: #%d | RMSE: %.4f", study.best_trial.number, study.best_value)

        best_model = lgb.LGBMRegressor(**study.best_params, verbosity=-1, random_state=42)
        best_model.fit(x_train, y_train)

        final_preds = best_model.predict(x_test)
        mlflow.log_metrics(
            {
                "final_rmse": float(root_mean_squared_error(y_test, final_preds)),
                "final_mae": float(mean_absolute_error(y_test, final_preds)),
                "final_r2": float(r2_score(y_test, final_preds)),
            }
        )

        log_model(best_model, "model")
        run = mlflow.active_run()
        if run is not None:
            logger.info("Model logged to MLFlow run: %s", run.info.run_id)


if __name__ == "__main__":
    main()
