# https://dev.meteostat.net/python
import abc
from datetime import date
from pathlib import Path

import meteostat as ms
import polars as pl

BOSTON = ms.Point(42.36, -71.06)


class AbstractWeatherRepository(abc.ABC):
    @abc.abstractmethod
    def get_weather_data(self, start_date: date, end_date: date) -> pl.DataFrame:
        raise NotImplementedError("Subclasses must implement this method.")

    @abc.abstractmethod
    def save_weather_data(self, start_date: date, end_date: date, output_path: Path) -> None:
        raise NotImplementedError("Subclasses must implement this method.")


class WeatherRepository(AbstractWeatherRepository):
    def get_weather_data(self, start_date: date, end_date: date) -> pl.DataFrame:
        stations = ms.stations.nearby(BOSTON, limit=4)
        ts = ms.hourly(stations, start_date, end_date)
        df = ms.interpolate(ts, BOSTON).fetch()

        if df is None or df.empty:
            raise ValueError("No data found for the specified location and time range.")

        return pl.from_pandas(df)

    def save_weather_data(self, start_date: date, end_date: date, output_path: Path) -> None:
        df = self.get_weather_data(start_date, end_date)
        df.write_parquet(output_path)
