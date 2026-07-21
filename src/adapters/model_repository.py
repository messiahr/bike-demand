import pickle

import boto3
import lightgbm as lgb

from config import AWS_BUCKET, AWS_REGION

S3_KEY = "model.pickle"


class ModelRepository:
    def __init__(self) -> None:
        self._bucket = AWS_BUCKET
        self._key = S3_KEY
        self._s3 = boto3.client("s3", region_name=AWS_REGION)
        self.model_path = f"s3://{self._bucket}/{self._key}"

    def save(self, model: lgb.LGBMRegressor) -> str:
        data = pickle.dumps(model)
        self._s3.put_object(Bucket=self._bucket, Key=self._key, Body=data)
        return self.model_path

    def load(self) -> lgb.LGBMRegressor:
        response = self._s3.get_object(Bucket=self._bucket, Key=self._key)
        data = response["Body"].read()
        return pickle.loads(data)

    def exists(self) -> bool:
        try:
            self._s3.head_object(Bucket=self._bucket, Key=self._key)
            return True
        except self._s3.exceptions.ClientError:
            return False
