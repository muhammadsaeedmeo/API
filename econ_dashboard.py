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

# ---------- 1. LOAD ----------
st.set_page_config(page_title="WDI batch processor", layout="wide")
st.title("WDI ➜ tidy panel + batch interpolate / frequency / log")

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
st.markdown(f"**Countries** : {len(countries)}  |  **Indicators** : {len(indicators)}  |  **Years** : {y0}–{y1}")

# ---------- 2. FILTER (ALL-AT-ONCE) ----------
with st.sidebar:
    years = sorted(tidy["year"].unique())
    y0, y1 = st.select_slider("Year range", options=years, value=(y0, y1))
    sel_ind = st.multiselect("Indicators", indicators, default=indicators)
    sel_cty = st.multiselect("Countries", sorted(countries), default=sorted(countries))

panel = (tidy
         .loc[tidy["year"].between(y0, y1)]
         .loc[tidy["Country Name"].isin(sel_cty)]
         .loc[tidy["Series Name"].isin(sel_ind)]
         .pivot_table(index=["Country Name", "year"],
                      columns="Series Name", values="value")
         .reset_index())

# ---------- 3. GLOBAL TOGGLES ----------
with st.sidebar:
    st.subheader("Processing pipeline")
    do_interp = st.checkbox("Interpolate missing", value=False)
    do_freq   = st.checkbox("Annual → monthly",   value=False)
    do_log    = st.checkbox("Natural log",        value=False)
    method_i  = st.selectbox("Interpolation", ["linear", "cubic", "pchip", "akima"])

# ---------- 4. PIPELINE (COUNTRY-WISE) ----------
note_parts = []
if do_interp: note_parts.append(f"interpolated({method_i})")
if do_freq:   note_parts.append("freq→monthly")
if do_log:    note_parts.append("logged")
note_str = " → ".join(note_parts) if note_parts else "no processing"

def country_pipe(g):
    g = g.copy().set_index("year")
    for col in sel_ind:
        s = g[col].copy()
        if do_interp and s.isna().any():
            s = s.interpolate(method=method_i)
        if do_freq:
            s = s.dropna()
            if s.empty: continue
            s.index = pd.to_datetime(s.index, format='%Y')   # FIX: DatetimeIndex
            s = denton_diff(s.asfreq('Y'))
        if do_log:
            s = np.log(s)
        g[col] = s
    return g.reset_index()

if any([do_interp, do_freq, do_log]):
    st.info(f"Pipeline: {note_str}  (country-specific)")
    processed = []
    for cty in sel_cty:
        sub = panel.query("`Country Name` == @cty")
        if sub.empty: continue
        processed.append(country_pipe(sub))
    panel_proc = pd.concat(processed, ignore_index=True) if processed else panel
else:
    panel_proc = panel

# ---------- 5. BEFORE / AFTER WORLD CHART ----------
if any([do_interp, do_freq, do_log]) and not panel_proc.empty:
    st.subheader("World aggregate: before vs after")
    bef_world = panel.groupby("year")[sel_ind].mean()
    aft_world = panel_proc.groupby("year")[sel_ind].mean()
    fig = go.Figure()
    for ind in sel_ind[:3]:
        fig.add_scatter(x=bef_world.index, y=bef_world[ind], name=f"{ind} (before)", mode="markers")
        fig.add_scatter(x=aft_world.index, y=aft_world[ind], name=f"{ind} (after)",  mode="lines")
    st.plotly_chart(fig, use_container_width=True)

# ---------- 6. DOWNLOAD ----------
csv_final = panel_proc.to_csv(index=False)
st.download_button(
        label=f"Download processed panel ({note_str})",
        data=csv_final,
        file_name=f"wdi_processed_{y0}_{y1}.csv",
        mime="text/csv"
)
