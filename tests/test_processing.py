from datetime import datetime

import polars as pl

from src.processing.merge_weather import merge_trips_with_weather
from src.processing.standardize_bluebikes_data import clean_names


def test_clean_names_literal_replacements() -> None:
    names = pl.Series(["A & B", "C.D", "E'F", "G-H", "I\\J", "K/L"])
    result = pl.DataFrame({"name": names}).with_columns(
        clean_names(pl.col("name")).alias("cleaned")
    )

    assert result["cleaned"].to_list() == ["a and b", "cd", "ef", "g h", "i j", "k l"]


def test_clean_names_word_replacements() -> None:
    names = pl.Series(["Northeastern University", "Central Square"])
    result = pl.DataFrame({"name": names}).with_columns(
        clean_names(pl.col("name")).alias("cleaned")
    )

    assert result["cleaned"].to_list() == ["northeastern u", "central sq"]


def test_merge_trips_with_weather_truncates_to_hour() -> None:
    trips = pl.LazyFrame({"started_at": [datetime(2024, 1, 1, 14, 30, 0)]})
    weather = pl.LazyFrame({"time": [datetime(2024, 1, 1, 14, 0, 0)], "temp": [20.0]})

    result = merge_trips_with_weather(trips, weather).collect()

    assert result["temp"][0] == 20.0


def test_merge_preserves_trips_without_weather() -> None:
    trips = pl.LazyFrame({"started_at": [datetime(2024, 1, 1, 14, 30, 0)]})
    weather = pl.LazyFrame({"time": [datetime(2024, 1, 1, 15, 0, 0)], "temp": [20.0]})

    result = merge_trips_with_weather(trips, weather).collect()

    assert result.shape[0] == 1
    assert result["temp"][0] is None


def test_merge_weather_hour_column_dropped() -> None:
    trips = pl.LazyFrame({"started_at": [datetime(2024, 1, 1, 14, 30, 0)]})
    weather = pl.LazyFrame({"time": [datetime(2024, 1, 1, 14, 0, 0)], "temp": [20.0]})

    result = merge_trips_with_weather(trips, weather).collect()

    assert "weather_hour" not in result.columns


def test_merge_multiple_trips_match_correct_hours() -> None:
    trips = pl.LazyFrame(
        {
            "started_at": [
                datetime(2024, 1, 1, 14, 30),
                datetime(2024, 1, 1, 15, 45),
            ]
        }
    )
    weather = pl.LazyFrame(
        {
            "time": [datetime(2024, 1, 1, 14, 0), datetime(2024, 1, 1, 15, 0)],
            "temp": [20.0, 22.0],
        }
    )

    result = merge_trips_with_weather(trips, weather).collect()

    assert result["temp"].to_list() == [20.0, 22.0]
