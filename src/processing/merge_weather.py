import polars as pl


def merge_trips_with_weather(
    trips: pl.LazyFrame,
    weather: pl.LazyFrame,
) -> pl.LazyFrame:
    trips_with_hour = trips.with_columns(
        pl.col("started_at").dt.truncate("1h").alias("weather_hour")
    )
    weather_renamed = weather.rename({"time": "weather_hour"})

    result = trips_with_hour.join(weather_renamed, on="weather_hour", how="left").drop(
        "weather_hour"
    )

    return result
