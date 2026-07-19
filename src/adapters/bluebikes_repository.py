import json
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

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


_STATION_SNAPSHOTS = [
    StationSnapshot(0, "Hubway_Stations_2011_2016.csv", datetime(2011, 7, 28)),
    StationSnapshot(1, "previous_Hubway_Stations_as_of_July_2017.csv", datetime(2017, 7, 1)),
    StationSnapshot(2, "Hubway_Stations_as_of_July_2017.csv", datetime(2019, 10, 30)),
]

_TRIP_COLUMN_MAPPING = {
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
    "birth year": "birth_year",
    "postal code": "postal_code",
}

_STATION_COLUMN_MAPPING = {
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

_CSV_DATETIME = "%Y-%m-%d %H:%M:%S%.f"
_MANIFEST_PATH = PROCESSED_DIR / "trips_manifest.json"


def _trip_csv_paths() -> list[Path]:
    return sorted(
        p for p in RAW_DIR.glob("*.csv") if "trip" in p.name and not p.name.startswith(".")
    )


def _load_manifest() -> dict[str, int]:
    if _MANIFEST_PATH.exists():
        return cast("dict[str, int]", json.loads(_MANIFEST_PATH.read_text()))
    return {}


def _save_manifest(paths: list[Path]) -> None:
    manifest = {p.name: int(p.stat().st_mtime) for p in paths}
    _MANIFEST_PATH.write_text(json.dumps(manifest))


def _classify_paths(paths: list[Path]) -> tuple[list[Path], bool]:
    """Return (paths_to_load, needs_rebuild).

    needs_rebuild is True when any previously-ingested file has changed
    mtime, meaning the existing parquet is stale and must be rebuilt from
    scratch to avoid duplicate rows.
    """
    manifest = _load_manifest()
    to_load: list[Path] = []
    rebuild = False
    for p in paths:
        recorded = manifest.get(p.name)
        current = int(p.stat().st_mtime)
        if recorded is None:
            to_load.append(p)
        elif recorded != current:
            to_load.append(p)
            rebuild = True
    return to_load, rebuild


def _load_trip_csv(path: Path) -> pl.LazyFrame:
    return (
        pl.scan_csv(path, null_values=["\\N"])
        .rename(_TRIP_COLUMN_MAPPING, strict=False)
        .with_columns(
            pl.col("started_at").str.strptime(pl.Datetime, _CSV_DATETIME, strict=False),
            pl.col("ended_at").str.strptime(pl.Datetime, _CSV_DATETIME, strict=False),
        )
    )


class BlueBikesRepository:
    def __init__(self) -> None:
        self.stations_path = PROCESSED_DIR / "all_stations.parquet"
        self.trips_path = PROCESSED_DIR / "all_trips.parquet"

    def stations(self) -> pl.LazyFrame:
        return pl.scan_parquet(self.stations_path)

    def trips(self) -> pl.LazyFrame:
        return pl.scan_parquet(self.trips_path)

    @staticmethod
    def get_station_version_expr(time_col: str) -> pl.Expr:
        expr = pl.lit(_STATION_SNAPSHOTS[0].version)

        for snapshot in _STATION_SNAPSHOTS[1:]:
            expr = (
                pl.when(pl.col(time_col) >= snapshot.effective_from)
                .then(snapshot.version)
                .otherwise(expr)
            )

        return expr.alias("station_version")

    def update_trips(self) -> None:
        all_paths = _trip_csv_paths()
        if not all_paths:
            return

        if self.trips_path.exists():
            to_load, rebuild = _classify_paths(all_paths)
            if not to_load:
                return
        else:
            to_load, rebuild = all_paths, True

        if rebuild:
            frames = [_load_trip_csv(p) for p in all_paths]
        else:
            frames = [pl.scan_parquet(self.trips_path)] + [_load_trip_csv(p) for p in to_load]

        pl.concat(frames, rechunk=True, how="diagonal_relaxed").sink_parquet(self.trips_path)
        _save_manifest(all_paths)

    def update_stations(self) -> None:
        pl.concat(
            [
                pl.scan_csv(RAW_DIR / s.filename, null_values=["\\N"])
                .rename(_STATION_COLUMN_MAPPING, strict=False)
                .with_columns(
                    pl.lit(s.version).alias("station_version"),
                    pl.lit(s.effective_from).alias("effective_from"),
                )
                for s in _STATION_SNAPSHOTS
            ],
            rechunk=True,
            how="diagonal_relaxed",
        ).sink_parquet(self.stations_path)

    def update(self) -> None:
        self.download()
        self.update_trips()
        self.update_stations()

    def download(self) -> None:
        keys = list_bucket_files(BUCKET_URL)
        if not keys:
            raise ValueError("No files found in bucket.")

        with ThreadPoolExecutor(max_workers=8) as exc:
            futures = {exc.submit(self._download_one, key): key for key in keys}
            for future in as_completed(futures):
                future.result()

    @staticmethod
    def _download_one(key: str) -> None:
        if ".zip" in key:
            zip_path = download(f"{BUCKET_URL}{key}", RAW_DIR / "zip" / Path(key).name)
            with zipfile.ZipFile(zip_path) as zf:
                for name in zf.namelist():
                    if not name.endswith(".csv"):
                        continue
                    dest = RAW_DIR / Path(name).name
                    if dest.exists():
                        continue
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(zf.read(name))
                    sanitize_csv(dest)
        else:
            dest = RAW_DIR / Path(key).name
            download(f"{BUCKET_URL}{key}", dest)
            sanitize_csv(dest)
