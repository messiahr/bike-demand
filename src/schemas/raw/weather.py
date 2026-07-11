import pandera.polars as pa
import polars as pl

RawWeatherSchema = pa.DataFrameSchema(
    {
        "time": pa.Column(pl.Datetime, nullable=False),
        "temp": pa.Column(pl.Float64, nullable=True),
        "dwpt": pa.Column(pl.Float64, nullable=True),
        "rhu": pa.Column(pl.Float64, nullable=True),
        "prcp": pa.Column(pl.Float64, nullable=True),
        "snow": pa.Column(pl.Float64, nullable=True),
        "wdir": pa.Column(pl.Float64, nullable=True),
        "wspd": pa.Column(pl.Float64, nullable=True),
        "wpgt": pa.Column(pl.Float64, nullable=True),
        "pres": pa.Column(pl.Float64, nullable=True),
        "tsun": pa.Column(pl.Float64, nullable=True),
        "coco": pa.Column(pl.Float64, nullable=True),
    }
)
