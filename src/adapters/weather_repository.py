# https://dev.meteostat.net/python
from datetime import date

import meteostat as ms
import polars as pl

from config import PROCESSED_DIR
from src.schemas.raw.weather import RawWeatherSchema

BOSTON = ms.Point(42.36, -71.06)
ms.config.block_large_requests = False

CACHE_PATH = PROCESSED_DIR / "weather.parquet"

# Meteostat returns 'rhum' but we rename to 'rhu' for consistency.
# Some stations don't report every parameter, so columns like dwpt, snow,
# wpgt, tsun, and coco may be absent from the API response.
_METEOSTAT_RENAME = {"rhum": "rhu"}

_WEATHER_METRICS = {
    "temp",
    "dwpt",
    "rhu",
    "prcp",
    "snow",
    "wdir",
    "wspd",
    "wpgt",
    "pres",
    "tsun",
    "coco",
}


def _fill_missing_columns(df: pl.DataFrame) -> pl.DataFrame:
    for col in _WEATHER_METRICS - set(df.columns):
        df = df.with_columns(pl.lit(None).cast(pl.Float64).alias(col))
    return df


def _fetch_weather_data(start_date: date, end_date: date) -> pl.DataFrame:
    """Fetch hourly weather data from Meteostat for the given date range."""
    stations = ms.stations.nearby(BOSTON, limit=4)
    ts = ms.hourly(stations, start_date, end_date)
    df = ms.interpolate(ts, BOSTON).fetch()

    if df is None or df.empty:
        raise ValueError("No data found for the specified location and time range.")

    polars_df = (
        pl.from_pandas(df, include_index=True).rename(_METEOSTAT_RENAME).pipe(_fill_missing_columns)
    )
    return RawWeatherSchema.validate(polars_df)


def _merge_into_cache(new_data: pl.DataFrame) -> None:
    """Merge new data into the cache, deduplicating by time (keeping latest)."""
    if CACHE_PATH.exists():
        existing = pl.read_parquet(CACHE_PATH)
        combined = pl.concat([existing, new_data], how="diagonal_relaxed").unique(
            subset=["time"], keep="last"
        )
    else:
        combined = new_data
    combined.write_parquet(CACHE_PATH)


class WeatherRepository:
    """Returns hourly weather data, using cache to minimize API calls."""

    def weather(self, start_date: date, end_date: date) -> pl.LazyFrame:
        if CACHE_PATH.exists():
            cache = pl.scan_parquet(CACHE_PATH)

            bounds = cache.select(
                pl.col("time").min().alias("cached_min"),
                pl.col("time").max().alias("cached_max"),
            ).collect()
            cached_min = bounds["cached_min"][0]
            cached_max = bounds["cached_max"][0]

            result = cache.filter(
                (pl.col("time") >= max(start_date, cached_min))
                & (pl.col("time") <= min(cached_max, end_date))
            )

            new_parts = []

            if start_date < cached_min:
                part = _fetch_weather_data(start_date, cached_min)
                new_parts.append(part)
                result = pl.concat(
                    [part.lazy(), result], how="diagonal_relaxed"
                ).unique(subset=["time"], keep="last")

            if end_date > cached_max:
                part = _fetch_weather_data(cached_max, end_date)
                new_parts.append(part)
                result = pl.concat(
                    [result, part.lazy()], how="diagonal_relaxed"
                ).unique(subset=["time"], keep="last")

            if new_parts:
                _merge_into_cache(pl.concat(new_parts, how="diagonal_relaxed"))

            return result

        new_data = _fetch_weather_data(start_date, end_date)
        _merge_into_cache(new_data)
        return new_data.lazy()
