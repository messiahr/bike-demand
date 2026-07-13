import abc

import polars as pl

from config import PROCESSED_DIR


class AbstractProcessedDataRepository(abc.ABC):
    @abc.abstractmethod
    def save(self, processed_data: pl.LazyFrame) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def data(self) -> pl.LazyFrame:
        raise NotImplementedError


class ProcessedDataRepository(AbstractProcessedDataRepository):
    def __init__(self) -> None:
        self.data_path = PROCESSED_DIR / "processed_data.parquet"

    def save(self, processed_data: pl.LazyFrame) -> None:
        processed_data.sink_parquet(self.data_path)

    def data(self) -> pl.LazyFrame:
        return pl.scan_parquet(self.data_path)
