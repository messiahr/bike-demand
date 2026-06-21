from pathlib import Path

import polars as pl
import streamlit as st

st.title("Hubway Data Explorer")

data_dir = Path("data/raw")


# List available CSVs

csv_files = sorted(p for p in data_dir.glob("*.csv") if not p.name.startswith("."))
selected = st.selectbox("Choose a file", csv_files, format_func=lambda p: p.name)

if selected:
    df = pl.scan_csv(selected).collect()
    st.write(f"**{len(df)} rows × {len(df.columns)} columns**")
    st.dataframe(df.head(100))
    st.subheader("Column Types")
    st.dataframe(pl.DataFrame({"column": df.columns, "dtype": [str(dt) for dt in df.dtypes]}))
    st.subheader("Summary Statistics")
    st.dataframe(df.describe())
