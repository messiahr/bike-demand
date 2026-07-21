from datetime import timedelta

import polars as pl
from prefect import flow, task

from src.adapters.bluebikes_repository import BlueBikesRepository
from src.adapters.processed_data_repository import ProcessedDataRepository
from src.adapters.weather_repository import WeatherRepository
from src.processing.merge_weather import merge_trips_with_weather
from src.processing.standardize_bluebikes_data import standardize_stations


@task
def bluebikes_import() -> tuple[pl.LazyFrame, pl.LazyFrame]:
    bluebikes_repository = BlueBikesRepository()
    bluebikes_repository.update()
    trips = bluebikes_repository.trips()
    stations = bluebikes_repository.stations()
    return (trips, stations)


@task
def weather_import(trips: pl.LazyFrame) -> pl.LazyFrame:
    dates = trips.select(
        pl.col("started_at").min().alias("min_date"),
        pl.col("ended_at").max().alias("max_date"),
    ).collect()
    min_date = dates["min_date"][0].date()
    max_date = dates["max_date"][0].date() + timedelta(days=1)
    return WeatherRepository().weather(min_date, max_date)


@task
def final_merges(
    trips: pl.LazyFrame, stations: pl.LazyFrame, weather: pl.LazyFrame
) -> pl.LazyFrame:
    trips_standardized = standardize_stations(
        trips, stations, BlueBikesRepository.get_station_version_expr
    )

    return merge_trips_with_weather(trips_standardized, weather)


@flow
def main() -> str:
    trips, stations = bluebikes_import()
    weather = weather_import(trips)
    merged = final_merges(trips, stations, weather)
    processed_data_repository = ProcessedDataRepository()
    processed_data_repository.save(merged)
    return processed_data_repository.data_path


if __name__ == "__main__":
    main()
