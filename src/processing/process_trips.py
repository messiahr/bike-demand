CUSTOMER_MAP = {
    "member": "member",
    "casual": "casual",
    "subscriber": "member",
    "customer": "casual",
}

# https://github.com/ropensci/bikedata
# matching ISO 5218
GENDER_MAP = {"0": "unknown", "1": "male", "2": "female"}


# def process_trips(lf: pl.LazyFrame) -> pl.LazyFrame:
#     return lf.pipe(standardize_columns).pipe(clean_values).pipe(select_columns)


# def standardize_columns(lf: pl.LazyFrame) -> pl.LazyFrame:
#     return lf.rename(COLUMN_MAPPING, strict=False)

# def clean_values(lf: pl.LazyFrame) -> pl.LazyFrame:
#     # Get columns
#     columns = lf.collect_schema().names()
#
#     # Parse datetimes
#     for time in ["started_at", "ended_at"]:
#         if time in columns:
#             lf = lf.with_columns(
#                 pl.col(time)
#                 .str.strptime(pl.Datetime, "%Y-%m-%d %H:%M:%S%.f", strict=False)
#                 .dt.truncate("1s")
#                 .alias(time),
#             )
#
#     # Standardize names for (un)subscribed customers
#     if "member_casual" in columns:
#         lf = lf.with_columns(pl.col("member_casual").replace(CUSTOMER_MAP))
#
#     # Parse birth_year as Int32 (nullable)
#     if "birth_year" in columns:
#         lf = lf.with_columns(pl.col("birth_year").cast(pl.Int32, strict=False))
#
#     # Convert gender to String
#     if "gender" in columns:
#         lf = lf.with_columns(pl.col("gender").replace(GENDER_MAP))
#
#     # Parse ZIP code as Int32 (nullable)
#     if "postal_code" in columns:
#         lf = lf.with_columns(pl.col("postal_code").cast(pl.Int32, strict=False))
#
#     # Remove rows missing critical fields
#     critical = ["start_station_id", "end_station_id", "started_at", "ended_at"]
#     for col in critical:
#         if col in columns:
#             lf.drop_nulls(subset=[col])
#
#     return lf
