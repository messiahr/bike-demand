import polars as pl

from src.ingestion.bluebikes_repository import BlueBikesRepository

if __name__ == "__main__":
    bb_repo = BlueBikesRepository()

    lf = bb_repo.trips_builder()

    station_aliases = {
        "lafayette sq at mass ave main st columbia st": "mass ave lafayette sq",
        "forsyth st at huntington ave": "northeastern u n parking lot",
        "prudential center belvidere": "prudential center belvedere st",
        "harvard u gund hall at quincy st kirkland s": "harvard u gund hall at quincy st kirkland st",
        "mass ave at boylston st": "boylston st at mass ave",
        "commonwealth ave at griggs st": "allston green district griggs st at commonwealth ave",
        "child street at brian p murphy staircase": "brian p murphy staircase at child street",
    }

    def clean_names(names: pl.Expr) -> pl.Expr:
        return (
            names.str.to_lowercase()
            .str.replace_all(r"\.", "")
            .str.replace_all(r"@", " at ")
            .str.replace_all(r"&", " and ")
            .str.replace_all(r"'", "")
            .str.replace_all(r"-", " ")
            .str.replace_all(r"\\", " ")
            .str.replace_all(r"\/", " ")
            .str.replace_all(r"\(former\)", "")
            .str.replace_all(r"\bnorth\b", "n")
            .str.replace_all(r"\bsouth\b", "s")
            .str.replace_all(r"\beast\b", "e")
            .str.replace_all(r"\bwest\b", "w")
            .str.replace_all(r"\bmassachusetts\b", "mass")
            .str.replace_all(r"\bstreet\b", "st")
            .str.replace_all(r"\bavenue\b", "ave")
            .str.replace_all(r"\bboulevard\b", "blvd")
            .str.replace_all(r"\bplace\b", "pl")
            .str.replace_all(r"\bdrive\b", "dr")
            .str.replace_all(r"\broad\b", "rd")
            .str.replace_all(r"\bpark\b", "pk")
            .str.replace_all(r"\bcenter\b", "ctr")
            .str.replace_all(r"\bsquare\b", "sq")
            .str.replace_all(r"\bstation\b", "")
            .str.replace_all(r"\buniversity\b", "u")
            .str.replace_all(r"\s+", " ")
            .str.strip_chars()
            .replace(station_aliases)
        )

    clean_trip_station_names = lf.with_columns(
        pl.col("start_station_name").pipe(clean_names)
    ).select("start_station_name")

    slf = bb_repo.stations_builder()
    print(slf.collect().columns)

    clean_station_names = slf.with_columns(pl.col("station_name").pipe(clean_names))

    mlf = clean_trip_station_names.join(
        clean_station_names, left_on="start_station_name", right_on="station_name", how="anti"
    )

    print(f"{lf.select(pl.len()).collect().item()} total rows")
    print(f"{mlf.select(pl.len()).collect().item()} rows with unmatched station names")
    unmatched = (
        mlf.group_by("start_station_name")
        .agg(pl.len().alias("count"))
        .sort("count", descending=True)
    )

    clean_trip_station_names.sink_csv("data/processed/clean_names.csv")
    clean_station_names.sink_csv("data/processed/clean_station_names.csv")
    unmatched.sink_csv("data/processed/unmatched.csv")
