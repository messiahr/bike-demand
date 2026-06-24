import polars as pl

from config import PROCESSED_DIR, RAW_DIR
from pipelines.bluebikes.column_mapping import (
    COLUMN_MAPPING,
    CUSTOMER_MAP,
    FINAL_COLUMNS,
    GENDER_MAP,
)


def process_trips(lf: pl.LazyFrame) -> pl.LazyFrame:
    return lf.pipe(standardize_columns).pipe(clean_values).pipe(select_columns)


def standardize_columns(lf: pl.LazyFrame) -> pl.LazyFrame:
    return lf.rename(COLUMN_MAPPING, strict=False)


def clean_values(lf: pl.LazyFrame) -> pl.LazyFrame:
    # Get columns
    columns = lf.collect_schema().names()

    # Parse datetimes
    for time in ["started_at", "ended_at"]:
        if time in columns:
            lf = lf.with_columns(
                pl.col(time)
                .str.strptime(pl.Datetime, "%Y-%m-%d %H:%M:%S%.f", strict=False)
                .dt.truncate("1s")
                .alias(time),
            )

    # Standardize names for (un)subscribed customers
    if "member_casual" in columns:
        lf = lf.with_columns(pl.col("member_casual").replace(CUSTOMER_MAP))

    # Parse birth_year as Int32 (nullable)
    if "birth_year" in columns:
        lf = lf.with_columns(pl.col("birth_year").cast(pl.Int32, strict=False))

    # Convert gender to String
    if "gender" in columns:
        lf = lf.with_columns(pl.col("gender").replace(GENDER_MAP))

    # Parse ZIP code as Int32 (nullable)
    if "postal_code" in columns:
        lf = lf.with_columns(pl.col("postal_code").cast(pl.Int32, strict=False))

    # Remove rows missing critical fields
    critical = ["start_station_id", "end_station_id", "started_at", "ended_at"]
    for col in critical:
        if col in columns:
            lf.drop_nulls(subset=[col])

    return lf


def select_columns(lf: pl.LazyFrame) -> pl.LazyFrame:
    return lf.select([c for c in FINAL_COLUMNS if c in lf.collect_schema().names()])


# TODO: replace with repository model
if __name__ == "__main__":
    lfs = []

    for path in sorted([p for p in RAW_DIR.glob("*csv") if not p.name.startswith(".")]):
        lf = pl.scan_csv(path, infer_schema_length=False, null_values=["\\N"])
        lfs.append(process_trips(lf))

    lf = pl.concat(lfs, how="diagonal_relaxed")

    lf.sink_parquet(PROCESSED_DIR / "trips.parquet")
