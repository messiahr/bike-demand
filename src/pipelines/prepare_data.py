import polars as pl
from prefect import flow, task

from src.adapters.bluebikes_repository import BlueBikesRepository
from src.adapters.boston_weather_repo import WeatherRepository
from src.processing.merge_weather import merge_trips_with_weather


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
def merge_weather(trips: pl.LazyFrame, weather: pl.LazyFrame) -> pl.LazyFrame:
    return merge_trips_with_weather(trips, weather)


@flow
def main() -> pl.LazyFrame:
    trips, _ = bluebikes_import()
    weather = weather_import(trips)
    merged = merge_weather(trips, weather)
    return merged


if __name__ == "__main__":
    main()
