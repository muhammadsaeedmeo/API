import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

st.title("Advanced WDI Formatter and Panel Builder")

uploaded = st.file_uploader("Upload WDI Excel file", type=["xlsx", "xls"])

if uploaded:
    df = pd.read_excel(uploaded)

    st.subheader("Raw Columns")
    st.write(df.columns.tolist())

    # METADATA SELECTION
    country_col = st.selectbox("Country column", df.columns)
    code_col = st.selectbox("Country code column (optional)", ["None"] + list(df.columns))
    code_col = None if code_col == "None" else code_col

    var_col = st.selectbox("Variable name column", df.columns)
    var_code_col = st.selectbox("Variable code column (optional)", ["None"] + list(df.columns))
    var_code_col = None if var_code_col == "None" else var_code_col

    # YEAR detection
    year_cols = [c for c in df.columns if isinstance(c, str) and c.split()[0].isdigit()]
    selected_years = st.multiselect("Select years", year_cols, default=year_cols)

    if st.button("Format Data"):
        # Clean years
        clean_year_map = {c: int(c.split()[0]) for c in selected_years}
        df_clean = df.rename(columns=clean_year_map)

        # Melt to long
        id_vars = [country_col, var_col]
        if code_col:
            id_vars.append(code_col)
        if var_code_col:
            id_vars.append(var_code_col)

        long_df = df_clean.melt(
            id_vars=id_vars,
            value_vars=list(clean_year_map.values()),
            var_name="year",
            value_name="value"
        ).dropna(subset=["value"])

        long_df = long_df.rename(columns={
            country_col: "country",
            var_col: "variable"
        })

        if code_col:
            long_df = long_df.rename(columns={code_col: "country_code"})
        if var_code_col:
            long_df = long_df.rename(columns={var_code_col: "variable_code"})

        long_df["year"] = long_df["year"].astype(int)

        # CREATE NUMERIC COUNTRY ID
        unique_countries = long_df["country"].unique()
        country_map = {c: i+1 for i, c in enumerate(sorted(unique_countries))}
        long_df["country_id"] = long_df["country"].map(country_map)

        # PIVOT: ONE ROW = COUNTRY-YEAR WITH MULTIPLE VARIABLES
        panel = long_df.pivot_table(
            index=["country", "country_id", "year"],
            columns="variable",
            values="value"
        ).reset_index()

        st.subheader("Structured Panel Data")
        st.write(panel.head(30))

        # COUNTRY selector for filtering + graph
        st.subheader("Country Selection for Graph")
        countries = sorted(panel["country"].unique())
        selected_countries = st.multiselect("Choose countries", countries, default=countries[0:1])

        # VARIABLE selector
        variables = [v for v in panel.columns if v not in ["country", "country_id", "year"]]
        selected_vars = st.multiselect("Choose variables", variables, default=variables[0:1])

        # FILTER based on selection
        df_filtered = panel[panel["country"].isin(selected_countries)]

        st.subheader("Filtered Data")
        st.write(df_filtered)

        # PLOT
        for country in selected_countries:
            sub = df_filtered[df_filtered["country"] == country]

            fig, ax = plt.subplots()
            for v in selected_vars:
                ax.plot(sub["year"], sub[v], label=v)

            ax.set_title(f"Time Series for {country}")
            ax.set_xlabel("Year")
            ax.set_ylabel("Value")
            ax.legend()
            st.pyplot(fig)

        # DOWNLOAD PANEL
        st.download_button(
            "Download Panel CSV",
            panel.to_csv(index=False),
            file_name="panel_data.csv",
            mime="text/csv"
        )
