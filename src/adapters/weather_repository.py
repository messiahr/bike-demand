# https://dev.meteostat.net/python
from datetime import date

import meteostat as ms
import polars as pl

from config import PROCESSED_DIR
from src.schemas.raw.weather import RawWeatherSchema

BOSTON = ms.Point(42.36, -71.06)
ms.config.block_large_requests = False

CACHE_PATH = PROCESSED_DIR / "weather.parquet"


class WeatherRepository:
    def get_weather_data(self, start_date: date, end_date: date) -> pl.DataFrame:
        stations = ms.stations.nearby(BOSTON, limit=4)
        ts = ms.hourly(stations, start_date, end_date)
        df = ms.interpolate(ts, BOSTON).fetch()

        if df is None or df.empty:
            raise ValueError("No data found for the specified location and time range.")

        polars_df = pl.from_pandas(df)
        result = RawWeatherSchema.validate(polars_df)

        if CACHE_PATH.exists():
            existing = pl.scan_parquet(CACHE_PATH).collect()
            combined = pl.concat([existing, result], how="diagonal_relaxed").unique(
                subset=["time"], keep="last"
            )
        else:
            combined = result
        combined.write_parquet(CACHE_PATH)

        return result

    def weather(self, start_date: date, end_date: date) -> pl.LazyFrame:
        if CACHE_PATH.exists():
            cached = pl.scan_parquet(CACHE_PATH)
            cached_max = cached.select(pl.col("time").max()).collect().item()
            if cached_max is not None and cached_max >= end_date:
                return cached.filter((pl.col("time") >= start_date) & (pl.col("time") <= end_date))
        return self.get_weather_data(start_date, end_date).lazy()
