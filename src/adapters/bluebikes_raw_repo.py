import abc
import zipfile
from collections.abc import Callable
from pathlib import Path

import polars as pl
from tqdm import tqdm

from config import RAW_DIR
from src.adapters.s3 import download, list_bucket_files, sanitize_csv

BUCKET_URL = "https://s3.amazonaws.com/hubway-data/"
STATIONS_CSV = "Hubway_Stations_as_of_July_2017.csv"


class AbstractRawRepo(abc.ABC):
    """Abstract base class for a raw data repository for Bluebikes data.

    This class returns builders when possible to take advantage of lazy evaluation.
    Builders are callables that return a polars.LazyFrame when called."""

    @abc.abstractmethod
    def update(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_trips_builder(self) -> Callable[[], pl.LazyFrame]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_stations_builder(self) -> Callable[[], pl.LazyFrame]:
        raise NotImplementedError


class RawRepo(AbstractRawRepo):
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

    def get_trips_builder(self) -> Callable[[], pl.LazyFrame]:
        def trips_builder() -> pl.LazyFrame:
            return pl.concat(
                [
                    # \N is an SQLite artifact
                    pl.scan_csv(path, null_values=["\\N"])
                    for path in RAW_DIR.glob("*.csv")
                    if "trip" in path.name and not path.name.startswith(".")
                ],
                rechunk=True,
                how="diagonal_relaxed",
            )

        return trips_builder

    def get_stations_builder(self) -> Callable[[], pl.LazyFrame]:
        def stations_builder() -> pl.LazyFrame:
            return pl.scan_csv(
                # \N is an SQLite artifact
                RAW_DIR / STATIONS_CSV,
                null_values=["\\N"],
            )

        return stations_builder
