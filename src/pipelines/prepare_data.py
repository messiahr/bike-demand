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
    bounds = trips.select(
        pl.col("started_at").min().alias("min_date"),
        pl.col("ended_at").max().alias("max_date"),
    ).collect()

    repo = WeatherRepository()
    return repo.get_weather_data(
        bounds["min_date"].item().date(), bounds["max_date"].item().date()
    ).lazy()


@task
def final_merges(
    trips: pl.LazyFrame, stations: pl.LazyFrame, weather: pl.LazyFrame
) -> pl.LazyFrame:
    bb_repo = BlueBikesRepository()
    station_version_expr = bb_repo.get_station_version_expr

    trips_standardized = standardize_stations(trips, stations, station_version_expr)

    return merge_trips_with_weather(trips_standardized, weather)


@flow
def main() -> None:
    trips, stations = bluebikes_import()
    weather = weather_import(trips)
    merged = final_merges(trips, stations, weather)

    data_repo = ProcessedDataRepository()
    data_repo.save(processed_data=merged)


if __name__ == "__main__":
    main()
