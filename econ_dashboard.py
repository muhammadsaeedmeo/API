import streamlit as st
import pandas as pd
import requests
import plotly.express as px

st.set_page_config(page_title="Economic Data Dashboard", layout="wide")

st.title("📊 Advanced Economic Data Explorer")

# ===========================================================
# HELPER FUNCTIONS
# ===========================================================

# ---------------- WORLD BANK ----------------
def wb_search_indicator(keyword):
    url = "http://api.worldbank.org/v2/indicator?format=json&per_page=20000"
    raw = requests.get(url).json()
    df = pd.json_normalize(raw[1])
    df = df[['id', 'name']]
    return df[df['name'].str.contains(keyword, case=False, na=False)]

def wb_countries():
    url = "http://api.worldbank.org/v2/country?format=json&per_page=400"
    raw = requests.get(url).json()
    df = pd.json_normalize(raw[1])
    return df[['id', 'name']]

def wb_get_data(country_code, indicator_code):
    url = f"http://api.worldbank.org/v2/country/{country_code}/indicator/{indicator_code}?format=json&per_page=20000"
    raw = requests.get(url).json()

    if len(raw) < 2:
        return pd.DataFrame()

    df = pd.json_normalize(raw[1])
    df = df[['date', 'value']]
    df['value'] = pd.to_numeric(df['value'], errors='coerce')
    return df.sort_values('date')


# ---------------- FRED ----------------
FRED_KEY = "ENTER_YOUR_FRED_KEY"

def fred_search(keyword):
    url = f"https://api.stlouisfed.org/fred/series/search?search_text={keyword}&api_key={FRED_KEY}&file_type=json"
    raw = requests.get(url).json()

    if "seriess" not in raw:
        return pd.DataFrame()

    df = pd.json_normalize(raw["seriess"])
    return df[['id', 'title']]

def fred_get(series_id):
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_KEY}&file_type=json"
    raw = requests.get(url).json()

    df = pd.DataFrame(raw["observations"])
    df['value'] = pd.to_numeric(df['value'], errors='coerce')
    return df[['date', 'value']]


# ===========================================================
# SIDEBAR SELECTIONS
# ===========================================================

source = st.sidebar.selectbox(
    "Select Data Source",
    ["World Bank", "FRED"]
)

keyword = st.sidebar.text_input("Search indicator")
run_search = st.sidebar.button("Search")


# ===========================================================
# SEARCH PANEL
# ===========================================================

if run_search and keyword.strip():

    if source == "World Bank":
        results = wb_search_indicator(keyword)

    elif source == "FRED":
        results = fred_search(keyword)

    else:
        results = pd.DataFrame()

    st.subheader("Search Results")
    st.dataframe(results, use_container_width=True)

    if not results.empty:
        selected_var = st.selectbox("Select Indicator", results.iloc[:, 0].tolist())

        if source == "World Bank":
            countries = wb_countries()
            country_name = st.selectbox("Select country", countries['name'])
            country_code = countries[countries['name'] == country_name]['id'].values[0]

        if st.button("Load Data"):

            if source == "World Bank":
                df = wb_get_data(country_code, selected_var)

            elif source == "FRED":
                df = fred_get(selected_var)

            if df.empty:
                st.error("No data found.")
            else:
                fig = px.line(df, x=df.columns[0], y="value", title=selected_var)
                st.plotly_chart(fig, use_container_width=True)

                csv = df.to_csv(index=False).encode()
                st.download_button("Download CSV", csv, "data.csv")
