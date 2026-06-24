from pathlib import Path

import polars as pl
from tqdm import tqdm

from config import PROCESSED_DIR, RAW_DIR
from pipelines.bluebikes.column_mapping import (
    COLUMN_MAPPING,
    CUSTOMER_MAP,
    FINAL_COLUMNS,
    GENDER_MAP,
)


def process_file(path: Path) -> pl.DataFrame:
    # \\N is an artifact from MySQL
    # TODO: extract line below to repository layer
    df = pl.read_csv(path, infer_schema_length=False, null_values=["\\N"])
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
