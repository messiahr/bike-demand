import polars as pl

from config import PROCESSED_DIR, RAW_DIR
from src.ingestion.bluebikes_raw_repo import BlueBikesRepo

if __name__ == "__main__":
    bb_repo = BlueBikesRepo()

    df = pl.read_parquet(PROCESSED_DIR / "trips.parquet")
    print(df)

    left = df.select(pl.col("start_station_id").unique().sort()).to_series().to_list()

    phs = pl.read_csv(RAW_DIR / "previous_Hubway_Stations_as_of_July_2017.csv", null_values=["\\N"])
    hs = pl.read_csv(RAW_DIR / "Hubway_Stations_2011_2016.csv", null_values=["\\N"])
    hsao = pl.read_csv(RAW_DIR / "Hubway_Stations_as_of_July_2017.csv", null_values=["\\N"])

    # right = phs.select(pl.col("station_id").unique().sort()).to_series().to_list()
    # rows = []
    # for x in left:
    #     match, score, idx = process.extractOne(x, right, scorer=fuzz.WRatio)
    #     rows.append((x, match, score))
    #
    # result = pl.DataFrame(rows, schema=["left", "right_match", "score"])
