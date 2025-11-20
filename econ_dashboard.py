import streamlit as st
import pandas as pd
import numpy as np
from scipy.optimize import minimize
import plotly.graph_objects as go

# ---------- 0. UTILS ----------
def _denton_mat(n_high, n_low):
    m = n_high // n_low
    rows = np.repeat(np.arange(n_low), m)
    cols = np.arange(n_high)
    from scipy.sparse import coo_matrix
    return coo_matrix((np.ones(n_high), (rows, cols)), shape=(n_low, n_high)).toarray()

def denton_diff(low):
    tgt_idx = pd.date_range(low.index[0], low.index[-1] + pd.offsets.YearEnd(), freq='M')
    A = _denton_mat(len(tgt_idx), len(low))
    x0 = np.repeat(low.values, 12)
    def obj(x): return np.sum(np.diff(x)**2)
    cons = {'type': 'eq', 'fun': lambda x: A @ x - low.values}
    res = minimize(obj, x0, method='SLSQP', constraints=cons, options={'ftol': 1e-9})
    return pd.Series(res.x, index=tgt_idx, name=low.name)

def chow_lin(low, indicator, ar1=0.9):
    from statsmodels.regression.linear_model import OLS
    df = pd.concat([low, indicator], axis=1, join='inner').dropna()
    y_d, x_d = df.iloc[:, 0], df.iloc[:, 1]
    model = OLS(y_d, x_d.resample('Y').sum())
    res = model.fit()
    high = res.predict(x_d)
    annual_hat = high.resample('Y').sum()
    adj = (y_d / annual_hat).reindex(high.index, method='ffill')
    return high * adj

# ---------- 1. LOAD ----------
st.set_page_config(page_title="WDI → Tidy Panel", layout="wide")
st.title("WDI wide export ➜ tidy panel + interpolate + frequency + log")

uploaded = st.file_uploader("1. Upload WDI wide CSV", type="csv")
if uploaded is None: st.stop()

wide = pd.read_csv(uploaded)
year_cols = [c for c in wide.columns if c.startswith("20") and c.endswith("]")]
id_cols   = ["Country Name", "Series Name", "Series Code"]
tidy = (wide
        .melt(id_vars=id_cols, value_vars=year_cols,
              var_name="year_raw", value_name="value")
        .assign(year=lambda d: pd.to_numeric(d["year_raw"].str[:4], errors="coerce"))
        .assign(value=lambda d: pd.to_numeric(d["value"], errors="coerce"))
        .drop(columns=["year_raw"])
        .dropna(subset=["year", "value"]))

countries, indicators = tidy["Country Name"].unique(), tidy["Series Name"].unique()
y0, y1 = int(tidy["year"].min()), int(tidy["year"].max())
st.markdown(f"**Countries**: {len(countries)} | **Indicators**: {len(indicators)} | **Years**: {y0}–{y1}")

# ---------- 2. FILTER ----------
with st.sidebar:
    years = sorted(tidy["year"].unique())
    y0, y1 = st.select_slider("Year range", options=years, value=(y0, y1))
    sel_ind = st.multiselect("Indicators", indicators, default=indicators[:3])
    sel_cty = st.multiselect("Countries", sorted(countries), default=sorted(countries)[:10])

panel = (tidy
         .loc[tidy["year"].between(y0, y1)]
         .loc[tidy["Country Name"].isin(sel_cty)]
         .loc[tidy["Series Name"].isin(sel_ind)]
         .pivot_table(index=["Country Name", "year"],
                      columns="Series Name", values="value")
         .reset_index())

# ---------- 3. DOWNLOAD RAW ----------
csv_raw = panel.to_csv(index=False)
st.download_button("2. Download raw panel", csv_raw,
                   file_name=f"wdi_raw_{y0}_{y1}.csv", mime="text/csv")

# ---------- 4. POST-PROCESS ----------
with st.expander("4. Post-process (interpolate → frequency → log)"):
    st.info("Order: interpolate missing → frequency conversion → natural log. Any step can be disabled.")
    proc_note = []

    demo_ind = st.selectbox("Demo indicator", panel.columns[2:])
    demo_country = st.selectbox("Demo country", panel["Country Name"].unique())

    # --- 4a. INTERPOLATE ---
    do_interp = st.checkbox("Interpolate missing values", value=False)
    if do_interp:
        method_i = st.selectbox("Interpolation method", ["linear", "cubic", "pchip", "akima"])
        proc_note.append(f"interpolated ({method_i})")

        @st.cache_data
        def interp(panel, m):
            return panel.groupby("Country Name").apply(
                lambda g: g.set_index("year")[demo_ind].interpolate(method=m)).reset_index()

        panel_int = interp(panel, method_i)
        bef = panel.query("`Country Name`==@demo_country").set_index("year")[demo_ind]
        aft = panel_int.query("`Country Name`==@demo_country").set_index("year")[demo_ind]
        fig = go.Figure()
        fig.add_scatter(x=bef.index, y=bef, name="before", mode="markers+lines")
        fig.add_scatter(x=aft.index, y=aft, name="after",  mode="lines")
        st.plotly_chart(fig, use_container_width=True)
        panel = panel_int

    # --- 4b. FREQUENCY CONVERSION ---
    do_freq = st.checkbox("Convert annual → monthly", value=False)
    if do_freq:
        proc_note.append("frequency→monthly (Denton-diff, country-wise)")
        ann = (panel.query("`Country Name`==@demo_country")
                    .set_index("year")[demo_ind].dropna().asfreq('Y'))
        if ann.empty: st.warning("No annual data for demo"); st.stop()
        monthly = denton_diff(ann)
        fig = go.Figure()
        fig.add_scatter(x=ann.index, y=ann, name="annual", mode="markers")
        fig.add_scatter(x=monthly.index, y=monthly, name="monthly", mode="lines")
        st.plotly_chart(fig, use_container_width=True)
        out_frames = []
        for cty in panel["Country Name"].unique():
            sub = panel.query("`Country Name`==@cty").set_index("year")[demo_ind].dropna().asfreq('Y')
            if sub.empty: continue
            mth = denton_diff(sub)
            df_m = mth.to_frame(name=demo_ind).reset_index()
            df_m["Country Name"] = cty
            out_frames.append(df_m)
        panel = pd.concat(out_frames, ignore_index=True)

    # --- 4c. LOG TRANSFORM ---
    do_log = st.checkbox("Take natural log", value=False)
    if do_log:
        proc_note.append("logged")
        panel[demo_ind] = np.log(panel[demo_ind])
        st.write("Natural log applied.")

    # ---------- 5. FINAL DOWNLOAD ----------
    note = " → ".join(["raw"] + proc_note) if proc_note else "no processing"
    csv_final = panel.to_csv(index=False)
    st.download_button(
            label=f"5. Download processed panel ({note})",
            data=csv_final,
            file_name=f"wdi_processed_{y0}_{y1}.csv",
            mime="text/csv"
    )
