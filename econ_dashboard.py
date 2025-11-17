# econ_dashboard.py
"""
Advanced Economic Data Explorer
 - World Bank (full indicator & country discovery)
 - FRED (search; requires API key)
 - OECD (dataflow discovery; CSV fetch by key)
 - IMF  (dataflow discovery; CompactData fetch)
Features:
 - Searchable catalogs
 - Country selectors (where available)
 - Plots (Plotly)
 - CSV / Excel downloads (safe bytes)
 - Transformations: log, pct-change, rolling mean
"""
import io
import time
from typing import Optional

import numpy as np
import pandas as pd
import requests
import streamlit as st
import plotly.express as px

# Page config
st.set_page_config(page_title="Economic Data Explorer", layout="wide")
st.title("📊 Economic Data Explorer — World Bank, FRED, OECD, IMF")

# ---------------------------
# Helpers
# ---------------------------
HEADERS = {"User-Agent": "EconDataExplorer/1.0 (research)"}

@st.cache_data(ttl=24 * 3600, show_spinner=False)
def fetch_json(url: str, params: dict | None = None, timeout: int = 30) -> dict | list | None:
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"__error__": str(e)}

@st.cache_data(ttl=24 * 3600, show_spinner=False)
def fetch_text(url: str, params: dict | None = None, timeout: int = 30) -> Optional[str]:
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception:
        return None

def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    # pandas will choose engine; xlsxwriter recommended in env
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=True, sheet_name="data")
    return buf.getvalue()

# ---------------------------
# Sidebar global controls
# ---------------------------
st.sidebar.markdown("## Global options")
transform_log = st.sidebar.checkbox("Log transform (log(x))", value=False)
transform_pct = st.sidebar.checkbox("Percent change (x_t/x_{t-1}-1)", value=False)
rolling = st.sidebar.number_input("Rolling window (periods, 0 = none)", min_value=0, value=0)

st.sidebar.markdown("---")
source = st.sidebar.selectbox("Select data source", ["World Bank", "FRED", "OECD", "IMF"])

st.sidebar.markdown("---")
st.sidebar.write("Tips: World Bank & OECD do not require API keys. FRED requires a free API key.")

# ---------------------------
# WORLD BANK: indicators, countries, fetch
# ---------------------------
@st.cache_data(ttl=24 * 3600, show_spinner=False)
def load_wb_countries():
    url = "https://api.worldbank.org/v2/country?format=json&per_page=400"
    j = fetch_json(url)
    if not j or "__error__" in j:
        return pd.DataFrame()
    df = pd.json_normalize(j[1])
    return df[['id', 'iso2Code', 'name']].rename(columns={"id": "id", "iso2Code": "iso2", "name": "name"})

@st.cache_data(ttl=24 * 3600, show_spinner=False)
def load_wb_indicators(max_pages: int = 20):
    indicators = []
    page = 1
    per_page = 200
    while page <= max_pages:
        url = f"https://api.worldbank.org/v2/indicator?format=json&per_page={per_page}&page={page}"
        j = fetch_json(url)
        if not j or "__error__" in j:
            break
        if len(j) < 2 or not j[1]:
            break
        indicators.extend(j[1])
        page += 1
    if not indicators:
        return pd.DataFrame(columns=["id", "name"])
    df = pd.json_normalize(indicators)[["id", "name"]]
    df = df.drop_duplicates(subset=["id"])
    return df

def fetch_wb_series(country_code: str, indicator_code: str, date_range: str | None = None) -> pd.DataFrame:
    url = f"https://api.worldbank.org/v2/country/{country_code}/indicator/{indicator_code}?format=json&per_page=20000"
    if date_range:
        url += f"&date={date_range}"
    j = fetch_json(url)
    if not j or "__error__" in j or len(j) < 2:
        return pd.DataFrame()
    df = pd.json_normalize(j[1])
    if df.empty:
        return pd.DataFrame()
    df = df[['date', 'value']].dropna()
    df['date'] = pd.to_numeric(df['date'], errors='coerce')
    df['value'] = pd.to_numeric(df['value'], errors='coerce')
    df = df.dropna().sort_values('date').set_index('date')
    return df

# ---------------------------
# FRED: search & fetch (requires API key)
# ---------------------------
@st.cache_data(ttl=24 * 3600, show_spinner=False)
def fred_search_api(query: str, api_key: str, limit: int = 200) -> pd.DataFrame:
    url = "https://api.stlouisfed.org/fred/series/search"
    params = {"search_text": query, "api_key": api_key, "file_type": "json", "limit": limit}
    j = fetch_json(url, params=params)
    if not j or "__error__" in j or "seriess" not in j:
        return pd.DataFrame()
    df = pd.json_normalize(j["seriess"])[["id", "title", "frequency"]]
    return df

def fred_fetch_series(series_id: str, api_key: str) -> pd.DataFrame:
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {"series_id": series_id, "api_key": api_key, "file_type": "json", "observation_start": "1900-01-01"}
    j = fetch_json(url, params=params)
    if not j or "__error__" in j or "observations" not in j:
        return pd.DataFrame()
    df = pd.DataFrame(j["observations"])
    if df.empty:
        return pd.DataFrame()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['value'] = pd.to_numeric(df['value'], errors='coerce')
    df = df.dropna(subset=['value']).set_index('date')
    return df[['value']]

# ---------------------------
# OECD: dataflows discovery (basic) and CSV fetch by dataset/key
# ---------------------------
@st.cache_data(ttl=24 * 3600, show_spinner=False)
def oecd_dataflows():
    url = "https://stats.oecd.org/restsdmx/sdmx.ashx?dataflow=all"
    # The JSON endpoint for dataflows is a bit awkward; try SDMX-JSON dataflow list
    url2 = "https://stats.oecd.org/SDMX-JSON/dataflow/ALL"
    j = fetch_json(url2)
    # Attempt to parse a variety of structures
    try:
        flows = j.get("dataflows", {}) if isinstance(j, dict) else {}
        # fallback parsing
    except Exception:
        flows = {}
    # If parsing fails, return empty DF
    # Simpler approach: user will paste the dataset key when necessary (we show documentation hint)
    return pd.DataFrame()  # placeholder: OECD catalog parsing is dataset-specific

def oecd_fetch_csv(dataset: str, key: str) -> pd.DataFrame:
    # key example: "USA.CPI.M" or similar; we expose to user as free-form input
    url = f"https://stats.oecd.org/SDMX-JSON/data/{dataset}/{key}/all?contentType=csv"
    txt = fetch_text(url)
    if not txt:
        return pd.DataFrame()
    try:
        df = pd.read_csv(io.StringIO(txt))
        return df
    except Exception:
        return pd.DataFrame()

# ---------------------------
# IMF: dataflow list & CompactData fetch (best-effort)
# ---------------------------
@st.cache_data(ttl=24 * 3600, show_spinner=False)
def imf_dataflows():
    url = "https://dataservices.imf.org/REST/SDMX_JSON.svc/Dataflow"
    j = fetch_json(url)
    if not j or "__error__" in j:
        return pd.DataFrame()
    try:
        items = j.get("Structure", {}).get("Dataflows", {}).get("Dataflow", [])
        df = pd.json_normalize(items)
        # standardize key names if present
        if 'Id' in df.columns:
            df = df.rename(columns={'Id': 'id'})
        # fallback to DataflowRef
        return df
    except Exception:
        return pd.DataFrame()

def imf_fetch_compact(db: str, series_key: str) -> pd.DataFrame:
    url = f"https://dataservices.imf.org/REST/SDMX_JSON.svc/CompactData/{db}/{series_key}"
    j = fetch_json(url)
    if not j or "__error__" in j:
        return pd.DataFrame()
    try:
        # Navigate payload: CompactData -> DataSet -> Series -> Obs
        obs = j["CompactData"]["DataSet"]["Series"]["Obs"]
        df = pd.DataFrame(obs)
        # columns might be '@TIME_PERIOD' and '@OBS_VALUE' or 'TIME_PERIOD' etc.
        time_cols = [c for c in df.columns if 'TIME' in c.upper()]
        val_cols = [c for c in df.columns if 'OBS' in c.upper() or 'VALUE' in c.upper()]
        if time_cols and val_cols:
            df2 = pd.DataFrame({
                "date": pd.to_datetime(df[time_cols[0]], errors='coerce'),
                "value": pd.to_numeric(df[val_cols[0]], errors='coerce')
            }).dropna().set_index('date')
            return df2
        else:
            return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

# ---------------------------
# UI: Main controls and flows
# ---------------------------

st.markdown("### Choose a source, search indicators/series, select country/key, then fetch and download.")

if source == "World Bank":
    st.header("World Bank Explorer")
    wb_indicators = load_wb_indicators()
    wb_countries_df = load_wb_countries()

    st.info("Search World Bank indicators by name or code (contains match). Use the country selector to pick the country.")
    search_text = st.text_input("Indicator search (e.g., GDP, inflation, population)", value="gdp")
    if st.button("Search World Bank indicators"):
        if wb_indicators.empty:
            st.error("Could not load World Bank indicators (HTTP error). Try again later.")
        else:
            matches = wb_indicators[
                wb_indicators['name'].str.contains(search_text, case=False, na=False) |
                wb_indicators['id'].str.contains(search_text, case=False, na=False)
            ]
            if matches.empty:
                st.warning("No matching indicators found. Try broader keywords.")
            else:
                # display a compact list and allow selection
                matches['label'] = matches['name'] + " (" + matches['id'] + ")"
                chosen = st.selectbox("Choose indicator", matches['label'].tolist())
                chosen_code = chosen.split("(")[-1].strip(")")
                country_choice = st.selectbox("Choose country", wb_countries_df['name'].tolist(), index=wb_countries_df['name'].tolist().index("United States") if "United States" in wb_countries_df['name'].tolist() else 0)
                country_code = wb_countries_df[wb_countries_df['name'] == country_choice]['id'].iloc[0]
                yrs_from = st.number_input("From year (YYYY)", min_value=1900, max_value=2100, value=2000)
                yrs_to = st.number_input("To year (YYYY)", min_value=1900, max_value=2100, value=int(time.strftime("%Y")))
                if st.button("Fetch World Bank series"):
                    df = fetch_wb_series(country_code, chosen_code, date_range=f"{yrs_from}:{yrs_to}")
                    if df.empty:
                        st.warning("No data returned for that indicator/country/date range.")
                    else:
                        series = df['value'].astype(float)
                        out = series.copy()
                        if transform_log:
                            out = np.log(out.replace(0, np.nan))
                        if transform_pct:
                            out = out.pct_change()
                        if rolling and rolling > 0:
                            out = out.rolling(window=rolling).mean()
                        plot_df = out.reset_index()
                        plot_df.columns = ["date", "value"]
                        fig = px.line(plot_df, x="date", y="value", labels={"date": "Year", "value": "Value"}, title=f"{chosen} — {country_choice}")
                        st.plotly_chart(fig, use_container_width=True)
                        st.dataframe(df.head(100))
                        st.download_button("Download CSV", df.to_csv().encode(), file_name=f"WB_{country_code}_{chosen_code}.csv", mime="text/csv")
                        st.download_button("Download Excel", df_to_excel_bytes(df), file_name=f"WB_{country_code}_{chosen_code}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

elif source == "FRED":
    st.header("FRED Explorer (requires API key)")
    fred_key = st.text_input("FRED API key (paste here)", type="password")
    fred_q = st.text_input("Search query (keywords, e.g., GDP, CPI)", value="GDP")
    if st.button("Search FRED") and fred_key.strip():
        res = fred_search_api(fred_q, fred_key)
        if res.empty:
            st.warning("No FRED results (check API key and query).")
        else:
            choices = [f'{r["title"]} ({r["id"]})' for _, r in res.iterrows()]
            pick = st.selectbox("Choose series", choices)
            series_id = pick.split("(")[-1].strip(")")
            if st.button("Fetch FRED series"):
                df = fred_fetch_series(series_id, fred_key)
                if df.empty:
                    st.warning("No observations returned.")
                else:
                    ser = df['value'].astype(float)
                    out = ser.copy()
                    if transform_log:
                        out = np.log(out.replace(0, np.nan))
                    if transform_pct:
                        out = out.pct_change()
                    if rolling and rolling > 0:
                        out = out.rolling(window=rolling).mean()
                    plot_df = out.reset_index().rename(columns={"index": "date", "value": "value"})
                    fig = px.line(plot_df, x="date", y="value", labels={"date": "Date", "value": "Value"}, title=series_id)
                    st.plotly_chart(fig, use_container_width=True)
                    st.dataframe(df.head(200))
                    st.download_button("Download CSV", df.to_csv().encode(), file_name=f"FRED_{series_id}.csv", mime="text/csv")
                    st.download_button("Download Excel", df_to_excel_bytes(df), file_name=f"FRED_{series_id}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

elif source == "OECD":
    st.header("OECD Explorer (basic)")
    st.info("OECD dataset discovery is complex. Use the dataset code and key (e.g., dataset='MEI', key='USA.CPI.M') and press 'Fetch'.")
    st.markdown("Find dataset codes at https://stats.oecd.org/ (use data explorer to get the dataflow/dataset code).")
    dataset = st.text_input("Dataset code (e.g., MEI)", value="MEI")
    key = st.text_input("Query key (dataset-specific, e.g., USA.CPI.M)", value="USA.CPI.M")
    if st.button("Fetch OECD CSV"):
        df = oecd_fetch_csv(dataset, key)
        if df.empty:
            st.warning("No data returned. Check dataset and key or consult OECD explorer for correct key syntax.")
        else:
            # Try to find date/value columns heuristically
            cols = df.columns.tolist()
            xcol = cols[0]
            ycol = cols[-1]
            fig = px.line(df, x=xcol, y=ycol, labels={xcol: "x", ycol: "value"}, title=f"{dataset} {key}")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df.head(200))
            st.download_button("Download CSV", df.to_csv(index=False).encode(), file_name=f"OECD_{dataset}_{key}.csv", mime="text/csv")
            st.download_button("Download Excel", df_to_excel_bytes(df), file_name=f"OECD_{dataset}_{key}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

elif source == "IMF":
    st.header("IMF Explorer (basic)")
    st.info("IMF SDMX: list dataflows to find database ids. Then fetch CompactData using db and a series key (country.indicator).")
    if st.button("List IMF dataflows (first 300)"):
        df_flow = imf_dataflows()
        if df_flow.empty:
            st.warning("Could not fetch IMF dataflows.")
        else:
            st.dataframe(df_flow.head(300))
    db = st.text_input("Database id (e.g., IFS, BOP, IFSQ)", value="IFS")
    series_key = st.text_input("Series key (country.indicator, e.g., USA.NGDP_RPCH)", value="USA.NGDP_RPCH")
    if st.button("Fetch IMF series"):
        if "." not in series_key:
            st.error("Series key must be COUNTRY.INDICATOR (e.g., USA.GDP).")
        else:
            df2 = imf_fetch_compact(db, series_key)
            if df2.empty:
                st.warning("No IMF data parsed for that key; IMF SDMX payloads are heterogeneous.")
            else:
                ser = df2['value'].astype(float)
                out = ser.copy()
                if transform_log:
                    out = np.log(out.replace(0, np.nan))
                if transform_pct:
                    out = out.pct_change()
                if rolling and rolling > 0:
                    out = out.rolling(window=rolling).mean()
                plot_df = out.reset_index().rename(columns={"index": "date", "value": "value"})
                fig = px.line(plot_df, x="date", y="value", title=f"IMF {db} {series_key}")
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df2.head(200))
                st.download_button("Download CSV", df2.to_csv().encode(), file_name=f"IMF_{db}_{series_key}.csv", mime="text/csv")
                st.download_button("Download Excel", df_to_excel_bytes(df2), file_name=f"IMF_{db}_{series_key}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# Footer tips
st.markdown("---")
st.write("Notes: 1) Validate units/frequency before using series in models.  2) FRED requires an API key (free). 3) OECD and IMF SDMX endpoints are flexible — you may need to use their online explorers to build correct keys.")
