import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="WDI → Clean Panel", layout="wide")
st.title("WDI raw CSV ➜ tidy panel")

# ---------- UPLOAD ----------
uploaded = st.file_uploader("1. Upload WDI csv", type="csv")
if uploaded is None:
    st.stop()

df_raw = pd.read_csv(uploaded)

# ---------- AUTO-DETECT ----------
country_col = None
year_col = None
for c in df_raw.columns:
    if df_raw[c].dtype == object and df_raw[c].nunique() > 50:
        country_col = c
for c in df_raw.columns:
    if pd.api.types.is_numeric_dtype(df_raw[c]):
        lo, hi = df_raw[c].min(), df_raw[c].max()
        if 1960 <= lo <= 2030 and 1960 <= hi <= 2030:
            year_col = c

# Let user override
with st.sidebar:
    country_col = st.selectbox("Country column", df_raw.columns,
                               index=df_raw.columns.get_loc(country_col) if country_col else 0)
    year_col = st.selectbox("Year column", df_raw.columns,
                            index=df_raw.columns.get_loc(year_col) if year_col else 0)

# ---------- META ----------
indicator_cols = [c for c in df_raw.columns if c not in {country_col, year_col}]
st.markdown(f"""
- **Countries** : {df_raw[country_col].nunique()}  
- **Years**     : {int(df_raw[year_col].min())} – {int(df_raw[year_col].max())}  
- **Indicators**: {len(indicator_cols)}
""")

# ---------- FILTERS ----------
with st.sidebar:
    years = sorted(df_raw[year_col].unique())
    y0 = st.selectbox("Start year", years, index=0)
    y1 = st.selectbox("End year", years, index=len(years) - 1)
    indicators = st.multiselect("Indicators", indicator_cols, default=indicator_cols[:3])
    countries = st.multiselect("Countries", sorted(df_raw[country_col].unique()),
                               default=sorted(df_raw[country_col].unique())[:5])

# ---------- SUBSET & RESHAPE ----------
panel = (df_raw
         .loc[df_raw[year_col].between(y0, y1)]
         .loc[df_raw[country_col].isin(countries)]
         .set_index([country_col, year_col])[indicators]
         .reset_index())

# ---------- DISPLAY / DOWNLOAD ----------
st.write("Preview (first 50 rows):")
st.dataframe(panel.head(50))

csv = panel.to_csv(index=False)
st.download_button(
    label="2. Download tidy panel CSV",
    data=csv,
    file_name=f"wdi_panel_{y0}_{y1}.csv",
    mime="text/csv"
)
