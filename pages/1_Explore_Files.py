import polars as pl
import streamlit as st

from config import RAW_DIR

st.title("Hubway Data Explorer")

# List available CSVs

csv_files = sorted(p for p in RAW_DIR.glob("*.csv") if not p.name.startswith("."))
selected = st.selectbox("Choose a file", csv_files, format_func=lambda p: p.name)

if selected:
    df = pl.scan_csv(selected).collect()
    st.write(f"**{len(df)} rows × {len(df.columns)} columns**")
    st.dataframe(df.head(100))
    st.subheader("Column Types")
    st.dataframe(pl.DataFrame({"column": df.columns, "dtype": [str(dt) for dt in df.dtypes]}))
    st.subheader("Summary Statistics")
    st.dataframe(df.describe())
