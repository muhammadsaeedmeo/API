# advanced_econ_dashboard.py
"""
Advanced Global Economic & Financial Data Dashboard (single file)

Save as: advanced_econ_dashboard.py
Run: streamlit run advanced_econ_dashboard.py

Features:
 - World Bank: country dropdown, searchable indicator list, plot, CSV/Excel download
 - FRED: search series (requires API key), pick series, plot, CSV/Excel download
 - OECD: dataset/filters (basic), plot and download (CSV/Excel)
 - IMF (basic): list dataflows and fetch compact data (best-effort)
 - Transform options: log, percent-change, rolling mean
 - Caching for API calls

Author: Generated for Dr .Meo — paste and run.
"""
import io
import time
from functools import lru_cache

import pandas as pd
import numpy as np
import requests
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Advanced Econ Dashboard", layout="wide")
st.title("Advanced Global Economic & Financial Data Dashboard")

# ---------------------------
# Helpers and caching
# ---------------------------
HEADERS = {"User-Agent": "AdvancedEconDashboard/1.0 (research)"}

@st.cache_data(ttl=24*3600, show_spinner=False)
def fetch_json(url, params=None, headers=None, timeout=30):
    try:
        r = requests.get(url, params=params, headers=headers or HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"__error__": str(e)}

@st.cache_data(ttl=24*3600, show_spinner=False)
def fetch_text(url, params=None, headers=None, timeout=30):
    try:
        r = requests.get(url, params=params, headers=headers or HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        return None

def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=True, sheet_name="data")
        writer.save()
    return buf.getvalue()

# ---------------------------
# Sidebar: Global controls
# ---------------------------
st.sidebar.markdown("## Global options")
transform_log = st.sidebar.checkbox("Log transform", value=False)
transform_pct = st.sidebar.checkbox("Percent change (period-over-period)", value=False)
rolling_window = st.sidebar.number_input("Rolling window (periods; 0 = none)", min_value=0, value=0, step=1)

st.sidebar.markdown("---")
source = st.sidebar.selectbox("Select data source", ["World Bank", "FRED", "OECD", "IMF"])

# ---------------------------
# WORLD BANK MODULE
# ---------------------------
if source == "World Bank":
    st.header("World Bank Explorer")

    # Countries (cached)
    wb_countries_json = fetch_json("https://api.worldbank.org/v2/country?format=json&per_page=400")
    if "__error__" in wb_countries_json:
        st.error(f"Error fetching World Bank countries: {wb_countries_json['__error__']}")
    else:
        countries = wb_countries_json[1]
        country_map = {c["name"]: c["id"] for c in countries if c.get("id")}
        country_list = sorted(list(country_map.keys()))
        country_name = st.sidebar.selectbox("Country", country_list, index=country_list.index("United States") if "United States" in country_list else 0)
        country_iso = country_map[country_name]

        # Indicators: allow search & filtering
        st.info("Indicator list can be large. Use the search box to filter indicators by keyword.")
        ind_search = st.text_input("Indicator search (name or code substring)", value="gdp")
        # fetch indicators pages (cached internal)
        @st.cache_data(ttl=24*3600, show_spinner=False)
        def get_all_wb_indicators():
            indicators = []
            page = 1
            while True:
                url = f"https://api.worldbank.org/v2/indicator?format=json&per_page=200&page={page}"
                resp = fetch_json(url)
                if "__error__" in resp:
                    break
                if not resp or len(resp) < 2 or not resp[1]:
                    break
                indicators.extend(resp[1])
                page += 1
                # safety cutoff
                if page > 25:
                    break
            return indicators

        indicators = get_all_wb_indicators()
        # create display list
        ind_display = []
        for ind in indicators:
            name = ind.get("name", "")
            iid = ind.get("id", "")
            combined = f"{name} ({iid})"
            if ind_search.strip() == "" or ind_search.lower() in combined.lower() or ind_search.lower() in iid.lower():
                ind_display.append((combined, iid))
        if not ind_display:
            st.warning("No indicators matched your search. Try broader keywords (e.g., GDP, inflation, population).")
        else:
            # show a sorted list (by name)
            ind_display_sorted = sorted(ind_display, key=lambda x: x[0]) 
            ind_labels = [x[0] for x in ind_display_sorted]
            chosen_ind_label = st.sidebar.selectbox(f"Indicator ({len(ind_labels)} matches)", ind_labels)
            chosen_ind_code = dict(ind_display_sorted)[chosen_ind_label]

            # Date range selection: query available years by fetching a long range and inspecting
            yr_from = st.number_input("From year (min)", min_value=1900, max_value=2100, value=2000)
            yr_to = st.number_input("To year (max)", min_value=1900, max_value=2100, value=2023)

            if st.button("Fetch World Bank data"):
                with st.spinner("Fetching World Bank series..."):
                    url = f"https://api.worldbank.org/v2/country/{country_iso}/indicator/{chosen_ind_code}?format=json&per_page=5000&date={yr_from}:{yr_to}"
                    resp = fetch_json(url)
                    if "__error__" in resp:
                        st.error(f"HTTP error: {resp['__error__']}")
                    elif not resp or len(resp) < 2:
                        st.warning("No data returned for that indicator/country/date range.")
                    else:
                        raw = resp[1]
                        df = pd.DataFrame(raw)
                        if df.empty:
                            st.warning("No observations returned.")
                        else:
                            df = df[["date", "value"]].dropna()
                            df["date"] = pd.to_numeric(df["date"], errors="coerce").astype(int)
                            df = df.sort_values("date").set_index("date")
                            series = df["value"].astype(float)

                            # Transformations
                            out = series.copy()
                            if transform_log:
                                out = np.log(out.replace(0, np.nan))
                            if transform_pct:
                                out = out.pct_change()
                            if rolling_window and rolling_window > 0:
                                out = out.rolling(window=rolling_window).mean()

                            # Plot
                            fig = px.line(out.reset_index().rename(columns={"date": "year", "value": "value"}), x="date", y=0 if isinstance(out, pd.Series) else "value", labels={"date":"Year"}, title=f"{chosen_ind_label} — {country_name}")
                            # When out is Series, px.line needs column name; convert to df
                            if isinstance(out, pd.Series):
                                plot_df = out.reset_index()
                                plot_df.columns = ["year", "value"]
                                fig = px.line(plot_df, x="year", y="value", labels={"year":"Year","value":"Value"}, title=f"{chosen_ind_label} — {country_name}")
                            st.plotly_chart(fig, use_container_width=True)

                            # show table head and availability
                            st.write("Series preview and availability")
                            st.dataframe(df.head(50))

                            # Downloads
                            csv_bytes = df.to_csv().encode()
                            st.download_button("Download CSV", csv_bytes, file_name=f"WB_{country_iso}_{chosen_ind_code}.csv", mime="text/csv")
                            excel_bytes = df_to_excel_bytes(df)
                            st.download_button("Download Excel", excel_bytes, file_name=f"WB_{country_iso}_{chosen_ind_code}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ---------------------------
# FRED MODULE
# ---------------------------
elif source == "FRED":
    st.header("FRED Explorer (requires API key)")
    st.info("Get a free API key at: https://fred.stlouisfed.org/docs/api/api_key.html")
    fred_key = st.sidebar.text_input("FRED API Key", type="password")
    fred_query = st.sidebar.text_input("Search query (keywords, e.g., 'GDP', 'CPI')", value="GDP")
    if not fred_key:
        st.warning("Paste a valid FRED API key in the sidebar to enable search and fetch.")
    else:
        if st.sidebar.button("Search FRED series"):
            with st.spinner("Searching FRED..."):
                s_url = "https://api.stlouisfed.org/fred/series/search"
                params = {"search_text": fred_query, "api_key": fred_key, "file_type": "json", "limit": 200}
                resp = fetch_json(s_url, params=params)
                if "__error__" in resp:
                    st.error(f"Error calling FRED: {resp['__error__']}")
                elif "seriess" not in resp or not resp["seriess"]:
                    st.warning("No results found.")
                else:
                    results = resp["seriess"]
                    # present as title (id)
                    choices = [f'{r.get("title","")[:120]} ({r.get("id")})' for r in results]
                    choice = st.selectbox("Choose series", choices)
                    if st.button("Fetch selected FRED series"):
                        series_id = choice.split("(")[-1].strip(")")
                        with st.spinner("Fetching FRED observations..."):
                            obs_url = "https://api.stlouisfed.org/fred/series/observations"
                            params = {"series_id": series_id, "api_key": fred_key, "file_type": "json", "observation_start": "1900-01-01", "observation_end": time.strftime("%Y-%m-%d")}
                            data = fetch_json(obs_url, params=params)
                            if "__error__" in data:
                                st.error(f"Error: {data['__error__']}")
                            elif "observations" not in data:
                                st.warning("No observations returned.")
                            else:
                                df = pd.DataFrame(data["observations"])
                                df["value"] = pd.to_numeric(df["value"], errors="coerce")
                                df = df.dropna(subset=["value"]).set_index(pd.to_datetime(df["date"]))
                                ser = df["value"].copy()

                                # transforms
                                out = ser.copy()
                                if transform_log:
                                    out = np.log(out.replace(0, np.nan))
                                if transform_pct:
                                    out = out.pct_change()
                                if rolling_window and rolling_window > 0:
                                    out = out.rolling(window=rolling_window).mean()

                                plot_df = out.reset_index().rename(columns={"index": "date", 0: "value"}) if isinstance(out, pd.Series) else out
                                fig = px.line(plot_df, x="date", y=plot_df.columns[-1], labels={"date":"Date"}, title=series_id)
                                st.plotly_chart(fig, use_container_width=True)

                                st.dataframe(df.head(200))

                                st.download_button("Download CSV", df.to_csv().encode(), file_name=f"FRED_{series_id}.csv")
                                st.download_button("Download Excel", df_to_excel_bytes(df), file_name=f"FRED_{series_id}.xlsx")

# ---------------------------
# OECD MODULE
# ---------------------------
elif source == "OECD":
    st.header("OECD Browser (basic)")
    st.info("OECD REST calls require dataset + key. This UI provides a simple CSV fetch pattern.")
    dataset = st.sidebar.text_input("Dataset code (e.g., MEI, PDB, QNA)", value="MEI")
    dimension_key = st.sidebar.text_input("Dimension key (OECD-specific). Example: USA.CPI.M", value="USA.CPI.M")
    if st.button("Fetch OECD CSV"):
        url = f"https://stats.oecd.org/SDMX-JSON/data/{dataset}/{dimension_key}/all?contentType=csv"
        txt = fetch_text(url)
        if not txt:
            st.error("No response or HTTP error from OECD. Check dataset and dimension key.")
        else:
            try:
                df = pd.read_csv(io.StringIO(txt))
                st.plotly_chart(px.line(df, x=df.columns[0], y=df.columns[-1], labels={df.columns[0]:"x", df.columns[-1]:"value"}, title=f"{dataset} {dimension_key}"), use_container_width=True)
                st.dataframe(df.head(200))
                st.download_button("Download CSV", df.to_csv(index=False).encode(), file_name=f"OECD_{dataset}_{dimension_key}.csv")
                st.download_button("Download Excel", df_to_excel_bytes(df), file_name=f"OECD_{dataset}_{dimension_key}.xlsx")
            except Exception as e:
                st.error(f"Could not parse OECD CSV: {e}")

# ---------------------------
# IMF MODULE (basic)
# ---------------------------
elif source == "IMF":
    st.header("IMF SDMX Browser (basic)")
    st.info("List available IMF dataflows and fetch CompactData entries (best-effort parser).")
    if st.button("List IMF dataflows"):
        url = "https://dataservices.imf.org/REST/SDMX_JSON.svc/Dataflow"
        resp = fetch_json(url)
        if "__error__" in resp:
            st.error(f"IMF error: {resp['__error__']}")
        else:
            try:
                items = resp.get("Structure", {}).get("Dataflows", {}).get("Dataflow", [])
                df = pd.json_normalize(items)
                if not df.empty:
                    st.dataframe(df[["DataflowAgencyId", "DataflowRef", "DataflowName"]].head(300))
                else:
                    st.warning("No dataflows parsed.")
            except Exception as e:
                st.error(f"Parsing error: {e}")

    db = st.text_input("Database id (e.g., IFS, BOP, IFSQ)", value="IFS")
    series_key = st.text_input("Series key (country.indicator e.g. USA.NGDP_RPCH)", value="USA.NGDP_RPCH")
    if st.button("Fetch IMF series"):
        if "." not in series_key:
            st.error("Series key should be in form COUNTRY.INDICATOR (e.g. USA.PGDP).")
        else:
            country, indicator = series_key.split(".", 1)
            url = f"https://dataservices.imf.org/REST/SDMX_JSON.svc/CompactData/{db}/{country}.{indicator}"
            resp = fetch_json(url)
            if "__error__" in resp:
                st.error(f"Error: {resp['__error__']}")
            else:
                try:
                    series = resp["CompactData"]["DataSet"]["Series"]["Obs"]
                    df = pd.DataFrame(series)
                    # IMS often uses 'TIME_PERIOD' and 'OBS_VALUE' naming
                    if "TIME_PERIOD" in df.columns or "@TIME_PERIOD" in df.columns:
                        time_col = "TIME_PERIOD" if "TIME_PERIOD" in df.columns else "@TIME_PERIOD"
                        val_col = "OBS_VALUE" if "OBS_VALUE" in df.columns else "@OBS_VALUE"
                        df2 = pd.DataFrame({
                            "date": pd.to_datetime(df[time_col], errors="coerce"),
                            "value": pd.to_numeric(df[val_col], errors="coerce")
                        }).dropna().set_index("date")
                        out = df2["value"].copy()
                        if transform_log:
                            out = np.log(out.replace(0, np.nan))
                        if transform_pct:
                            out = out.pct_change()
                        if rolling_window and rolling_window > 0:
                            out = out.rolling(window=rolling_window).mean()
                        plot_df = out.reset_index().rename(columns={"index": "date", 0: "value"}) if isinstance(out, pd.Series) else out
                        fig = px.line(plot_df, x="date", y=plot_df.columns[-1], title=series_key)
                        st.plotly_chart(fig, use_container_width=True)
                        st.dataframe(df2.head(200))
                        st.download_button("Download CSV", df2.to_csv().encode(), file_name=f"IMF_{db}_{series_key}.csv")
                        st.download_button("Download Excel", df_to_excel_bytes(df2), file_name=f"IMF_{db}_{series_key}.xlsx")
                    else:
                        st.warning("Could not find TIME_PERIOD / OBS_VALUE columns in IMF response; raw JSON below.")
                        st.json(resp)
                except Exception as e:
                    st.error(f"Parsing IMF response failed: {e}")

# ---------------------------
# Footer tips
# ---------------------------
st.markdown("---")
st.write(
    "Notes: 1) World Bank and OECD endpoints are public; FRED requires API key. "
    "2) API providers impose rate limits — caching is enabled. 3) This is a research tool; validate series metadata (units, frequency) before inference."
)
