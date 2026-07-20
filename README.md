<!-- markdownlint-disable MD013 MD033 MD041 -->
<div align="center">

# BlueBikes Demand Forecasting

**End-to-end machine learning system for predicting hourly bike-sharing demand
in Boston**

<img src="https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.13"/>
<img src="https://img.shields.io/badge/Polars-DataFrames-000000?style=flat-square&logo=polars&logoColor=white" alt="Polars"/>
<img src="https://img.shields.io/badge/LightGBM-Gradient%20Boosting-000000?style=flat-square&logo=lightgbm&logoColor=white" alt="LightGBM"/>
<img src="https://img.shields.io/badge/MLflow-Experiment%20Tracking-0194E2?style=flat-square&logo=mlflow&logoColor=white" alt="MLflow"/>
<img src="https://img.shields.io/badge/Optuna-Hyperparameter%20Tuning-2B60DE?style=flat-square&logo=optuna&logoColor=white" alt="Optuna"/>
<img src="https://img.shields.io/badge/Prefect-Orchestration-070D10?style=flat-square&logo=prefect&logoColor=white" alt="Prefect"/>
<img src="https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?style=flat-square&logo=streamlit&logoColor=white" alt="Streamlit"/>
<img src="https://img.shields.io/badge/Pandera-Schema%20Validation-000000?style=flat-square" alt="Pandera"/>
<img src="https://img.shields.io/badge/Nix-Reproducible-5277C3?style=flat-square&logo=nixos&logoColor=white" alt="Nix"/>
<img src="https://img.shields.io/badge/Code%20Style-Ruff-000000?style=flat-square" alt="Ruff"/>
<img src="https://img.shields.io/badge/Typing-strict%20mypy-319F43?style=flat-square" alt="Mypy strict"/>

</div>
<!-- markdownlint-enable MD013 MD033 -->

---

## Overview

Ingests **12+ years** of BlueBikes trip records (900k+ rides) from Boston's
public S3 bucket, combines them with hourly weather data, trains a
gradient-boosted regression model to forecast station-level demand, and displays
results through an interactive 3D dashboard.

Uses strict static typing, Pandera schema validation, Prefect-orchestrated
pipelines, MLflow experiment tracking, and a Nix-based reproducible environment.

---

## Key Highlights

<!-- markdownlint-disable MD013 -->

| Area                     | What This Project Demonstrates                                                                                                                                                                           |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Data Engineering**     | Ingestion from public S3 (HTTP API), incremental parquet caching, CSV sanitization (null bytes, legacy macOS encodings), change detection via mtime manifests                                            |
| **Feature Engineering**  | Temporal decomposition (hour, weekday, month, year, weekend flag), station metadata enrichment, weather integration (11 meteorological variables), station versioning across 3 historical naming schemas |
| **Modeling**             | LightGBM regression with Optuna hyperparameter tuning (TPE sampler, early stopping, 9-parameter search space), chronological train/val/test splits (3-month sliding windows)                             |
| **MLOps**                | MLflow experiment tracking (params, metrics, artifacts), Prefect pipeline orchestration, idempotent incremental data processing                                                                          |
| **Visualization**        | Streamlit interactive dashboard with PyDeck 3D column layers, hourly time slider, dynamic elevation scaling, viridis color mapping                                                                       |
| **Data Validation**      | Pandera schemas enforcing column types, nullability, and completeness at ingestion boundaries                                                                                                            |
| **Software Engineering** | Layered architecture (adapters → schemas → processing → services → UI), strict mypy typing, pytest test suite, Ruff linting/formatting, pre-commit hooks                                                 |
| **Reproducibility**      | Nix flake for system dependencies, `uv` lockfile for Python packages, `.python-version` pinned to 3.13                                                                                                   |

<!-- markdownlint-enable MD013 -->

---

## Architecture

```text
┌─────────────────────────────────────────────────┐
│       Adapters (Data Access / External I/O)     │
│    S3 download · BlueBikes repo · Weather repo  │
└─────────────────────┬───────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────┐
│              Pandera Schemas                    │
│    RawTripSchema · RawWeatherSchema             │
└─────────────────────┬───────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────┐
│               Processing (Pure Transforms)      │
│    standardize_bluebikes_data · merge_weather   │
└─────────────────────┬───────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────┐
│                 Services                        │
│    model_training (LightGBM + Optuna + MLflow)  │
└─────────────────────┬───────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────┐
│                   Streamlit UI                  │
│    1_Explore_Files · 2_Bike_Demand_Map          │
└─────────────────────────────────────────────────┘
```

**Dependency direction:** Adapters → Pandera Schemas → Processing → Services →
Streamlit UI

---

## Tech Stack

| Category              | Tools                           |
| --------------------- | ------------------------------- |
| Data Processing       | Polars (LazyFrame), Pandera     |
| ML Framework          | LightGBM, scikit-learn          |
| Hyperparameter Tuning | Optuna                          |
| Experiment Tracking   | MLflow (SQLite backend)         |
| Orchestration         | Prefect                         |
| Visualization         | Streamlit, PyDeck, Matplotlib   |
| Weather Data          | Meteostat API                   |
| Package Management    | uv                              |
| Environment           | Nix (flake), direnv             |
| Code Quality          | Ruff, mypy (strict), pre-commit |
| Testing               | pytest + pytest-cov             |

---

## Quick Start

```bash
# 1. Enter the Nix development shell (optional, for system-level deps)
nix develop

# 2. Install Python dependencies
make setup

# 3. Download and process data (~1M trip records + weather)
uv run python -m src.pipelines.prepare_data

# 4. Train the demand forecasting model
uv run python -m src.services.model_training

# 5. Launch the dashboard
make run
```

Orchestrated pipeline (with Prefect):

```bash
uv run prefect server start          # Start Prefect server
uv run python -m src.pipelines.prepare_data
```

---

## Model Performance Tracking

All training runs are logged to MLflow with the following tracked artifacts:

- **Parameters:** LightGBM hyperparameters (9 tuned), feature list
- **Metrics:** RMSE, MAE, R² on chronological test splits
- **Artifacts:** Trained model (pickle), feature importance plot

View experiments:

```bash
uv run mlflow ui --backend-store-uri sqlite:///mlflow.db
```

---

## Development

```bash
make lint          # Format & lint (Ruff + mypy)
uv run pytest      # Run the test suite
```
