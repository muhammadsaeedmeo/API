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
    
    # PRE-FILTERING: Select countries and variables BEFORE formatting
    st.subheader("🔍 Filter Data Before Processing")
    
    # Clean and sort countries (remove NaN and convert to string)
    available_countries = df[country_col].dropna().unique()
    available_countries = sorted([str(c) for c in available_countries])
    
    selected_countries_raw = st.multiselect(
        "Select countries (leave empty for all)", 
        available_countries,
        default=None,
        help="Choose specific countries or leave empty to include all"
    )
    
    # Clean and sort variables (remove NaN and convert to string)
    available_variables = df[var_col].dropna().unique()
    available_variables = sorted([str(v) for v in available_variables])
    
    selected_variables_raw = st.multiselect(
        "Select variables (leave empty for all)", 
        available_variables,
        default=None,
        help="Choose specific indicators or leave empty to include all"
    )
    
    if st.button("Format Data"):
        # Apply filters if any selected
        df_filtered = df.copy()
        
        if selected_countries_raw:
            df_filtered = df_filtered[df_filtered[country_col].isin(selected_countries_raw)]
            st.info(f"✅ Filtered to {len(selected_countries_raw)} countries")
        else:
            st.info(f"✅ Including all {len(available_countries)} countries")
            
        if selected_variables_raw:
            df_filtered = df_filtered[df_filtered[var_col].isin(selected_variables_raw)]
            st.info(f"✅ Filtered to {len(selected_variables_raw)} variables")
        else:
            st.info(f"✅ Including all {len(available_variables)} variables")
        
        # Clean years
        clean_year_map = {c: int(c.split()[0]) for c in selected_years}
        df_clean = df_filtered.rename(columns=clean_year_map)
        
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
        
        # Store in session state for persistence
        st.session_state['panel'] = panel
        
        st.success("✅ Data formatted successfully!")
        
# Display results if panel exists in session state
if 'panel' in st.session_state:
    panel = st.session_state['panel']
    
    st.subheader("📊 Structured Panel Data")
    st.write(f"Shape: {panel.shape[0]} rows × {panel.shape[1]} columns")
    st.dataframe(panel.head(30))
    
    # VISUALIZATION SECTION
    st.subheader("📈 Visualization Options")
    
    countries = sorted(panel["country"].unique())
    variables = [v for v in panel.columns if v not in ["country", "country_id", "year"]]
    
    col1, col2 = st.columns(2)
    
    with col1:
        viz_countries = st.multiselect(
            "Select countries to visualize", 
            countries, 
            default=countries[0:min(3, len(countries))],
            key="viz_countries"
        )
    
    with col2:
        viz_vars = st.multiselect(
            "Select variables to plot", 
            variables, 
            default=variables[0:min(2, len(variables))],
            key="viz_vars"
        )
    
    if viz_countries and viz_vars:
        # FILTER for visualization
        df_viz = panel[panel["country"].isin(viz_countries)]
        
        st.subheader("🔍 Filtered Data for Visualization")
        st.dataframe(df_viz)
        
        # PLOT
        for country in viz_countries:
            sub = df_viz[df_viz["country"] == country]
            if not sub.empty:
                fig, ax = plt.subplots(figsize=(10, 6))
                for v in viz_vars:
                    if v in sub.columns:
                        ax.plot(sub["year"], sub[v], marker='o', label=v)
                ax.set_title(f"Time Series for {country}", fontsize=14, fontweight='bold')
                ax.set_xlabel("Year")
                ax.set_ylabel("Value")
                ax.legend()
                ax.grid(True, alpha=0.3)
                st.pyplot(fig)
    elif not viz_countries:
        st.warning("⚠️ Please select at least one country to visualize")
    elif not viz_vars:
        st.warning("⚠️ Please select at least one variable to visualize")
    
    # DOWNLOAD OPTIONS
    st.subheader("💾 Download Options")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.download_button(
            "📥 Download Full Panel (CSV)",
            panel.to_csv(index=False),
            file_name="panel_data_full.csv",
            mime="text/csv"
        )
    
    with col2:
        if viz_countries and viz_vars:
            filtered_panel = panel[panel["country"].isin(viz_countries)]
            st.download_button(
                "📥 Download Filtered Panel (CSV)",
                filtered_panel.to_csv(index=False),
                file_name="panel_data_filtered.csv",
                mime="text/csv"
            )
