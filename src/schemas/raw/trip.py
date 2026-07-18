import pandera.polars as pa
import polars as pl

RawTripSchema = pa.DataFrameSchema(
    {
        "started_at": pa.Column(pl.Datetime, nullable=False),
        "ended_at": pa.Column(pl.Datetime, nullable=False),
        "start_station_id": pa.Column(pl.String, nullable=True),
        "end_station_id": pa.Column(pl.String, nullable=True),
        "user_type": pa.Column(pl.String, nullable=True),
        "birth_year": pa.Column(pl.Int64, nullable=True),
        "gender": pa.Column(pl.Int64, nullable=True),
        "postal_code": pa.Column(pl.Int64, nullable=True),
    }
)
