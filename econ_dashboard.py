import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from pandas_datareader import wb
import requests
import io

st.set_page_config(page_title="Advanced Economic Data Explorer", layout="wide")

# ===========================================================
#                 APP HEADER
# ===========================================================
st.title("📊 Advanced Economic Data Explorer")
st.markdown("Select a data source, search variables, choose country and visualize instantly.")

# ===========================================================
#                 DATA SOURCES
# ===========================================================
DATA_SOURCES = ["World Bank", "OECD", "IMF (IFS)", "FRED"]

source = st.sidebar.selectbox("Select Data Source", DATA_SOURCES)

# ===========================================================
#          WORLD BANK FUNCTIONS
# ===========================================================
def wb_search_indicator(keyword):
    url = f"http://api.worldbank.org/v2/indicator?format=json&per_page=2000"
    data = requests.get(url).json()
    df = pd.json_normalize(data[1])
    return df[df['name'].str.contains(keyword, case=False, na=False)][['id', 'name']]

def wb_get_data(country, indicator):
    df = wb.download(indicator=indicator, country=country, start=1960, end=2024)
    df = df.reset_index()
    return df

# ===========================================================
#          OECD FUNCTIONS
# ===========================================================
def oecd_search(keyword):
    url = "https://stats.oecd.org/SDMX-JSON/dataflow/ALL/?contentType=sdmx-json"
    data = requests.get(url).json()
    flows = data["dataflows"]["dataflow"]

    results = []
    for k, v in flows.items():
        name = v["name"]["en"]
        if keyword.lower() in name.lower():
            results.append([k, name])
    
    return pd.DataFrame(results, columns=["Code", "Name"])

# ===========================================================
#          IMF FUNCTIONS
# ===========================================================
def imf_search(keyword):
    url = "https://dataservices.imf.org/REST/SDMX_JSON.svc/Dataflow"
    data = requests.get(url).json()
    flows = data["Structure"]["Dataflows"]["Dataflow"]

    res = []
    for f in flows:
        code = f["@id"]
        name = f["Name"]["#text"]
        if keyword.lower() in name.lower():
            res.append([code, name])
    return pd.DataFrame(res, columns=["Code", "Name"])

# ===========================================================
#              FRED FUNCTIONS
# ===========================================================
def fred_search(keyword):
    url = f"https://api.stlouisfed.org/fred/series/search?search_text={keyword}&api_key=YOUR_KEY&file_type=json"
    out = requests.get(url).json()

    if "seriess" not in out:
        return pd.DataFrame(columns=["ID", "Title"])

    df = pd.json_normalize(out["seriess"])
    return df[["id", "title"]]

def fred_get(id):
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={id}&api_key=YOUR_KEY&file_type=json"
    data = requests.get(url).json()
    df = pd.DataFrame(data["observations"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df

# ===========================================================
#                 UI PANEL
# ===========================================================
keyword = st.sidebar.text_input("Search Indicator Keyword")

if keyword:
    if source == "World Bank":
        results = wb_search_indicator(keyword)
    elif source == "OECD":
        results = oecd_search(keyword)
    elif source == "IMF (IFS)":
        results = imf_search(keyword)
    elif source == "FRED":
        results = fred_search(keyword)
    else:
        results = pd.DataFrame()

    st.subheader("Search Results")
    st.dataframe(results, use_container_width=True)

    if not results.empty:
        selected_var = st.selectbox("Select Indicator / Series", results.iloc[:, 0])

        # COUNTRY SELECTOR FOR WB, OECD, IMF
        if source in ["World Bank"]:
            country = st.selectbox("Select Country", wb.get_countries().name.tolist())

        if st.button("Load Data"):
            if source == "World Bank":
                country_code = wb.get_countries()[wb.get_countries().name == country].iso2c.values[0]
                df = wb_get_data(country_code, selected_var)

                if df.empty:
                    st.error("No data found.")
                else:
                    fig = px.line(df, x="year", y=selected_var, title=f"{selected_var} - {country}")
                    st.plotly_chart(fig, use_container_width=True)

                    csv = df.to_csv(index=False).encode()
                    st.download_button("Download CSV", csv, "wb_data.csv")
            
            if source == "FRED":
                df = fred_get(selected_var)

                if df.empty:
                    st.error("No data found.")
                else:
                    fig = px.line(df, x="date", y="value", title=selected_var)
                    st.plotly_chart(fig, use_container_width=True)

                    csv = df.to_csv(index=False).encode()
                    st.download_button("Download CSV", csv, "fred_data.csv")

