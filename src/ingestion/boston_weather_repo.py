# https://dev.meteostat.net/python
import abc
from datetime import date

import meteostat as ms
import polars as pl


class AbstractWeatherRepository(abc.ABC):
    @abc.abstractmethod
    def get_weather_data(self, start_date: date, end_date: date) -> pl.DataFrame:
        raise NotImplementedError("Subclasses must implement this method.")


class WeatherRepository(AbstractWeatherRepository):
    def get_weather_data(self, start_date: date, end_date: date) -> pl.DataFrame:
        boston = ms.Point(42.36, -71.06)  # Boston, MA
        stations = ms.stations.nearby(boston, limit=4)
        ts = ms.hourly(stations, start_date, end_date)
        df = ms.interpolate(ts, boston).fetch()

        if df is None or df.empty:
            raise ValueError("No data found for the specified location and time range.")

        return pl.from_pandas(df)
