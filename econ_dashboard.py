
import streamlit as st
import pandas as pd
import requests

st.title("Global Economic & Financial Data Dashboard")

st.sidebar.header("Data Source")
source = st.sidebar.selectbox("Select API", ["World Bank", "FRED", "OECD"])

if source == "World Bank":
    indicator = st.sidebar.text_input("Indicator Code", "NY.GDP.MKTP.CD")
    country = st.sidebar.text_input("Country Code", "USA")
    url = f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}?format=json"
    r = requests.get(url)
    data = r.json()
    if isinstance(data, list) and len(data) > 1:
        df = pd.DataFrame(data[1])
        st.dataframe(df)
        csv = df.to_csv(index=False).encode()
        st.download_button("Download CSV", csv, "worldbank_data.csv")

elif source == "FRED":
    api_key = st.sidebar.text_input("API Key")
    series = st.sidebar.text_input("Series ID", "GDP")
    if api_key:
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series}&api_key={api_key}&file_type=json"
        r = requests.get(url)
        data = r.json()
        if "observations" in data:
            df = pd.DataFrame(data["observations"])
            st.dataframe(df)
            csv = df.to_csv(index=False).encode()
            st.download_button("Download CSV", csv, "fred_data.csv")

elif source == "OECD":
    dataset = st.sidebar.text_input("Dataset", "MEI")
    location = st.sidebar.text_input("Location", "USA")
    subject = st.sidebar.text_input("Subject", "IRTST")
    url = f"https://stats.oecd.org/SDMX-JSON/data/{dataset}/{location}.{subject}.M/all?contentType=csv"
    r = requests.get(url)
    if r.status_code == 200:
        df = pd.read_csv(pd.compat.StringIO(r.text))
        st.dataframe(df)
        csv = df.to_csv(index=False).encode()
        st.download_button("Download CSV", csv, "oecd_data.csv")
