import streamlit as st
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

st.set_page_config(page_title="WDI Panel Data Builder", page_icon="🌍", layout="wide")

st.title("🌍 WDI Panel Data Builder")

# Initialize session state
if 'panel' not in st.session_state:
    st.session_state['panel'] = None
if 'df_long' not in st.session_state:
    st.session_state['df_long'] = None

# File upload
uploaded = st.file_uploader("Upload your WDI Excel file", type=["xlsx", "xls"])

if uploaded is not None:
    try:
        # Read the file
        df = pd.read_excel(uploaded)
        
        # Convert all column names to strings to avoid comparison issues
        df.columns = [str(col) for col in df.columns]
        
        st.success(f"✅ File loaded successfully! Shape: {df.shape}")
        
        # Show first few rows
        with st.expander("📋 Preview Raw Data"):
            st.dataframe(df.head(10))
        
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
                options=[col for col in df.columns.tolist() if col != country_col],
                help="Column containing variable names"
            )
        
        # Optional columns
        with st.expander("⚙️ Optional: Select Code Columns"):
            col3, col4 = st.columns(2)
            with col3:
                code_col_options = ["None"] + [col for col in df.columns.tolist() if col not in [country_col, var_col]]
                code_col = st.selectbox("Country code column", code_col_options)
                code_col = None if code_col == "None" else code_col
            
            with col4:
                var_code_options = ["None"] + [col for col in df.columns.tolist() if col not in [country_col, var_col, code_col]]
                var_code_col = st.selectbox("Variable code column", var_code_options)
                var_code_col = None if var_code_col == "None" else var_code_col
        
        # Detect year columns
        st.subheader("📅 Step 2: Select Years")
        
        excluded_cols = [country_col, var_col]
        if code_col:
            excluded_cols.append(code_col)
        if var_code_col:
            excluded_cols.append(var_code_col)
        
        year_cols = []
        for col in df.columns:
            if col not in excluded_cols:
                col_str = str(col).strip()
                # Check if column name starts with digits or contains year pattern
                if col_str and (col_str[0].isdigit() or any(year in col_str for year in ['19', '20'])):
                    year_cols.append(col)
        
        if year_cols:
            st.info(f"📅 Detected {len(year_cols)} potential year columns")
            selected_years = st.multiselect(
                "Select year columns to include",
                options=year_cols,
                default=year_cols[:min(10, len(year_cols))],
                help="Choose which years to include in your panel"
            )
        else:
            st.warning("⚠️ No year columns detected. Looking for columns starting with digits (e.g., '1990', '2000')")
            # Allow manual selection
            all_other_cols = [col for col in df.columns if col not in excluded_cols]
            selected_years = st.multiselect(
                "Manually select year columns",
                options=all_other_cols,
                help="Select columns that contain yearly data"
            )
        
        # Filtering options
        st.subheader("🔍 Step 3: Filter Data (Optional)")
        
        # Get unique values safely - convert to string and remove NaN
        try:
            countries_raw = df[country_col].dropna().astype(str).unique().tolist()
            countries_sorted = sorted([c for c in countries_raw if c and c.strip() and c != 'nan'])
        except Exception as e:
            st.warning(f"Could not sort countries: {e}")
            countries_sorted = []
        
        try:
            variables_raw = df[var_col].dropna().astype(str).unique().tolist()
            variables_sorted = sorted([v for v in variables_raw if v and v.strip() and v != 'nan'])
        except Exception as e:
            st.warning(f"Could not sort variables: {e}")
            variables_sorted = []
        
        col5, col6 = st.columns(2)
        
        with col5:
            selected_countries = st.multiselect(
                f"Select specific countries (Total: {len(countries_sorted)})",
                options=countries_sorted,
                default=None,
                help="Leave empty to include all countries"
            )
        
        with col6:
            selected_variables = st.multiselect(
                f"Select specific variables (Total: {len(variables_sorted)})",
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
                        
                        if df_work.empty:
                            st.error("❌ No data remaining after filtering. Please adjust your filters.")
                        else:
                            # Map year columns to integers
                            year_map = {}
                            import re
                            for col in selected_years:
                                try:
                                    # Extract year from column name
                                    col_str = str(col).strip()
                                    # Try to extract 4-digit year
                                    year_match = re.search(r'(19|20)\d{2}', col_str)
                                    if year_match:
                                        year_int = int(year_match.group())
                                    else:
                                        # Try direct conversion
                                        year_int = int(col_str.split()[0])
                                    year_map[col] = year_int
                                except Exception as e:
                                    st.warning(f"Could not parse year from: {col}. Skipping this column.")
                            
                            if not year_map:
                                st.error("❌ Could not parse any year columns. Please check your data format.")
                            else:
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
                                
                                # Clean data - handle '..' and other non-numeric values
                                # First, replace '..' with NaN
                                df_long['value'] = df_long['value'].replace('..', np.nan)
                                df_long['value'] = df_long['value'].replace('', np.nan)
                                
                                # Convert value to numeric
                                df_long['value'] = pd.to_numeric(df_long['value'], errors='coerce')
                                
                                # Count missing values before dropping
                                missing_count = df_long['value'].isna().sum()
                                total_count = len(df_long)
                                
                                df_long = df_long.dropna(subset=['value'])
                                
                                if df_long.empty:
                                    st.error("❌ No valid numeric data found after cleaning. Please check your data format.")
                                else:
                                    st.info(f"✓ Removed {missing_count} missing/non-numeric values ({missing_count/total_count*100:.1f}%)")
                                    
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
                                    try:
                                        df_long['year'] = df_long['year'].astype(int)
                                    except:
                                        st.warning("⚠️ Year column could not be converted to integer. Keeping as-is.")
                                    
                                    # Create country ID
                                    unique_countries = sorted(df_long['country'].astype(str).unique())
                                    country_id_map = {c: i+1 for i, c in enumerate(unique_countries)}
                                    df_long['country_id'] = df_long['country'].astype(str).map(country_id_map)
                                    
                                    # Pivot to panel format (one row per country-year)
                                    index_cols = ['country', 'country_id', 'year']
                                    if code_col:
                                        index_cols.insert(2, 'country_code')
                                    
                                    panel = df_long.pivot_table(
                                        index=index_cols,
                                        columns='variable',
                                        values='value',
                                        aggfunc='first'
                                    ).reset_index()
                                    
                                    # Clean column names (remove any special characters)
                                    panel.columns = [str(col).strip() for col in panel.columns]
                                    
                                    # Convert all string columns to avoid Arrow serialization issues
                                    for col in panel.columns:
                                        if panel[col].dtype == 'object':
                                            try:
                                                panel[col] = panel[col].astype(str)
                                            except:
                                                pass
                                    
                                    # Store in session state
                                    st.session_state['panel'] = panel
                                    st.session_state['df_long'] = df_long
                                    
                                    st.success(f"✅ Successfully formatted! Panel has {panel.shape[0]} rows and {panel.shape[1]} columns")
                        
                    except Exception as e:
                        st.error(f"❌ Error during formatting: {str(e)}")
                        with st.expander("View full error details"):
                            st.exception(e)
        
    except Exception as e:
        st.error(f"❌ Error loading file: {str(e)}")
        with st.expander("View full error details"):
            st.exception(e)

# Display results if available
if st.session_state.get('panel') is not None:
    panel = st.session_state['panel']
    
    st.divider()
    st.subheader("📊 Formatted Panel Data")
    
    st.write(f"**Shape:** {panel.shape[0]} rows × {panel.shape[1]} columns")
    
    # Show summary statistics
    with st.expander("📈 Summary Statistics"):
        numeric_cols = panel.select_dtypes(include=[np.number]).columns.tolist()
        if numeric_cols:
            st.dataframe(panel[numeric_cols].describe())
    
    # Show data - convert to avoid Arrow issues
    with st.expander("👁️ View Panel Data", expanded=True):
        # Create a copy for display to avoid Arrow serialization issues
        display_panel = panel.copy()
        st.dataframe(display_panel, use_container_width=True, height=400)
    
    # Visualization
    st.divider()
    st.subheader("📈 Visualize Data")
    
    try:
        countries = sorted([str(c) for c in panel['country'].unique()])
        variables = [col for col in panel.columns if col not in ['country', 'country_id', 'year', 'country_code']]
    except Exception as e:
        st.error(f"Error preparing visualization options: {e}")
        countries = []
        variables = []
    
    if not variables:
        st.warning("⚠️ No variables available for plotting")
    else:
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
            df_plot = panel[panel['country'].astype(str).isin(viz_countries)].copy()
            
            for country in viz_countries:
                df_country = df_plot[df_plot['country'].astype(str) == country].sort_values('year')
                
                if not df_country.empty:
                    fig, ax = plt.subplots(figsize=(10, 5))
                    
                    for var in viz_vars:
                        if var in df_country.columns:
                            # Remove NaN values for plotting
                            plot_data = df_country[['year', var]].dropna()
                            if not plot_data.empty:
                                ax.plot(plot_data['year'], plot_data[var], 
                                       marker='o', label=var, linewidth=2, markersize=6)
                    
                    ax.set_title(f"{country}", fontsize=14, fontweight='bold')
                    ax.set_xlabel("Year", fontsize=12)
                    ax.set_ylabel("Value", fontsize=12)
                    ax.legend(loc='best')
                    ax.grid(True, alpha=0.3)
                    plt.tight_layout()
                    
                    st.pyplot(fig)
                    plt.close(fig)
        else:
            st.info("👆 Select countries and variables to visualize")
    
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
        if 'viz_countries' in st.session_state and st.session_state.viz_countries:
            filtered = panel[panel['country'].astype(str).isin(st.session_state.viz_countries)]
            csv_filtered = filtered.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Filtered Panel (CSV)",
                data=csv_filtered,
                file_name="wdi_panel_filtered.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.button(
                label="📥 Download Filtered Panel (CSV)",
                disabled=True,
                use_container_width=True,
                help="Select countries in the visualization section first"
            )
    
    # Long format download
    if st.session_state.get('df_long') is not None:
        with st.expander("💾 Download Long Format Data"):
            csv_long = st.session_state['df_long'].to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Long Format (CSV)",
                data=csv_long,
                file_name="wdi_panel_long.csv",
                mime="text/csv",
                use_container_width=True
            )

else:
    st.info("👆 Upload a WDI Excel file to get started!")

# Footer
st.divider()
st.caption("Built with Streamlit • WDI Panel Data Builder v2.1")
