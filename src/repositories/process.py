from pathlib import Path

import polars as pl
from tqdm import tqdm

from config import PROCESSED_DIR, RAW_DIR

COLUMN_MAPPING = {
    # changing to match 2023/04 schema shift
    "tripduration": "trip_duration",
    "starttime": "started_at",
    "stoptime": "ended_at",
    "start station id": "start_station_id",
    "start station name": "start_station_name",
    "start station latitude": "start_lat",
    "start station longitude": "start_lng",
    "end station id": "end_station_id",
    "end station name": "end_station_name",
    "end station latitude": "end_lat",
    "end station longitude": "end_lng",
    "bikeid": "bike_id",
    "usertype": "member_casual",
    "birth year": "birth_year",
    "postal code": "postal_code",
}

FINAL_COLUMNS = [
    "started_at",
    "ended_at",
    "start_station_id",
    "end_station_id",
    "member_casual",
    "birth_year",
    "gender",
    "postal_code",
]

CUSTOMER_MAP = {
    "member": "member",
    "casual": "casual",
    "subscriber": "member",
    "customer": "casual",
}

# https://github.com/ropensci/bikedata
# matching ISO 5218
GENDER_MAP = {"0": "unknown", "1": "male", "2": "female"}


def process_file(path: Path) -> pl.DataFrame:
    df = pl.read_csv(path, infer_schema_length=False)
    df = standardize_columns(df)
    df = clean_values(df)
    df = select_columns(df)
    return df


def standardize_columns(df: pl.DataFrame) -> pl.DataFrame:
    return df.rename(COLUMN_MAPPING, strict=False)


def clean_values(df: pl.DataFrame) -> pl.DataFrame:
    # Parse datetimes
    for time in ["started_at", "ended_at"]:
        if time in df.columns:
            df = df.with_columns(
                pl.col(time)
                .str.strptime(pl.Datetime, "%Y-%m-%d %H:%M:%S%.f", strict=False)
                .dt.truncate("1s")
                .alias(time),
            )
            print(df.head(10))

    # TODO: remap IDs before shift

    # Standardize names for (un)subscribed customers
    if "member_casual" in df.columns:
        df = df.with_columns(pl.col("member_casual").replace(CUSTOMER_MAP))

    # Parse birth_year as Int32 (nullable)
    if "birth_year" in df.columns:
        df = df.with_columns(pl.col("birth_year").cast(pl.Int32, strict=False))

    # Convert gender to String
    if "gender" in df.columns:
        df = df.with_columns(pl.col("gender").replace(GENDER_MAP))

    # Parse ZIP code as Int32 (nullable)
    if "postal_code" in df.columns:
        df = df.with_columns(pl.col("postal_code").cast(pl.Int32, strict=False))

    # Remove rows missing critical fields
    critical = ["start_station_id", "end_station_id", "started_at", "ended_at"]
    for col in critical:
        if col in df.columns:
            df.drop_nulls(subset=[col])

    return df


def select_columns(df: pl.DataFrame) -> pl.DataFrame:
    return df.select([c for c in FINAL_COLUMNS if c in df.columns])


# TODO: replace with PostgreSQL
if __name__ == "__main__":
    csv_files = sorted([p for p in RAW_DIR.glob("*csv") if not p.name.startswith(".")])
    df = pl.DataFrame()
    for path in tqdm(
        csv_files, desc="󱄟 Processing", bar_format="{desc}: |{bar}| {percentage:.1f}%"
    ):
        df = pl.concat([df, process_file(path)], how="diagonal_relaxed")
    df.write_csv(PROCESSED_DIR / "trips.csv")
