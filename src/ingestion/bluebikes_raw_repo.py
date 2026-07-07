import abc
import zipfile
from pathlib import Path

import polars as pl
from tqdm import tqdm

from config import RAW_DIR
from src.ingestion.s3 import download, list_bucket_files, sanitize_csv

BUCKET_URL = "https://s3.amazonaws.com/hubway-data/"
STATIONS_CSV = "Hubway_Stations_as_of_July_2017.csv"

# changing to match 2023/04 schema shift
COLUMN_MAPPING = {
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


class AbstractRawTripRepo(abc.ABC):
    """Abstract base class for a raw data repository for Bluebikes data.

    This class returns builders when possible to take advantage of lazy evaluation.
    Builders are callables that return a polars.LazyFrame when called."""

    @abc.abstractmethod
    def update(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def trips_builder(self) -> pl.LazyFrame:
        raise NotImplementedError

    @abc.abstractmethod
    def stations_builder(self) -> pl.LazyFrame:
        raise NotImplementedError


class BlueBikesRepo(AbstractRawTripRepo):
    def update(self) -> None:
        """Ingest all files from the bucket in data/raw/zip and data/raw."""
        keys = list_bucket_files(BUCKET_URL)

        if not keys:
            raise ValueError("No files found in bucket.")

        for key in tqdm(keys, desc="󱄟 Ingesting", bar_format="{desc}: |{bar}| {percentage:.1f}%"):
            if ".zip" in key:
                zip_path = download(f"{BUCKET_URL}{key}", RAW_DIR / "zip" / Path(key).name)
                with zipfile.ZipFile(zip_path) as zf:
                    csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
                    for name in csv_names:  # Extract CSV to data/raw/ (keeps raw directory as
                        csv_filename = Path(name).name
                        csv_path = RAW_DIR / csv_filename
                        csv_path.parent.mkdir(parents=True, exist_ok=True)
                        if not csv_path.exists():
                            with zf.open(name) as f:
                                csv_path.write_bytes(f.read())
                            sanitize_csv(csv_path)
            else:
                download(f"{BUCKET_URL}{key}", RAW_DIR / Path(key).name)
                sanitize_csv(RAW_DIR / Path(key).name)

    def _scan_files(self) -> list[pl.LazyFrame]:
        return [
            # \N is an SQLite artifact
            pl.scan_csv(path, null_values=["\\N"]).rename(COLUMN_MAPPING, strict=False)
            for path in RAW_DIR.glob("*.csv")
            if "trip" in path.name and not path.name.startswith(".")
        ]

    def _normalize_columns(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        return lf.rename(COLUMN_MAPPING, strict=False)

    def _clean_datetimes(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        return lf.with_columns(
            pl.col("started_at").str.strptime(pl.Datetime, "%Y-%m-%d %H:%M:%S%.f", strict=False),
            pl.col("ended_at").str.strptime(pl.Datetime, "%Y-%m-%d %H:%M:%S%.f", strict=False),
        )

    def trips_builder(self) -> pl.LazyFrame:
        lf = (
            pl.concat(self._scan_files(), rechunk=True, how="diagonal_relaxed")
            .pipe(self._normalize_columns)
            .pipe(self._clean_datetimes)
            .select(
                [
                    "started_at",
                    "ended_at",
                    "start_station_name",
                    "end_station_name",
                    "member_casual",
                    "birth_year",
                    "gender",
                    "postal_code",
                ]
            )
        )

        return lf

    def stations_builder(self) -> pl.LazyFrame:
        return pl.scan_csv(
            # \N is an SQLite artifact
            RAW_DIR / STATIONS_CSV,
            null_values=["\\N"],
        )
