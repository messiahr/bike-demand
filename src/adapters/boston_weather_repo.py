# https://dev.meteostat.net/python
import abc
from datetime import date
from pathlib import Path

import meteostat as ms
import polars as pl

from src.schemas.raw.weather import RawWeatherSchema

BOSTON = ms.Point(42.36, -71.06)


class AbstractWeatherRepository(abc.ABC):
    @abc.abstractmethod
    def get_weather_data(self, start_date: date, end_date: date) -> pl.DataFrame:
        raise NotImplementedError

    @abc.abstractmethod
    def save_weather_data(self, start_date: date, end_date: date, output_path: Path) -> None:
        raise NotImplementedError


class WeatherRepository(AbstractWeatherRepository):
    def get_weather_data(self, start_date: date, end_date: date) -> pl.DataFrame:
        stations = ms.stations.nearby(BOSTON, limit=4)
        ts = ms.hourly(stations, start_date, end_date)
        df = ms.interpolate(ts, BOSTON).fetch()

        if df is None or df.empty:
            raise ValueError("No data found for the specified location and time range.")

        polars_df = pl.from_pandas(df)
        return RawWeatherSchema.validate(polars_df)

    def save_weather_data(self, start_date: date, end_date: date, output_path: Path) -> None:
        df = self.get_weather_data(start_date, end_date)
        df.write_parquet(output_path)
