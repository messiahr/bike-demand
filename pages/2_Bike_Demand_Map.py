from datetime import datetime, timedelta

import numpy as np
import polars as pl
import pydeck as pdk
import streamlit as st

from config import OUTPUT_DIR

DATA_PATH = OUTPUT_DIR / "all_trips_standardized.parquet"
BOSTON_CENTER = (42.3601, -71.0589)

st.set_page_config(page_title="Bike Demand by Station", layout="wide")
st.title("Boston Bike Demand by Station")


@st.cache_data(ttl=3600)
def load_demand_data(path: str, start: datetime, end: datetime) -> pl.DataFrame:
    return (
        pl.scan_parquet(path)
        .filter(pl.col("started_at").is_between(start, end))
        .group_by(
            pl.col("started_at").dt.truncate("1h").alias("datetime"),
            pl.col("start_station_name").alias("station"),
        )
        .agg(
            pl.len().alias("demand"),
            pl.col("start_lat").first().alias("lat"),
            pl.col("start_lng").first().alias("lng"),
        )
        .drop_nulls()
        .sort("datetime")
        .collect()
    )


st.sidebar.header("Filters")
today = datetime.now()
prev_month_last = today.replace(day=1) - timedelta(days=1)
prev_month_first = prev_month_last.replace(day=1)
date_range = st.sidebar.date_input(
    "Date Range",
    value=(prev_month_first.date(), prev_month_last.date()),
)

if not isinstance(date_range, tuple) or len(date_range) != 2:
    st.info("Select both start and end dates in the sidebar to begin.")
    st.stop()

start_d, end_d = date_range
start_dt = datetime.combine(start_d, datetime.min.time())
end_dt = datetime.combine(end_d, datetime.min.time()) + timedelta(days=1) - timedelta(seconds=1)

with st.spinner("Loading demand data..."):
    data = load_demand_data(str(DATA_PATH), start_dt, end_dt)

if data.height == 0:
    st.warning("No data available for the selected date range.")
    st.stop()

min_dt: datetime = data["datetime"].min()
max_dt: datetime = data["datetime"].max()

# --- slider ---
selected_dt: datetime = st.slider(
    "Hour",
    min_value=min_dt,
    max_value=max_dt,
    value=min_dt,
    step=timedelta(hours=1),
    format="YYYY-MM-DD HH:mm",
    label_visibility="collapsed",
)

hour_data = data.filter(pl.col("datetime") == selected_dt)

st.markdown(
    f"**{selected_dt.strftime('%Y-%m-%d %H:00')}**  —  "
    f"{hour_data.height} stations · {hour_data['demand'].sum()} trips"
)

if hour_data.height == 0:
    st.info("No trips started during this hour.")
    st.stop()

