from collections.abc import Callable

import polars as pl

from src.ingestion.bluebikes_repository import BlueBikesRepository

STATION_ALIASES = {
    "lafayette sq at mass ave main st columbia st": "mass ave lafayette sq",
    "forsyth st at huntington ave": "northeastern u n parking lot",
    "prudential center belvidere": "prudential center belvedere st",
    "harvard u gund hall at quincy st kirkland s": "harvard u gund hall at quincy st kirkland st",
    "mass ave at boylston st": "boylston st at mass ave",
    "commonwealth ave at griggs st": "allston green district griggs st at commonwealth ave",
    "child street at brian p murphy staircase": "brian p murphy staircase at child street",
}

LITERAL_REPLACEMENTS = {
    ".": "",
    "&": " and ",
    "@": " at ",
    "'": "",
    "-": " ",
    "\\": " ",
    "/": " ",
    "(former)": "",
}

WORD_REPLACEMENTS = {
    "north": "n",
    "south": "s",
    "east": "e",
    "west": "w",
    "massachusetts": "mass",
    "university": "u",
    "street": "st",
    "avenue": "ave",
    "boulevard": "blvd",
    "place": "pl",
    "drive": "dr",
    "road": "rd",
    "park": "pk",
    "center": "ctr",
    "square": "sq",
    "station": "",
}


def apply_literal_replacements(expr: pl.Expr) -> pl.Expr:
    for old, new in LITERAL_REPLACEMENTS.items():
        expr = expr.str.replace_all(old, new, literal=True)
    return expr


def clean_names(names: pl.Expr) -> pl.Expr:
    return (
        names.str.to_lowercase()
        .pipe(apply_literal_replacements)
        .str.split(" ")
        .list.eval(pl.element().replace(WORD_REPLACEMENTS).filter(pl.element() != ""))
        .list.join(" ")
        .replace(STATION_ALIASES)
    )


def get_station_map(stations: pl.LazyFrame) -> dict[str, str]:
    names = (
        stations.select("station_name")
        .unique()
        .with_columns(pl.col("station_name").pipe(clean_names).alias("clean_station_name"))
    ).collect()

    return dict(zip(names["station_name"], names["clean_station_name"], strict=True))


def normalize_stations(station_mapping: dict[str, str], stations: pl.LazyFrame) -> pl.LazyFrame:
    return stations.select(
        ["station_name", "total_docks", "station_version", "public", "district"]
    ).with_columns(pl.col("station_name").replace(station_mapping))


def normalize_trips(
    station_version_expr: Callable[[str], pl.Expr],
    station_mapping: dict[str, str],
    trips: pl.LazyFrame,
) -> pl.LazyFrame:
    return trips.with_columns(
        station_version_expr("started_at").alias("start_station_version"),
        station_version_expr("ended_at").alias("end_station_version"),
        pl.col("start_station_name").replace(station_mapping),
        pl.col("end_station_name").replace(station_mapping),
    )


def join_trips_and_stations(
    trips_modified: pl.LazyFrame,
    stations_modified: pl.LazyFrame,
) -> pl.LazyFrame:
    result = trips_modified
    for start_or_end in ["start", "end"]:
        station_col = f"{start_or_end}_station_name"
        stations_renamed = stations_modified.rename(
            {
                "station_name": station_col,
                "station_version": f"{start_or_end}_station_version",
                "total_docks": f"{start_or_end}_station_total_docks",
                "public": f"{start_or_end}_station_public",
                "district": f"{start_or_end}_district",
            }
        )
        result = result.join(
            stations_renamed, on=[station_col, f"{start_or_end}_station_version"], how="left"
        )
    return result


if __name__ == "__main__":
    bb_repo = BlueBikesRepository()

    bb_repo.update()
    bb_stations = bb_repo.stations()
    bb_trips = bb_repo.trips()

    bb_station_version_expr = bb_repo.get_station_version_expr
    bb_station_map = get_station_map(bb_stations)

    bb_stations_modified = normalize_stations(station_mapping=bb_station_map, stations=bb_stations)

    bb_trips_modified = normalize_trips(
        station_version_expr=bb_station_version_expr, station_mapping=bb_station_map, trips=bb_trips
    )

    final = join_trips_and_stations(
        trips_modified=bb_trips_modified, stations_modified=bb_stations_modified
    )

    print(final.head(10).collect())
