import abc
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import polars as pl

from config import PROCESSED_DIR, RAW_DIR
from src.adapters.s3 import download, list_bucket_files, sanitize_csv

BUCKET_URL = "https://s3.amazonaws.com/hubway-data/"


# lists station files and the ranges of time they represent
# as of July 2026, the new "Hubway" file was last modified October 30th 2019
# BlueBikes began operations July 28th 2011
@dataclass(frozen=True)
class StationSnapshot:
    version: int
    filename: str
    effective_from: datetime


STATION_SNAPSHOTS = [
    StationSnapshot(0, "Hubway_Stations_2011_2016.csv", datetime(2011, 7, 28)),
    StationSnapshot(1, "previous_Hubway_Stations_as_of_July_2017.csv", datetime(2017, 7, 1)),
    StationSnapshot(2, "Hubway_Stations_as_of_July_2017.csv", datetime(2019, 10, 30)),
]

# changing to account for 2023/04 schema shift
TRIP_COLUMN_MAPPING = {
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
    "usertype": "user_type",
    "member_casual": "user_type",
    "birth year": "birth_year",
    "postal code": "postal_code",
}

STATION_COLUMN_MAPPING = {
    "Number": "station_id",
    "Name": "station_name",
    "Latitude": "lat",
    "Longitude": "lng",
    "Public": "public",
    "District": "district",
    "Total docks": "total_docks",
    "Station": "station_name",
    "Station ID": "station_id",
    "publiclyExposed": "public",
    "Municipality": "district",
    "# of Docks": "total_docks",
}


class AbstractRawTripRepo(abc.ABC):
    """Abstract base class for a raw data repository for Bluebikes data.

    This class returns builders when possible to take advantage of lazy evaluation.
    Builders are callables that return a polars.LazyFrame when called."""

    @abc.abstractmethod
    def update(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def trips(self) -> pl.LazyFrame:
        raise NotImplementedError

    @abc.abstractmethod
    def stations(self) -> pl.LazyFrame:
        raise NotImplementedError


class BlueBikesRepository(AbstractRawTripRepo):
    def __init__(self) -> None:
        self.stations_path = PROCESSED_DIR / "all_stations.parquet"
        self.trips_path = PROCESSED_DIR / "all_trips.parquet"

    def stations(self) -> pl.LazyFrame:
        return pl.scan_parquet(self.stations_path)

    def trips(self) -> pl.LazyFrame:
        return pl.scan_parquet(self.trips_path)

    # Exposes station versioning information.

    def get_station_version_expr(self, time_col: str) -> pl.Expr:
        snapshots = sorted(
            STATION_SNAPSHOTS,
            key=lambda s: s.effective_from,
        )

        expr = pl.lit(snapshots[0].version)

        for snapshot in snapshots[1:]:
            expr = (
                pl.when(pl.col(time_col) >= snapshot.effective_from)
                .then(snapshot.version)
                .otherwise(expr)
            )

        return expr.alias("station_version")

    # Code for ingesting and compiling files.

    @staticmethod
    def _newer_than(parquet_path: Path, source_paths: list[Path]) -> bool:
        """Return True if any source file is newer than the parquet (or parquet doesn't exist)."""
        if not parquet_path.exists():
            return True
        parquet_mtime = parquet_path.stat().st_mtime
        return any(p.stat().st_mtime > parquet_mtime for p in source_paths if p.exists())

    def _scan_files(self) -> list[pl.LazyFrame]:
        return [
            # \N is an SQLite artifact
            pl.scan_csv(path, null_values=["\\N"])
            for path in RAW_DIR.glob("*.csv")
            if "trip" in path.name and not path.name.startswith(".")
        ]

    def update_trips(self) -> None:
        pl.concat(
            [
                (
                    lf.rename(TRIP_COLUMN_MAPPING, strict=False).with_columns(
                        pl.col("started_at").str.strptime(
                            pl.Datetime, "%Y-%m-%d %H:%M:%S%.f", strict=False
                        ),
                        pl.col("ended_at").str.strptime(
                            pl.Datetime, "%Y-%m-%d %H:%M:%S%.f", strict=False
                        ),
                    )
                )
                for lf in self._scan_files()
            ],
            rechunk=True,
            how="diagonal_relaxed",
        ).sink_parquet(self.trips_path)

    def update_stations(self) -> None:
        pl.concat(
            [
                pl.scan_csv(
                    # \N is an SQLite artifact
                    RAW_DIR / snapshot.filename,
                    null_values=["\\N"],
                )
                .rename(STATION_COLUMN_MAPPING, strict=False)
                .with_columns(
                    pl.lit(snapshot.version).alias("station_version"),
                    pl.lit(snapshot.effective_from).alias("effective_from"),
                )
                for snapshot in STATION_SNAPSHOTS
            ],
            rechunk=True,
            how="diagonal_relaxed",
        ).sink_parquet(self.stations_path)

    def download(self) -> None:
        keys = list_bucket_files(BUCKET_URL)

        if not keys:
            raise ValueError("No files found in bucket.")

        for key in keys:
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

    def update(self) -> None:
        """Ingest all files from the bucket in data/raw/zip and data/raw."""
        self.download()

        trip_files = [
            p for p in RAW_DIR.glob("*.csv") if "trip" in p.name and not p.name.startswith(".")
        ]
        if self._newer_than(self.trips_path, trip_files):
            self.update_trips()

        station_files = [RAW_DIR / s.filename for s in STATION_SNAPSHOTS]
        if self._newer_than(self.stations_path, station_files):
            self.update_stations()
