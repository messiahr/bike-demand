import polars as pl

from config import RAW_DIR

if __name__ == "__main__":
    data = pl.read_csv(
        RAW_DIR / "Hubway_Stations_as_of_July_2017.csv",
        null_values=["\\N"],
    )
    print(data)
