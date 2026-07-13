from datetime import datetime

import polars as pl

from src.processing.merge_weather import merge_trips_with_weather


def test_merge_preserves_all_weather_columns() -> None:
    trips = pl.LazyFrame({"started_at": [datetime(2024, 1, 1, 14, 30)]})
    weather = pl.LazyFrame(
        {
            "time": [datetime(2024, 1, 1, 14, 0)],
            "temp": [20.0],
            "rhu": [65.0],
            "wspd": [5.5],
        }
    )

    result = merge_trips_with_weather(trips, weather).collect()

    assert "temp" in result.columns
    assert "rhu" in result.columns
    assert "wspd" in result.columns
    assert result["temp"][0] == 20.0
    assert result["rhu"][0] == 65.0
    assert result["wspd"][0] == 5.5


def test_merge_trips_outside_weather_range() -> None:
    weather = pl.LazyFrame({"time": [datetime(2024, 1, 1, 14, 0)], "temp": [20.0]})
    trips = pl.LazyFrame(
        {
            "started_at": [
                datetime(2024, 1, 1, 13, 59),
                datetime(2024, 1, 1, 15, 1),
            ]
        }
    )

    result = merge_trips_with_weather(trips, weather).collect()

    assert result["temp"].to_list() == [None, None]


def test_merge_many_trips_few_weather_rows() -> None:
    trips = pl.LazyFrame(
        {
            "started_at": [
                datetime(2024, 1, 1, 14, 0),
                datetime(2024, 1, 1, 14, 15),
                datetime(2024, 1, 1, 14, 30),
                datetime(2024, 1, 1, 14, 45),
            ]
        }
    )
    weather = pl.LazyFrame({"time": [datetime(2024, 1, 1, 14, 0)], "temp": [18.5]})

    result = merge_trips_with_weather(trips, weather).collect()

    assert result.shape[0] == 4
    assert all(v == 18.5 for v in result["temp"].to_list())
