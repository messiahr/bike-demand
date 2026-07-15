# https://dev.meteostat.net/python
import abc
from datetime import date, timedelta
from pathlib import Path

import meteostat as ms
import polars as pl

from config import WEATHER_DIR

BOSTON = ms.Point(42.36, -71.06)
ms.config.block_large_requests = False


class AbstractWeatherRepository(abc.ABC):
    @abc.abstractmethod
    def get_weather_data(self, start_date: date, end_date: date) -> pl.DataFrame:
        raise NotImplementedError

    @abc.abstractmethod
    def save_weather_data(self, start_date: date, end_date: date, output_path: Path) -> None:
        raise NotImplementedError


class WeatherRepository(AbstractWeatherRepository):
    def __init__(self) -> None:
        self._cache_path = WEATHER_DIR / "boston_weather.parquet"

    def _fetch_from_api(self, start_date: date, end_date: date) -> pl.DataFrame:
        """Fetch weather data from the Meteostat API."""
        stations = ms.stations.nearby(BOSTON, limit=4)
        ts = ms.hourly(stations, start_date, end_date)
        df = ms.interpolate(ts, BOSTON).fetch()

        if df is None or df.empty:
            raise ValueError("No data found for the specified location and time range.")

        df = df.reset_index()
        return pl.from_pandas(df)

    def get_weather_data(self, start_date: date, end_date: date) -> pl.DataFrame:
        if self._cache_path.exists():
            cached = pl.read_parquet(self._cache_path)
            if "time" not in cached.columns:
                self._cache_path.unlink()
            else:
                cached_min = cached.select(pl.col("time").min().dt.date()).item()
                cached_max = cached.select(pl.col("time").max().dt.date()).item()

                if start_date >= cached_min and end_date <= cached_max:
                    return cached.filter(
                        (pl.col("time").dt.date() >= start_date)
                        & (pl.col("time").dt.date() <= end_date)
                    )

                gaps: list[pl.DataFrame] = []
                if start_date < cached_min:
                    gaps.append(self._fetch_from_api(start_date, cached_min - timedelta(days=1)))
                if end_date > cached_max:
                    gaps.append(self._fetch_from_api(cached_max + timedelta(days=1), end_date))

                cached = pl.concat([cached, *gaps]).sort("time").unique(subset=["time"])
                cached.write_parquet(self._cache_path)

                return cached.filter(
                    (pl.col("time").dt.date() >= start_date)
                    & (pl.col("time").dt.date() <= end_date)
                )

        df = self._fetch_from_api(start_date, end_date)
        df.write_parquet(self._cache_path)
        return df

    def save_weather_data(self, start_date: date, end_date: date, output_path: Path) -> None:
        df = self.get_weather_data(start_date, end_date)
        df.write_parquet(output_path)
