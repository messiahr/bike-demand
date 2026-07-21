from datetime import datetime, timedelta

import matplotlib as mpl
import numpy as np
import polars as pl
import pydeck as pdk
import streamlit as st

from src.adapters.model_repository import ModelRepository
from src.adapters.processed_data_repository import ProcessedDataRepository
from src.services.model_training import (
    FEATURE_COLS,
    WEATHER_NULL_FILL,
)

processed_data_repository = ProcessedDataRepository()
model_repository = ModelRepository()
DATA_PATH = processed_data_repository.data_path
BOSTON_CENTER = (42.3601, -71.0589)

st.set_page_config(
    page_title="Boston Bike Demand Prediction",
    layout="wide",
)

st.title("Boston Bluebikes Demand Prediction")
st.caption(
    "Column height = actual trips. "
    "Colour = prediction error — blue for under-predicted, white for accurate, "
    "red for over-predicted."
)

if not processed_data_repository.exists():
    st.error("Data file not found in S3.")
    st.stop()

if not model_repository.exists():
    st.error("No trained model found in S3.")
    st.stop()


@st.cache_resource
def load_model():
    return model_repository.load()


model = load_model()


@st.cache_data(ttl=3600)
def load_prediction_data(path: str, start: datetime, end: datetime) -> pl.DataFrame:
    lf = pl.scan_parquet(path).filter(pl.col("started_at").is_between(start, end))

    data = (
        lf.group_by(
            pl.col("started_at").dt.truncate("1h").alias("datetime"),
            pl.col("start_station_name").alias("station"),
        )
        .agg(
            pl.len().alias("actual"),
            pl.col("start_lat").first().alias("lat"),
            pl.col("start_lng").first().alias("lng"),
            pl.col("start_station_total_docks").first().alias("total_docks"),
            *[pl.col(c).first() for c in WEATHER_NULL_FILL],
        )
        .with_columns(
            pl.col("datetime").dt.hour().alias("hour"),
            pl.col("datetime").dt.weekday().alias("weekday"),
            pl.col("datetime").dt.month().alias("month"),
            pl.col("datetime").dt.year().alias("year"),
            pl.col("datetime").dt.weekday().is_in([5, 6]).alias("is_weekend"),
            *[pl.col(col).fill_null(fill) for col, fill in WEATHER_NULL_FILL.items()],
        )
        .drop_nulls()
        .sort("datetime")
        .collect()
    )

    if data.height == 0:
        return data.with_columns(
            pl.Series("predicted", [], dtype=pl.Int64),
            pl.Series("error", [], dtype=pl.Int64),
        )

    features = data.select(FEATURE_COLS).to_numpy()
    predictions = model.predict(features)
    predicted_series = pl.Series("predicted", np.clip(predictions, 0, None).round().astype(int))
    return data.with_columns(
        predicted_series,
        (predicted_series - pl.col("actual")).alias("error"),
    )


st.sidebar.header("Filters")

today = datetime.now()
prev_month_last = today.replace(day=1) - timedelta(days=1)
prev_month_first = prev_month_last.replace(day=1)

date_range = st.sidebar.date_input(
    "Date range",
    value=(prev_month_first.date(), prev_month_last.date()),
)

if not isinstance(date_range, tuple) or len(date_range) != 2:
    st.info("Select both a start and end date in the sidebar to begin.")
    st.stop()

start_d, end_d = date_range
start_dt = datetime.combine(start_d, datetime.min.time())
end_dt = datetime.combine(end_d, datetime.min.time()) + timedelta(days=1) - timedelta(seconds=1)

with st.spinner("Computing predictions..."):
    data = load_prediction_data(str(DATA_PATH), start_dt, end_dt)

if data.height == 0:
    st.warning("No data available for the selected date range.")
    st.stop()

min_dt: datetime = data["datetime"].min()
max_dt: datetime = data["datetime"].max()

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
    f"**{selected_dt.strftime('%Y-%m-%d %H:00')}**  &nbsp;&mdash;&nbsp;  "
    f"{hour_data.height} stations &nbsp;|&nbsp; "
    f"{int(hour_data['actual'].sum()):,} actual trips &nbsp;|&nbsp; "
    f"{int(hour_data['predicted'].sum()):,} predicted trips"
)

if hour_data.height == 0:
    st.info("No data available for this hour.")
    st.stop()

error_vals = hour_data["error"]
abs_max = max(int(abs(error_vals.min())), int(abs(error_vals.max())), 1)

cmap = mpl.colormaps["RdBu"]
norm = mpl.colors.TwoSlopeNorm(vmin=-abs_max, vcenter=0, vmax=abs_max)

norm_vals = norm(error_vals.to_numpy())
rgba_vals = [[round(r), round(g), round(b), 180] for [r, g, b, _] in cmap(norm_vals) * 255]

hour_data_pd = hour_data.with_columns(pl.col("station").str.to_titlecase()).to_pandas()
hour_data_pd["fill_color"] = rgba_vals

actual_vals = hour_data_pd["actual"]
elevation_scale = 5 if actual_vals.max() > 50 else 30 if actual_vals.max() > 10 else 100

layer = pdk.Layer(
    "ColumnLayer",
    hour_data_pd,
    get_position=["lng", "lat"],
    get_elevation="actual",
    elevation_scale=elevation_scale,
    radius=60,
    get_fill_color="fill_color",
    get_line_color=[255, 255, 255, 100],
    get_line_width=1,
    pickable=True,
    auto_highlight=True,
    extruded=True,
    coverage=0.8,
)

deck = pdk.Deck(
    layers=[layer],
    initial_view_state=pdk.ViewState(
        latitude=BOSTON_CENTER[0],
        longitude=BOSTON_CENTER[1],
        zoom=12,
        pitch=50,
        bearing=20,
    ),
    tooltip={
        "html": ("<b>{station}</b><br>Actual: {actual} trips<br>Predicted: {predicted} trips")
    },
    map_provider="carto",
    map_style="light",
)

st.pydeck_chart(deck, width="stretch")

st.markdown(
    """
<style>
.legend-bar {
    height: 14px;
    border-radius: 7px;
    background: linear-gradient(to right, #2166ac, #f7f7f7, #b2182b);
    margin-top: 4px;
}
</style>
<div class="legend-bar"></div>
<div style="display:flex;justify-content:space-between;font-size:0.8rem;color:#888;margin-top:2px">
    <span>Under-predicted</span><span>Accurate</span><span>Over-predicted</span>
</div>
""",
    unsafe_allow_html=True,
)

with st.sidebar.expander("About this app"):
    st.markdown("""
    **Boston Bluebikes Demand Prediction** compares actual bike-share trip
    counts against machine-learning predictions for every station-hour.

    **Model** — LightGBM regressor with hyperparameters tuned via Optuna
    and tracked in MLflow. Features include station, weather, and date information.

    **Data** — Bluebikes trip records joined with weather observations from Meteostat.
    """)
