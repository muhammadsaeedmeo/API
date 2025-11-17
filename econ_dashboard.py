import streamlit as st
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Set backend before importing pyplot
import matplotlib.pyplot as plt

st.title("🌍 WDI Panel Data Builder")

# File upload
uploaded = st.file_uploader("Upload your WDI Excel file", type=["xlsx", "xls"])

if uploaded is not None:
    try:
        # Read the file
        df = pd.read_excel(uploaded)
        
        st.success(f"✅ File loaded successfully! Shape: {df.shape}")
        
        # Show first few rows
        with st.expander("📋 Preview Raw Data"):
            st.dataframe(df.head())
        
        # Column selection
        st.subheader("📝 Step 1: Select Columns")
        
        col1, col2 = st.columns(2)
        
        with col1:
            country_col = st.selectbox(
                "Country column",
                options=df.columns.tolist(),
                help="Column containing country names"
            )
        
        with col2:
            var_col = st.selectbox(
                "Variable/Indicator column",
                options=df.columns.tolist(),
                help="Column containing variable names"
            )
        
        # Optional columns
        with st.expander("⚙️ Optional: Select Code Columns"):
            col3, col4 = st.columns(2)
            with col3:
                code_col_options = ["None"] + df.columns.tolist()
                code_col = st.selectbox("Country code column", code_col_options)
                code_col = None if code_col == "None" else code_col
            
            with col4:
                var_code_col = st.selectbox("Variable code column", code_col_options)
                var_code_col = None if var_code_col == "None" else var_code_col
        
        # Detect year columns
        st.subheader("📅 Step 2: Select Years")
        year_cols = []
        for col in df.columns:
            col_str = str(col)
            # Check if column name starts with digits (year)
            if col_str and col_str[0].isdigit():
                year_cols.append(col)
        
        if year_cols:
            selected_years = st.multiselect(
                "Select year columns to include",
                options=year_cols,
                default=year_cols,
                help="Choose which years to include in your panel"
            )
        else:
            st.warning("⚠️ No year columns detected. Looking for columns starting with digits (e.g., '1990', '2000')")
            selected_years = []
        
        # Filtering options
        st.subheader("🔍 Step 3: Filter Data (Optional)")
        
        # Get unique values safely
        try:
            countries_raw = df[country_col].dropna().astype(str).unique().tolist()
            countries_sorted = sorted(countries_raw)
        except:
            countries_sorted = df[country_col].dropna().astype(str).tolist()
        
        try:
            variables_raw = df[var_col].dropna().astype(str).unique().tolist()
            variables_sorted = sorted(variables_raw)
        except:
            variables_sorted = df[var_col].dropna().astype(str).tolist()
        
        col5, col6 = st.columns(2)
        
        with col5:
            selected_countries = st.multiselect(
                "Select specific countries",
                options=countries_sorted,
                default=None,
                help="Leave empty to include all countries"
            )
        
        with col6:
            selected_variables = st.multiselect(
                "Select specific variables",
                options=variables_sorted,
                default=None,
                help="Leave empty to include all variables"
            )
        
        # Format button
        if st.button("🚀 Format Data", type="primary"):
            if not selected_years:
                st.error("❌ Please select at least one year column")
            else:
                with st.spinner("Processing data..."):
                    try:
                        # Filter data
                        df_work = df.copy()
                        
                        if selected_countries:
                            df_work = df_work[df_work[country_col].astype(str).isin(selected_countries)]
                            st.info(f"✓ Filtered to {len(selected_countries)} countries")
                        
                        if selected_variables:
                            df_work = df_work[df_work[var_col].astype(str).isin(selected_variables)]
                            st.info(f"✓ Filtered to {len(selected_variables)} variables")
                        
                        # Map year columns to integers
                        year_map = {}
                        for col in selected_years:
                            try:
                                # Extract year from column name
                                year_str = str(col).split()[0]
                                year_int = int(year_str)
                                year_map[col] = year_int
                            except:
                                st.warning(f"Could not parse year from: {col}")
                        
                        # Rename year columns
                        df_renamed = df_work.rename(columns=year_map)
                        
                        # Prepare ID variables for melting
                        id_vars = [country_col, var_col]
                        if code_col:
                            id_vars.append(code_col)
                        if var_code_col:
                            id_vars.append(var_code_col)
                        
                        # Melt to long format
                        df_long = df_renamed.melt(
                            id_vars=id_vars,
                            value_vars=list(year_map.values()),
                            var_name="year",
                            value_name="value"
                        )
                        
                        # Clean data
                        # Convert value to numeric (handles '..' and other non-numeric)
                        df_long['value'] = pd.to_numeric(df_long['value'], errors='coerce')
                        df_long = df_long.dropna(subset=['value'])
                        
                        # Rename columns to standard names
                        rename_dict = {
                            country_col: 'country',
                            var_col: 'variable'
                        }
                        if code_col:
                            rename_dict[code_col] = 'country_code'
                        if var_code_col:
                            rename_dict[var_code_col] = 'variable_code'
                        
                        df_long = df_long.rename(columns=rename_dict)
                        
                        # Ensure year is integer
                        df_long['year'] = df_long['year'].astype(int)
                        
                        # Create country ID
                        unique_countries = sorted(df_long['country'].unique())
                        country_id_map = {c: i+1 for i, c in enumerate(unique_countries)}
                        df_long['country_id'] = df_long['country'].map(country_id_map)
                        
                        # Pivot to panel format (one row per country-year)
                        panel = df_long.pivot_table(
                            index=['country', 'country_id', 'year'],
                            columns='variable',
                            values='value',
                            aggfunc='first'
                        ).reset_index()
                        
                        # Store in session state
                        st.session_state['panel'] = panel
                        st.session_state['df_long'] = df_long
                        
                        st.success(f"✅ Successfully formatted! Panel has {panel.shape[0]} rows and {panel.shape[1]} columns")
                        
                    except Exception as e:
                        st.error(f"❌ Error during formatting: {str(e)}")
                        st.exception(e)
        
    except Exception as e:
        st.error(f"❌ Error loading file: {str(e)}")
        st.exception(e)

# Display results if available
if 'panel' in st.session_state:
    panel = st.session_state['panel']
    
    st.divider()
    st.subheader("📊 Formatted Panel Data")
    
    st.write(f"**Shape:** {panel.shape[0]} rows × {panel.shape[1]} columns")
    
    # Show data
    with st.expander("👁️ View Panel Data", expanded=True):
        st.dataframe(panel, use_container_width=True, height=400)
    
    # Visualization
    st.divider()
    st.subheader("📈 Visualize Data")
    
    countries = sorted(panel['country'].unique())
    variables = [col for col in panel.columns if col not in ['country', 'country_id', 'year']]
    
    col7, col8 = st.columns(2)
    
    with col7:
        viz_countries = st.multiselect(
            "Countries to plot",
            options=countries,
            default=countries[:min(3, len(countries))],
            key="viz_countries"
        )
    
    with col8:
        viz_vars = st.multiselect(
            "Variables to plot",
            options=variables,
            default=variables[:min(2, len(variables))],
            key="viz_vars"
        )
    
    if viz_countries and viz_vars:
        # Filter and plot
        df_plot = panel[panel['country'].isin(viz_countries)]
        
        for country in viz_countries:
            df_country = df_plot[df_plot['country'] == country].sort_values('year')
            
            if not df_country.empty:
                fig, ax = plt.subplots(figsize=(10, 5))
                
                for var in viz_vars:
                    if var in df_country.columns:
                        ax.plot(df_country['year'], df_country[var], 
                               marker='o', label=var, linewidth=2)
                
                ax.set_title(f"{country}", fontsize=14, fontweight='bold')
                ax.set_xlabel("Year", fontsize=12)
                ax.set_ylabel("Value", fontsize=12)
                ax.legend()
                ax.grid(True, alpha=0.3)
                plt.tight_layout()
                
                st.pyplot(fig)
                plt.close(fig)
    
    # Download section
    st.divider()
    st.subheader("💾 Download Data")
    
    col9, col10 = st.columns(2)
    
    with col9:
        csv = panel.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Full Panel (CSV)",
            data=csv,
            file_name="wdi_panel_full.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col10:
        if viz_countries:
            filtered = panel[panel['country'].isin(viz_countries)]
            csv_filtered = filtered.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Filtered Panel (CSV)",
                data=csv_filtered,
                file_name="wdi_panel_filtered.csv",
                mime="text/csv",
                use_container_width=True
            )
