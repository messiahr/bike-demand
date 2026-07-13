from datetime import datetime

import polars as pl

from src.processing.merge_weather import merge_trips_with_weather


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
