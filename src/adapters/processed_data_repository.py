import boto3
import polars as pl

from config import AWS_BUCKET, AWS_REGION


class ProcessedDataRepository:
    def __init__(self) -> None:
        self._bucket = AWS_BUCKET
        self._key = "all_trips_standardized.parquet"
        self._s3 = boto3.client("s3", region_name=AWS_REGION)
        self.data_path = f"s3://{self._bucket}/{self._key}"
        self._storage_options = {"region": AWS_REGION}

    def save(self, df: pl.LazyFrame) -> str:
        df.sink_parquet(self.data_path, storage_options=self._storage_options)
        return self.data_path

    def load(self) -> pl.LazyFrame:
        return pl.scan_parquet(self.data_path, storage_options=self._storage_options)

    def exists(self) -> bool:
        try:
            self._s3.head_object(Bucket=self._bucket, Key=self._key)
            return True
        except self._s3.exceptions.ClientError:
            return False
