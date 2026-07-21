import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

AWS_BUCKET = os.environ.get("AWS_BUCKET", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
