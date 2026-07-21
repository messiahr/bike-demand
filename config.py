import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"


def _resolve(key: str, default: Any = "") -> Any:
    try:
        import streamlit as st

        return st.secrets.get(key, os.environ.get(key, default))
    except Exception:
        return os.environ.get(key, default)


AWS_BUCKET = _resolve("AWS_BUCKET", "")
AWS_REGION = _resolve("AWS_REGION", "us-east-1")
