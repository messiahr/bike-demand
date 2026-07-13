from datetime import datetime

import polars as pl

from src.processing.standardize_bluebikes_data import (
    apply_literal_replacements,
    clean_names,
    get_station_map,
    join_trips_and_stations,
    normalize_stations,
    normalize_trips,
    standardize_stations,
)

# ---------------------------------------------------------------------------
# apply_literal_replacements
# ---------------------------------------------------------------------------


def test_apply_literal_replacements_at_symbol() -> None:
    result = pl.DataFrame({"n": ["main@tech"]}).with_columns(
        apply_literal_replacements(pl.col("n")).alias("out")
    )
    assert result["out"][0] == "main at tech"


def test_apply_literal_replacements_mixed_symbols() -> None:
    result = pl.DataFrame({"n": ["A&B C.D"]}).with_columns(
        apply_literal_replacements(pl.col("n")).alias("out")
    )
    assert result["out"][0] == "A and B CD"


# ---------------------------------------------------------------------------
# clean_names
# ---------------------------------------------------------------------------


def test_clean_names_all_steps_combined() -> None:
    names = pl.Series(["Prudential Center Belvidere"])
    result = pl.DataFrame({"name": names}).with_columns(
        clean_names(pl.col("name")).alias("cleaned")
    )
    assert result["cleaned"][0] == "prudential center belvedere st"


def test_clean_names_multiple_aliases() -> None:
    working_aliases = {
        "lafayette sq at mass ave main st columbia st": "mass ave lafayette sq",
        "forsyth st at huntington ave": "northeastern u n parking lot",
        "prudential center belvidere": "prudential center belvedere st",
        "harvard u gund hall at quincy st kirkland s": "harvard u gund hall at quincy st kirkland st",
        "mass ave at boylston st": "boylston st at mass ave",
        "commonwealth ave at griggs st": "allston green district griggs st at commonwealth ave",
        "child street at brian p murphy staircase": "brian p murphy staircase at child st",
    }
    names = pl.Series(list(working_aliases.keys()))
    result = pl.DataFrame({"name": names}).with_columns(
        clean_names(pl.col("name")).alias("cleaned")
    )
    for i, (raw, expected) in enumerate(working_aliases.items()):
        assert result["cleaned"][i] == expected, f"Alias mismatch for {raw}"


# ---------------------------------------------------------------------------
# get_station_map
# ---------------------------------------------------------------------------


def test_get_station_map_basic() -> None:
    stations = pl.LazyFrame(
        {
            "station_name": ["Mass Ave At Boylston St", "Central Square"],
        }
    )
    mapping = get_station_map(stations)

    assert mapping["Mass Ave At Boylston St"] == "boylston st at mass ave"
    assert mapping["Central Square"] == "central sq"


def test_get_station_map_deduplicates_names() -> None:
    stations = pl.LazyFrame(
        {
            "station_name": ["Mass Ave At Boylston St", "Mass Ave At Boylston St"],
        }
    )
    mapping = get_station_map(stations)

    assert len(mapping) == 1
    assert "Mass Ave At Boylston St" in mapping


# ---------------------------------------------------------------------------
# normalize_stations
# ---------------------------------------------------------------------------


def test_normalize_stations_selects_columns() -> None:
    stations = pl.LazyFrame(
        {
            "station_name": ["A"],
            "total_docks": [10],
            "station_version": [0],
            "public": [True],
            "district": ["Boston"],
            "extra_col": ["ignored"],
        }
    )
    mapping = {"A": "a_clean"}
    result = normalize_stations(mapping, stations).collect()

    assert set(result.columns) == {
        "station_name",
        "total_docks",
        "station_version",
        "public",
        "district",
    }
    assert result["station_name"][0] == "a_clean"
    assert result["total_docks"][0] == 10


# ---------------------------------------------------------------------------
# normalize_trips
# ---------------------------------------------------------------------------


def _dummy_version_expr(time_col: str) -> pl.Expr:
    return pl.lit(0).alias("station_version")


def test_normalize_trips_maps_station_names() -> None:
    trips = pl.LazyFrame(
        {
            "started_at": [datetime(2024, 1, 1, 12, 0)],
            "ended_at": [datetime(2024, 1, 1, 12, 30)],
            "start_station_name": ["Mass Ave At Boylston St"],
            "end_station_name": ["Central Square"],
            "usertype": ["subscriber"],
            "gender": ["1"],
        }
    )
    mapping = get_station_map(
        pl.LazyFrame({"station_name": ["Mass Ave At Boylston St", "Central Square"]})
    )
    result = normalize_trips(_dummy_version_expr, mapping, trips).collect()

    assert result["start_station_name"][0] == "boylston st at mass ave"
    assert result["end_station_name"][0] == "central sq"


def test_normalize_trips_maps_usertype() -> None:
    trips = pl.LazyFrame(
        {
            "started_at": [datetime(2024, 1, 1, 12, 0)] * 4,
            "ended_at": [datetime(2024, 1, 1, 12, 30)] * 4,
            "start_station_name": ["X"] * 4,
            "end_station_name": ["Y"] * 4,
            "usertype": ["subscriber", "customer", "member", "casual"],
            "gender": ["0", "0", "0", "0"],
        }
    )
    mapping = {"X": "x", "Y": "y"}
    result = normalize_trips(_dummy_version_expr, mapping, trips).collect()

    assert result["usertype"].to_list() == ["member", "casual", "member", "casual"]


def test_normalize_trips_maps_gender() -> None:
    trips = pl.LazyFrame(
        {
            "started_at": [datetime(2024, 1, 1, 12, 0)] * 3,
            "ended_at": [datetime(2024, 1, 1, 12, 30)] * 3,
            "start_station_name": ["X"] * 3,
            "end_station_name": ["Y"] * 3,
            "usertype": ["member"] * 3,
            "gender": ["0", "1", "2"],
        }
    )
    mapping = {"X": "x", "Y": "y"}
    result = normalize_trips(_dummy_version_expr, mapping, trips).collect()

    assert result["gender"].to_list() == ["unknown", "male", "female"]


def test_normalize_trips_adds_station_version_columns() -> None:
    def version_expr(time_col: str) -> pl.Expr:
        return pl.col(time_col).dt.year().alias("station_version")

    trips = pl.LazyFrame(
        {
            "started_at": [datetime(2024, 1, 1, 12, 0)],
            "ended_at": [datetime(2024, 6, 15, 12, 0)],
            "start_station_name": ["X"],
            "end_station_name": ["Y"],
            "usertype": ["member"],
            "gender": ["0"],
        }
    )
    mapping = {"X": "x", "Y": "y"}
    result = normalize_trips(version_expr, mapping, trips).collect()

    assert "start_station_version" in result.columns
    assert "end_station_version" in result.columns


# ---------------------------------------------------------------------------
# join_trips_and_stations
# ---------------------------------------------------------------------------


def test_join_trips_and_stations_left_join_preserves_trips() -> None:
    trips = pl.LazyFrame(
        {
            "started_at": [datetime(2024, 1, 1, 12, 0)],
            "ended_at": [datetime(2024, 1, 1, 12, 30)],
            "start_station_name": ["a"],
            "end_station_name": ["missing_station"],
            "start_station_version": [0],
            "end_station_version": [0],
        }
    )
    stations = pl.LazyFrame(
        {
            "station_name": ["a"],
            "station_version": [0],
            "total_docks": [10],
            "public": [True],
            "district": ["Boston"],
        }
    )
    result = join_trips_and_stations(trips, stations).collect()

    assert result.shape[0] == 1
    assert result["start_station_total_docks"][0] == 10
    assert result["end_station_total_docks"][0] is None


def test_join_trips_and_stations_matches_both_start_and_end() -> None:
    trips = pl.LazyFrame(
        {
            "started_at": [datetime(2024, 1, 1, 12, 0)],
            "ended_at": [datetime(2024, 1, 1, 12, 30)],
            "start_station_name": ["a"],
            "end_station_name": ["b"],
            "start_station_version": [0],
            "end_station_version": [0],
        }
    )
    stations = pl.LazyFrame(
        {
            "station_name": ["a", "b"],
            "station_version": [0, 0],
            "total_docks": [10, 20],
            "public": [True, False],
            "district": ["Boston", "Cambridge"],
        }
    )
    result = join_trips_and_stations(trips, stations).collect()

    assert result["start_station_total_docks"][0] == 10
    assert result["end_station_total_docks"][0] == 20
    assert result["start_district"][0] == "Boston"
    assert result["end_district"][0] == "Cambridge"


def test_join_trips_and_stations_version_filtering() -> None:
    trips = pl.LazyFrame(
        {
            "started_at": [datetime(2024, 1, 1, 12, 0)],
            "ended_at": [datetime(2024, 1, 1, 12, 30)],
            "start_station_name": ["a"],
            "end_station_name": ["a"],
            "start_station_version": [0],
            "end_station_version": [1],
        }
    )
    stations = pl.LazyFrame(
        {
            "station_name": ["a", "a"],
            "station_version": [0, 1],
            "total_docks": [10, 20],
            "public": [True, False],
            "district": ["Boston", "Boston"],
        }
    )
    result = join_trips_and_stations(trips, stations).collect()

    assert result["start_station_total_docks"][0] == 10
    assert result["end_station_total_docks"][0] == 20


# ---------------------------------------------------------------------------
# standardize_stations (integration)
# ---------------------------------------------------------------------------


def test_standardize_stations_full_pipeline() -> None:
    def version_expr(time_col: str) -> pl.Expr:
        return pl.lit(0).alias("station_version")

    stations = pl.LazyFrame(
        {
            "station_name": ["Mass Ave At Boylston St", "Central Square"],
            "total_docks": [15, 20],
            "station_version": [0, 0],
            "public": [True, False],
            "district": ["Boston", "Cambridge"],
        }
    )
    trips = pl.LazyFrame(
        {
            "started_at": [datetime(2024, 1, 1, 12, 0)],
            "ended_at": [datetime(2024, 1, 1, 12, 30)],
            "start_station_name": ["Mass Ave At Boylston St"],
            "end_station_name": ["Central Square"],
            "usertype": ["subscriber"],
            "gender": ["1"],
        }
    )

    result = standardize_stations(trips, stations, version_expr).collect()

    assert result.shape[0] == 1
    assert result["start_station_name"][0] == "boylston st at mass ave"
    assert result["end_station_name"][0] == "central sq"
    assert result["usertype"][0] == "member"
    assert result["gender"][0] == "male"
    assert result["start_station_total_docks"][0] == 15
    assert result["end_station_total_docks"][0] == 20


def test_standardize_stations_preserves_unmatched_trips() -> None:
    def version_expr(time_col: str) -> pl.Expr:
        return pl.lit(0).alias("station_version")

    stations = pl.LazyFrame(
        {
            "station_name": ["Known Station"],
            "total_docks": [12],
            "station_version": [0],
            "public": [True],
            "district": ["Boston"],
        }
    )
    trips = pl.LazyFrame(
        {
            "started_at": [datetime(2024, 1, 1, 12, 0)],
            "ended_at": [datetime(2024, 1, 1, 12, 30)],
            "start_station_name": ["Unknown Station"],
            "end_station_name": ["Known Station"],
            "usertype": ["casual"],
            "gender": ["2"],
        }
    )

    result = standardize_stations(trips, stations, version_expr).collect()

    assert result.shape[0] == 1
    assert result["start_station_total_docks"][0] is None
    assert result["end_station_total_docks"][0] == 12
