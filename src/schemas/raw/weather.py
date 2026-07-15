import pandera.polars as pa
import polars as pl

RawWeatherSchema = pa.DataFrameSchema(
    {
        "time": pa.Column(pl.Datetime, nullable=False),
        "temp": pa.Column(pl.Float64, nullable=True),
        "rhum": pa.Column(pl.Float64, nullable=True),
        "prcp": pa.Column(pl.Float64, nullable=True),
        "wdir": pa.Column(pl.Float64, nullable=True),
        "wspd": pa.Column(pl.Float64, nullable=True),
        "wpgt": pa.Column(pl.Float64, nullable=True),
        "pres": pa.Column(pl.Float64, nullable=True),
        "cldc": pa.Column(pl.Float64, nullable=True),
        "coco": pa.Column(pl.Float64, nullable=True),
    }
)
