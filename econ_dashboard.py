
--------------------------------------------------
File 2: app.py
------------------------------------------------```python
import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="WDI → Panel", layout="wide")
st.title("WDI raw file → clean panel")

# ---------- 1. LOAD ----------
uploaded = st.file_uploader("Upload your WDI csv (or any wide csv)", type="csv")
if uploaded is None:
    st.stop()

df_raw = pd.read_csv(uploaded)

# ---------- 2. AUTO-DETECT ----------
# Heuristic: find the column with most unique values ≈ countries
country_col = None
time_col   = None
for c in df_raw.columns:
    if df_raw[c].nunique() > 50 and df_raw[c].dtype == object:
        country_col = c
        break
# Heuristic: find a year-like column
for c in df_raw.columns:
    if df_raw[c].dtype in ['int64', 'float64']:
        if df_raw[c].min() >= 1960 and df_raw[c].max() <= 2030:
            time_col = c
            break
# Fallback: let user override
with st.sidebar:
    st.markdown("### Column mapping")
    country_col = st.selectbox("Country column", df_raw.columns, index=df_raw.columns.get_loc(country_col) if country_col else 0)
    time_col   = st.selectbox("Year column",    df_raw.columns, index=df_raw.columns.get_loc(time_col)   if time_col   else 0)

# ---------- 3. META INFO ----------
st.markdown(f"""
- **Countries**: {df_raw[country_col].nunique()}  
- **Years range**: {int(df_raw[time_col].min())} – {int(df_raw[time_col].max())}  
- **Indicators (value columns)**: {len([c for c in df_raw.columns if c not in [country_col, time_col]])}
""")

# ---------- 4. USER FILTERS ----------
indicator_cols = [c for c in df_raw.columns if c not in [country_col, time_col]]
with st.sidebar:
    years       = sorted(df_raw[time_col].unique())
    year_start  = st.selectbox("Start year", years, index=0)
    year_end    = st.selectbox("End year",   years, index=len(years)-1)
    indicators  = st.multiselect("Select indicators", indicator_cols, default=indicator_cols[:3])
    countries   = st.multiselect("Select countries",  sorted(df_raw[country_col].unique()),
                                   default=sorted(df_raw[country_col].unique())[:5])

# ---------- 5. SUBSET & RESHAPE ----------
panel = (df_raw
         .loc[df_raw[time_col].between(year_start, year_end)]
         .loc[df_raw[country_col].isin(countries)]
         .set_index([country_col, time_col])[indicators]
         .reset_index())

# ---------- 6. DISPLAY & DOWNLOAD ----------
st.write("Preview of cleansed panel:")
st.dataframe(panel.head(50))

csv = panel.to_csv(index=False)
st.download_button(label="Download panel as CSV",
                   data=csv,
                   file_name=f"wdi_panel_{year_start}_{year_end}.csv",
                   mime="text/csv")
