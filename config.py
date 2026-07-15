from pathlib import Path

ROOT = Path(__file__).resolve().parent

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
WEATHER_DIR = DATA_DIR / "weather"

for _dir in [RAW_DIR, PROCESSED_DIR, WEATHER_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)
