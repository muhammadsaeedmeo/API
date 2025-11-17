import streamlit as st
import pandas as pd
import numpy as np

st.title("WDI Formatter and Panel Converter")

uploaded = st.file_uploader("Upload WDI Excel file", type=["xlsx", "xls"])

if uploaded:
    df = pd.read_excel(uploaded)
    st.subheader("Raw Columns")
    st.write(df.columns.tolist())

    # Auto-detect metadata columns
    default_country = "Country Name" if "Country Name" in df.columns else df.columns[0]
    default_code = "Country Code" if "Country Code" in df.columns else None

    country_col = st.selectbox("Country column", df.columns, index=list(df.columns).index(default_country))
    code_col = st.selectbox("Country code column (optional)", ["None"] + list(df.columns))
    code_col = None if code_col == "None" else code_col

    # Series name and series code columns
    possible_series = [c for c in df.columns if "Series" in c or "Indicator" in c]
    if len(possible_series) >= 1:
        var_col = st.selectbox("Variable name column", possible_series)
    else:
        var_col = st.selectbox("Variable name column", df.columns)

    # Detect year columns: patterns like "2010 [YR2010]"
    year_cols = [c for c in df.columns if isinstance(c, str) and c.split()[0].isdigit()]
    st.subheader("Detected year columns")
    st.write(year_cols)

    selected_years = st.multiselect("Select years to include", year_cols, default=year_cols)

    if st.button("Convert to Long Panel"):
        # Clean year names: "2010 [YR2010]" -> 2010
        clean_year_map = {c: int(c.split()[0]) for c in selected_years}
        df_clean = df.rename(columns=clean_year_map)

        # Melt to long panel
        id_vars = [country_col, var_col]
        if code_col:
            id_vars.append(code_col)

        long_df = df_clean.melt(
            id_vars=id_vars,
            value_vars=list(clean_year_map.values()),
            var_name="year",
            value_name="value"
        )

        long_df = long_df.dropna(subset=["value"])

        # Rename columns for consistency
        rename_map = {
            country_col: "country",
            var_col: "variable"
        }
        if code_col:
            rename_map[code_col] = "country_code"

        long_df = long_df.rename(columns=rename_map)
        long_df["year"] = long_df["year"].astype(int)

        st.subheader("Final Long Panel")
        st.write(long_df)

        # Summary: missing values per country in original wide file
        st.subheader("Missing Data Summary")
        missing_per_country = df.groupby(country_col)[selected_years].apply(lambda x: x.isna().sum().sum())
        missing_per_country = missing_per_country.reset_index()
        missing_per_country.columns = ["country", "missing_values"]
        st.write(missing_per_country.sort_values("missing_values", ascending=False))

        # Summary: maximum years of data per country
        st.subheader("Countries with Maximum Time Coverage")
        wide_years = df[selected_years]
        coverage = df.groupby(country_col)[selected_years].apply(lambda x: x.notna().sum().sum())
        coverage = coverage.reset_index()
        coverage.columns = ["country", "years_available"]

        st.write(coverage.sort_values("years_available", ascending=False))

        # Download button
        st.download_button(
            "Download Long Panel CSV",
            long_df.to_csv(index=False),
            file_name="wdi_long_panel.csv",
            mime="text/csv"
        )
