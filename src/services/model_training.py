import polars as pl
FEATURE_COLS = [
    "hour",
    "weekday",
    "month",
    "year",
    "is_weekend",
    "total_docks",
    "lat",
    "lng",
    "temp",
    "rhu",
    "prcp",
    "wspd",
    "wdir",
    "snow",
]

_WEATHER_NULL_FILL: dict[str, int | pl.Expr] = {
    "prcp": 0,
    "snow": 0,
    "temp": pl.col("temp").mean(),
    "rhu": pl.col("rhu").mean(),
    "wspd": pl.col("wspd").mean(),
    "wdir": pl.col("wdir").mean(),
}


def engineer_features(df: pl.LazyFrame) -> pl.DataFrame:
    return (
        df.group_by(
            pl.col("started_at").dt.truncate("1h").alias("datetime"),
            pl.col("start_station_name").alias("station"),
        )
        .agg(
            pl.len().alias("demand"),
            pl.col("start_lat").first().alias("lat"),
            pl.col("start_lng").first().alias("lng"),
            pl.col("start_station_total_docks").first().alias("total_docks"),
            *[pl.col(c).first() for c in _WEATHER_NULL_FILL],
        )
        .with_columns(
            pl.col("datetime").dt.hour().alias("hour"),
            pl.col("datetime").dt.weekday().alias("weekday"),
            pl.col("datetime").dt.month().alias("month"),
            pl.col("datetime").dt.year().alias("year"),
            pl.col("datetime").dt.weekday().is_in([5, 6]).alias("is_weekend"),
            *[pl.col(col).fill_null(fill) for col, fill in _WEATHER_NULL_FILL.items()],
        )
        .drop_nulls()
        .sort("datetime")
        .collect()
    )


