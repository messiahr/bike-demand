import polars as pl
from prefect import flow, task

from src.adapters.bluebikes_repository import BlueBikesRepository
from src.adapters.boston_weather_repo import WeatherRepository
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
    min_date = trips.select(pl.col("started_at").min()).collect().item().date()
    max_date = trips.select(pl.col("ended_at").max()).collect().item().date()

    repo = WeatherRepository()
    return repo.get_weather_data(min_date, max_date).lazy()


@task
def final_merges(
    trips: pl.LazyFrame, stations: pl.LazyFrame, weather: pl.LazyFrame
) -> pl.LazyFrame:
    bb_repo = BlueBikesRepository()
    station_version_expr = bb_repo.get_station_version_expr

    trips_standardized = standardize_stations(trips, stations, station_version_expr)

    return merge_trips_with_weather(trips_standardized, weather)


@flow
def main() -> pl.LazyFrame:
    trips, stations = bluebikes_import()
    weather = weather_import(trips)
    merged = final_merges(trips, stations, weather)
    return merged


if __name__ == "__main__":
    main()
