from datetime import datetime

import polars as pl

from src.adapters.bluebikes_repository import BlueBikesRepository


def _get_version_expr() -> pl.Expr:
    repo = BlueBikesRepository.__new__(BlueBikesRepository)
    return repo.get_station_version_expr("started_at")


def _evaluate_version(dates: list[datetime]) -> list[int]:
    df = pl.DataFrame({"started_at": dates})
    expr = _get_version_expr()
    return df.with_columns(expr).select("station_version").to_series().to_list()


def test_version_mixed_dates() -> None:
    dates = [
        datetime(2011, 7, 28),  # v0
        datetime(2016, 12, 31),  # v0
        datetime(2017, 7, 1),  # v1
        datetime(2019, 10, 29),  # v1
        datetime(2019, 10, 30),  # v2
        datetime(2025, 6, 1),  # v2
    ]
    result = _evaluate_version(dates)
    assert result == [0, 0, 1, 1, 2, 2]


def test_version_with_null_date() -> None:
    df = pl.DataFrame({"started_at": [datetime(2024, 1, 1), None]})
    expr = _get_version_expr()
    result = df.with_columns(expr).select("station_version").to_series().to_list()
    assert result[0] == 2
    assert result[1] == 0
