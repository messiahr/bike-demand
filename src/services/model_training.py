# ruff: noqa: N806, N803 (ML convention: X/y feature/target naming)
"""Train a bike-demand prediction model using LightGBM, Optuna, and MLFlow."""

import math
import os
from datetime import datetime, timedelta

import lightgbm as lgb
import mlflow
import numpy as np
import optuna
import polars as pl
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from src.adapters.model_repository import ModelRepository
from src.adapters.processed_data_repository import ProcessedDataRepository

MLFLOW_TRACKING_URI = "sqlite:///mlflow.db"
MLFLOW_EXPERIMENT = "bike-demand"
RANDOM_STATE = 42
TEST_MONTHS = 3
OPTUNA_TRIALS = 20
EARLY_STOPPING_ROUNDS = 50
_THREADS = os.cpu_count() or 1

FEATURE_COLS = [
    "hour",
    "weekday",
    "month",
    "year",
    "is_weekend",
    "total_docks",
    "lat",
    "lng",
    "temp",
    "rhu",
    "prcp",
    "wspd",
    "wdir",
    "snow",
]

WEATHER_NULL_FILL: dict[str, int | pl.Expr] = {
    "prcp": 0,
    "snow": 0,
    "temp": pl.col("temp").mean(),
    "rhu": pl.col("rhu").mean(),
    "wspd": pl.col("wspd").mean(),
    "wdir": pl.col("wdir").mean(),
}


def _log(msg: str) -> None:
    print(msg, flush=True)


def get_best_params() -> dict[str, object] | None:
    """Return tuned hyperparameters from the best MLflow run, or None.

    Caller must configure mlflow tracking URI and experiment first.
    """
    try:
        runs = mlflow.search_runs(order_by=["metrics.rmse ASC"])
    except Exception:
        _log("Failed to query MLflow runs.")
        return None

    if runs.empty:
        return None

    best_run = runs.iloc[0]
    params: dict[str, object] = {}
    for col in runs.columns:
        if not col.startswith("params.tuned_"):
            continue
        key = col.removeprefix("params.tuned_")
        val = best_run[col]
        if isinstance(val, float) and math.isnan(val):
            continue
        val_str = str(val)
        if val_str.replace(".", "", 1).isnumeric():
            num = float(val_str)
            params[key] = int(num) if num.is_integer() else num
        else:
            params[key] = val

    return params if params else None


def engineer_features(df: pl.LazyFrame) -> pl.DataFrame:
    return (
        df.group_by(
            pl.col("started_at").dt.truncate("1h").alias("datetime"),
            pl.col("start_station_name").alias("station"),
        )
        .agg(
            pl.len().alias("demand"),
            pl.col("start_lat").first().alias("lat"),
            pl.col("start_lng").first().alias("lng"),
            pl.col("start_station_total_docks").first().alias("total_docks"),
            *[pl.col(c).first() for c in WEATHER_NULL_FILL],
        )
        .with_columns(
            pl.col("datetime").dt.hour().alias("hour"),
            pl.col("datetime").dt.weekday().alias("weekday"),
            pl.col("datetime").dt.month().alias("month"),
            pl.col("datetime").dt.year().alias("year"),
            pl.col("datetime").dt.weekday().is_in([5, 6]).alias("is_weekend"),
            *[pl.col(col).fill_null(fill) for col, fill in WEATHER_NULL_FILL.items()],
        )
        .drop_nulls()
        .sort("datetime")
        .collect()
    )


def _lgb_objective(
    trial: optuna.Trial,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
) -> float:
    params: dict[str, object] = {
        "objective": "regression",
        "metric": "rmse",
        "boosting_type": "gbdt",
        "num_leaves": trial.suggest_int("num_leaves", 16, 256),
        "max_depth": trial.suggest_int("max_depth", 3, 15),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "n_estimators": trial.suggest_int("n_estimators", 100, 2000),
        "min_child_samples": trial.suggest_int("min_child_samples", 5, 100),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
        "verbosity": -1,
        "random_state": RANDOM_STATE,
        "num_threads": _THREADS,
    }
    model = lgb.LGBMRegressor(**params)  # type: ignore[arg-type]
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        eval_metric="rmse",
        callbacks=[lgb.early_stopping(EARLY_STOPPING_ROUNDS), lgb.log_evaluation(period=0)],
    )
    return float(np.sqrt(mean_squared_error(y_val, model.predict(X_val))))


def _to_xy(df: pl.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    return df.select(FEATURE_COLS).to_numpy(), df.select("demand").to_numpy().ravel()


def tune_hyperparameters(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    n_trials: int,
) -> dict[str, object]:
    study = optuna.create_study(
        direction="minimize",
        sampler=optuna.samplers.TPESampler(seed=RANDOM_STATE),
    )
    study.optimize(
        lambda trial: _lgb_objective(trial, X_train, y_train, X_val, y_val),
        n_trials=n_trials,
        callbacks=[lambda _study, trial: _log(f"  trial {trial.number}: rmse={trial.value:.4f}")],
        show_progress_bar=True,
    )
    return study.best_params


def train_final(
    X_train: np.ndarray,
    y_train: np.ndarray,
    params: dict[str, object],
) -> lgb.LGBMRegressor:
    model = lgb.LGBMRegressor(
        **params,  # type: ignore[arg-type]
        verbosity=-1,
        random_state=RANDOM_STATE,
        num_threads=_THREADS,
    )
    model.fit(X_train, y_train)
    return model


def evaluate(model: lgb.LGBMRegressor, X_test: np.ndarray, y_test: np.ndarray) -> dict[str, float]:
    y_pred = model.predict(X_test)
    return {
        "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
        "mae": float(mean_absolute_error(y_test, y_pred)),
        "r2": float(r2_score(y_test, y_pred)),
    }


def run(trials: int = OPTUNA_TRIALS, test_months: int = TEST_MONTHS) -> None:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT)

    _log("Loading data ...")
    data = engineer_features(ProcessedDataRepository().load())
    _log(f"  {data.height:,} rows, {data.width} columns")

    test_cutoff = datetime.now() - timedelta(days=test_months * 30)

    train_val_pool = data.filter(pl.col("datetime") < test_cutoff)
    test_set = data.filter(pl.col("datetime") >= test_cutoff)

    val_cutoff = train_val_pool["datetime"].max() - timedelta(days=test_months * 30)
    train_data = train_val_pool.filter(pl.col("datetime") < val_cutoff)
    val_data = train_val_pool.filter(pl.col("datetime") >= val_cutoff)

    _log(f"  train={train_data.height:,}  val={val_data.height:,}  test={test_set.height:,}")

    _log("Converting to numpy ...")
    X_train, y_train = _to_xy(train_data)
    X_val, y_val = _to_xy(val_data)
    X_full, y_full = _to_xy(pl.concat([train_data, val_data]))
    X_test, y_test = _to_xy(test_set)
    _log(f"  X_train={X_train.shape}  X_val={X_val.shape}  X_test={X_test.shape}")

    with mlflow.start_run() as mlflow_run:
        mlflow.log_params(
            {
                "random_state": RANDOM_STATE,
                "test_months": test_months,
                "threads": _THREADS,
                "early_stopping_rounds": EARLY_STOPPING_ROUNDS,
                "features": FEATURE_COLS,
            }
        )

        existing_params = get_best_params()
        if existing_params:
            _log("Found existing tuned parameters; skipping hyperparameter search.")
            best_params = existing_params
        else:
            _log(f"\nTuning ({trials} trials, {_THREADS} threads) ...")
            best_params = tune_hyperparameters(X_train, y_train, X_val, y_val, trials)

        mlflow.log_params({f"tuned_{k}": v for k, v in best_params.items()})
        _log("Training final model ...")
        model = train_final(X_full, y_full, best_params)
        metrics = evaluate(model, X_test, y_test)
        mlflow.log_metrics(metrics)
        mlflow.lightgbm.log_model(model, name="model")
        ModelRepository().save(model)

        _log(f"\nRun: {mlflow_run.info.run_id}")
        _log(f"  RMSE={metrics['rmse']:.4f}  MAE={metrics['mae']:.4f}  R²={metrics['r2']:.4f}")


if __name__ == "__main__":
    run()
