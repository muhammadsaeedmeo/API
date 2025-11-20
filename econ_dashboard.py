import streamlit as st
import pandas as pd

st.set_page_config(page_title="WDI → Tidy Panel", layout="wide")
st.title("WDI wide export ➜ tidy panel")

# ---------- 1. LOAD ----------
uploaded = st.file_uploader("1. Upload WDI wide CSV", type="csv")
if uploaded is None:
    st.stop()

wide = pd.read_csv(uploaded)

# ---------- 2. TIDY (MELT) ----------
year_cols = [c for c in wide.columns if c.startswith("20") and c.endswith("]")]
id_cols   = ["Country Name", "Series Name", "Series Code"]
tidy      = (wide
             .melt(id_vars=id_cols,
                   value_vars=year_cols,
                   var_name="year_raw",
                   value_name="value")
             .assign(year=lambda d: pd.to_numeric(d["year_raw"].str[:4], errors="coerce"))
             # --- coerce value to numeric, turn ".." into NaN ---
             .assign(value=lambda d: pd.to_numeric(d["value"], errors="coerce"))
             .drop(columns=["year_raw"])
             .dropna(subset=["year", "value"]))   # drops NaN years & missing values
# ---------- 3. META ----------
countries   = tidy["Country Name"].unique()
indicators  = tidy["Series Name"].unique()
year_range  = tidy["year"].agg(["min", "max"])
st.markdown(f"""
- **Countries** : {len(countries)}  
- **Indicators**: {len(indicators)}  
- **Years**     : {int(year_range['min'])} – {int(year_range['max'])}
""")

# ---------- 4. USER FILTERS ----------
with st.sidebar:
    y0, y1 = st.select_slider(
            "Year range",
            options=sorted(tidy["year"].unique()),
            value=(int(year_range["min"]), int(year_range["max"])))
    sel_ind = st.multiselect("Indicators", indicators, default=indicators[:3])
    sel_cty = st.multiselect("Countries",  sorted(countries),
                             default=sorted(countries)[:10])

# ---------- 5. BUILD PANEL ----------
panel = (tidy
         .loc[tidy["year"].between(y0, y1)]
         .loc[tidy["Country Name"].isin(sel_cty)]
         .loc[tidy["Series Name"].isin(sel_ind)]
         .pivot_table(index=["Country Name", "year"],
                      columns="Series Name",
                      values="value")
         .reset_index())

# ---------- 6. DISPLAY / DOWNLOAD ----------
st.write("Preview (first 50 rows):")
st.dataframe(panel.head(50))

csv = panel.to_csv(index=False)
st.download_button(
        label="2. Download tidy panel CSV",
        data=csv,
        file_name=f"wdi_panel_{y0}_{y1}.csv",
        mime="text/csv"
)
# ---------- 7. INTERPOLATION SECTION ----------
if not panel.empty:
    with st.expander("3. Interpolate missing values"):
        # choose one indicator that has NaNs
        cand = [c for c in panel.columns
                if panel[c].isna().any() and pd.api.types.is_numeric_dtype(panel[c])]
        if not cand:
            st.info("No missing numeric data in the selected slice.")
        else:
            indict = st.selectbox("Indicator to interpolate", cand)
            method = st.selectbox("Method",
                                  ["linear", "cubic", "pchip", "akima"],
                                  help="PCHIP = shape-preserving, no overshoot")

            # split by first country for demo chart
            demo_country = panel["Country Name"].iloc[0]
            ser = (panel.query("`Country Name` == @demo_country")
                        .set_index("year")[indict])
            ser_int = ser.interpolate(method=method)

            pct = 100 * ser.isna().mean()
            st.write(f"Missing values: **{pct:.1f} %**  ({ser.isna().sum()} / {len(ser)})")

            chart_df = pd.concat({"original": ser, "interpolated": ser_int}, axis=1)
            st.line_chart(chart_df)

            # add interpolated column to the full panel
            new_col = f"{indict}_{method}"
            panel[new_col] = (panel.groupby("Country Name")[indict]
                                   .transform(lambda s: s.interpolate(method=method)))

            csv_int = panel.to_csv(index=False)
            st.download_button(
                    label=f"Download panel + {new_col}",
                    data=csv_int,
                    file_name=f"wdi_panel_{y0}_{y1}_{method}.csv",
                    mime="text/csv"
            )
