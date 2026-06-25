"""
day5_dashboard.py  --  Bluestock MF Capstone  --  Day 5 Streamlit Dashboard
Run:  streamlit run scripts/day5_dashboard.py
"""
from pathlib import Path
import warnings, sqlite3
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from scipy import stats as sp_stats
from scipy.optimize import minimize

warnings.filterwarnings("ignore")

try:
    import streamlit as st
except ImportError:
    raise SystemExit("Install streamlit:  pip install streamlit plotly")

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE   = Path(__file__).resolve().parents[1]
DB     = BASE / "data" / "db" / "bluestock_mf.db"
PROC   = BASE / "data" / "processed"

RISK_FREE    = 0.065
TRADING_DAYS = 252

# ── Palette ────────────────────────────────────────────────────────────────────
NAVY   = "#0B2447"
TEAL   = "#19376D"
ACCENT = "#0096C7"
GREEN  = "#27AE60"
RED    = "#E74C3C"
ORANGE = "#E67E22"
RISK_COLORS = {"Low":GREEN,"Moderate":"#F1C40F",
               "Moderately High":ORANGE,"High":RED}

# ── Data ───────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load():
    with sqlite3.connect(DB) as conn:
        fund  = pd.read_sql("SELECT * FROM dim_fund", conn)
        nav   = pd.read_sql("SELECT * FROM fact_nav ORDER BY scheme_code, date_key", conn)
        perf  = pd.read_sql("SELECT p.*, f.scheme_name, f.sub_category, f.category, f.amc_name, f.risk_level, f.expense_ratio FROM fact_performance p JOIN dim_fund f ON p.scheme_code=f.scheme_code", conn)
        txn   = pd.read_sql("SELECT * FROM fact_transactions", conn)
        aum   = pd.read_sql("SELECT * FROM fact_aum", conn)
        sip   = pd.read_sql("SELECT * FROM ref_sip_inflows ORDER BY month", conn)
        fol   = pd.read_sql("SELECT * FROM ref_folio_count ORDER BY month", conn)
        bm    = pd.read_sql("SELECT * FROM ref_benchmark_indices ORDER BY index_name, date", conn)
        cat   = pd.read_sql("SELECT * FROM ref_category_inflows", conn)
        ptf   = pd.read_sql("SELECT * FROM ref_portfolio_holdings", conn)
    nav["date"]  = pd.to_datetime(nav["date_key"])
    txn["date"]  = pd.to_datetime(txn["date_key"])
    sip["month"] = pd.to_datetime(sip["month"])
    fol["month"] = pd.to_datetime(fol["month"])
    aum["date"]  = pd.to_datetime(aum["date_key"])
    bm["date"]   = pd.to_datetime(bm["date"])
    cat["month"] = pd.to_datetime(cat["month"])
    # Load scorecard if exists
    sc_path = PROC / "fund_scorecard.csv"
    scorecard = pd.read_csv(sc_path) if sc_path.exists() else perf[['scheme_code','scheme_name']].assign(composite_score=50)
    return fund, nav, perf, txn, aum, sip, fol, bm, cat, ptf, scorecard

# ── Helpers ────────────────────────────────────────────────────────────────────
def fmt_pct(v): return f"{v*100:.2f}%" if pd.notna(v) else "N/A"
def fmt_cr(v):  return f"₹{v:,.0f} Cr" if pd.notna(v) else "N/A"
def fmt_num(v, d=3): return f"{v:.{d}f}" if pd.notna(v) else "N/A"

# ══════════════════════════════════════════════════════════════════════════════
# PAGE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def page_executive(fund, nav, perf, txn, sip, fol, scorecard):
    st.title("📊 Executive Summary")

    # Slicers
    c1,c2,c3 = st.columns(3)
    sel_cat  = c1.multiselect("Category",  sorted(perf["category"].dropna().unique()),  default=sorted(perf["category"].dropna().unique()))
    sel_risk = c2.multiselect("Risk Level",sorted(perf["risk_level"].dropna().unique()),default=sorted(perf["risk_level"].dropna().unique()))
    sel_amc  = c3.multiselect("AMC",       sorted(perf["amc_name"].dropna().unique()),  default=sorted(perf["amc_name"].dropna().unique()))

    pf = perf[perf["category"].isin(sel_cat) & perf["risk_level"].isin(sel_risk) & perf["amc_name"].isin(sel_amc)]
    st.divider()

    # KPIs row 1
    k = st.columns(6)
    k[0].metric("Total Funds",    len(pf))
    k[1].metric("Categories",     pf["category"].nunique())
    k[2].metric("AMCs",           pf["amc_name"].nunique())
    k[3].metric("Avg 1Y Return",  f"{pf['return_1yr_pct'].mean():.1f}%")
    k[4].metric("Best 3Y CAGR",   f"{pf['return_3yr_pct'].max():.1f}%")
    k[5].metric("Best Sharpe",    f"{pf['sharpe_ratio'].max():.2f}")
    st.divider()

    # KPIs row 2 — industry
    k2 = st.columns(4)
    latest_sip = sip["sip_inflow_crore"].iloc[-1] if len(sip) else 0
    k2[0].metric("Latest Monthly SIP", f"₹{latest_sip:,.0f} Cr")
    k2[1].metric("Industry Folios",    f"{fol['total_folios_crore'].iloc[-1]:.2f} Cr" if len(fol) else "N/A")
    total_txn_cr = txn["amount_inr"].sum() / 1e7
    k2[2].metric("Total Txn Amount",   f"₹{total_txn_cr:,.0f} Cr")
    k2[3].metric("Funds Sharpe > 1",   str((perf["sharpe_ratio"] > 1).sum()))
    st.divider()

    # Top/Bottom performers
    c_top, c_bot = st.columns(2)
    with c_top:
        st.subheader("Top 5 — 3Y Return")
        top5 = pf.sort_values("return_3yr_pct", ascending=False).head(5)
        fig = px.bar(top5, x="return_3yr_pct", y="scheme_name", orientation="h",
                     color="return_3yr_pct", color_continuous_scale="Greens",
                     text=top5["return_3yr_pct"].apply(lambda x: f"{x:.1f}%"),
                     labels={"return_3yr_pct":"3Y Return%","scheme_name":""})
        fig.update_layout(height=260, showlegend=False,
                          plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
    with c_bot:
        st.subheader("Bottom 5 — 3Y Return")
        bot5 = pf.sort_values("return_3yr_pct").head(5)
        fig2 = px.bar(bot5, x="return_3yr_pct", y="scheme_name", orientation="h",
                      color="return_3yr_pct", color_continuous_scale="Reds_r",
                      text=bot5["return_3yr_pct"].apply(lambda x: f"{x:.1f}%"),
                      labels={"return_3yr_pct":"3Y Return%","scheme_name":""})
        fig2.update_layout(height=260, showlegend=False,
                           plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        fig2.update_traces(textposition="outside")
        st.plotly_chart(fig2, use_container_width=True)

    # Category donut + Risk-Return
    c_do, c_sc = st.columns(2)
    with c_do:
        st.subheader("Category Breakdown")
        cc = pf.groupby("sub_category").size().reset_index(name="count")
        fig3 = px.pie(cc, names="sub_category", values="count", hole=0.42)
        fig3.update_layout(height=320, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig3, use_container_width=True)
    with c_sc:
        st.subheader("Risk vs Return (3Y)")
        fig4 = px.scatter(pf, x="std_dev_ann_pct", y="return_3yr_pct",
                          color="risk_level", size="aum_crore",
                          hover_name="scheme_name",
                          color_discrete_map=RISK_COLORS,
                          labels={"std_dev_ann_pct":"Ann Volatility %","return_3yr_pct":"3Y Return %"})
        fig4.update_layout(height=320, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig4, use_container_width=True)

    # Full table
    st.subheader("Fund Snapshot")
    disp = pf[["scheme_name","sub_category","amc_name","risk_level",
               "return_1yr_pct","return_3yr_pct","sharpe_ratio",
               "max_drawdown_pct","expense_ratio_pct","aum_crore"]].copy()
    disp.columns = ["Fund","Sub-Cat","AMC","Risk","1Y%","3Y%","Sharpe","MaxDD%","ER%","AUM Cr"]
    for c in ["1Y%","3Y%","MaxDD%","ER%"]:
        disp[c] = disp[c].round(2)
    disp["Sharpe"] = disp["Sharpe"].round(3)
    disp["AUM Cr"] = disp["AUM Cr"].apply(lambda x: f"{x:,}" if pd.notna(x) else "N/A")
    st.dataframe(disp, use_container_width=True, height=420)


def page_nav_performance(fund, nav, bm):
    st.title("📈 Fund Performance")

    c1,c2,c3 = st.columns([3,2,2])
    sel_funds = c1.multiselect("Select Funds (up to 6)",
                               fund["scheme_name"].tolist(),
                               default=fund["scheme_name"].tolist()[:4],
                               max_selections=6)
    d_from = c2.date_input("From", value=pd.to_datetime("2022-01-01"))
    d_to   = c3.date_input("To",   value=nav["date"].max())

    if not sel_funds:
        st.warning("Select at least one fund."); return

    sel_codes = fund[fund["scheme_name"].isin(sel_funds)]["scheme_code"].values
    nav_f = nav[nav["scheme_code"].isin(sel_codes) &
                (nav["date"] >= pd.Timestamp(d_from)) &
                (nav["date"] <= pd.Timestamp(d_to))].copy()

    st.divider()

    # Indexed NAV
    st.subheader("Indexed NAV (Base=100 at start)")
    fig = go.Figure()
    for code in sel_codes:
        f = nav_f[nav_f["scheme_code"]==code].sort_values("date")
        if f.empty: continue
        idx  = f["nav"] / f["nav"].iloc[0] * 100
        name = fund.loc[fund["scheme_code"]==code,"scheme_name"].values[0]
        fig.add_trace(go.Scatter(x=f["date"], y=idx, name=name[:28], mode="lines", line=dict(width=2)))
    fig.add_hline(y=100, line_dash="dot", line_color="gray", opacity=0.5)
    fig.update_layout(height=420, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02),
                      yaxis_title="Indexed NAV", xaxis_title="Date")
    st.plotly_chart(fig, use_container_width=True)

    c_roll, c_vol = st.columns(2)
    with c_roll:
        st.subheader("Rolling 1Y Return (%)")
        fig2 = go.Figure()
        for code in sel_codes:
            f = nav_f[nav_f["scheme_code"]==code].sort_values("date").set_index("date")
            if len(f) < 252: continue
            r = f["nav"].pct_change(252) * 100
            fig2.add_trace(go.Scatter(x=r.index, y=r.values,
                name=fund.loc[fund["scheme_code"]==code,"scheme_name"].values[0][:22],
                mode="lines", line=dict(width=1.5)))
        fig2.add_hline(y=0, line_color="gray", line_dash="dot")
        fig2.update_layout(height=320, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)

    with c_vol:
        st.subheader("Rolling 90-Day Volatility (%)")
        fig3 = go.Figure()
        for code in sel_codes:
            f = nav_f[nav_f["scheme_code"]==code].sort_values("date")
            if f.empty or "daily_return" not in f.columns: continue
            rv = f["daily_return"].rolling(90, min_periods=60).std() * np.sqrt(252) * 100
            fig3.add_trace(go.Scatter(x=f["date"], y=rv,
                name=fund.loc[fund["scheme_code"]==code,"scheme_name"].values[0][:22],
                mode="lines", line=dict(width=1.5)))
        fig3.update_layout(height=320, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig3, use_container_width=True)


def page_risk(perf, nav, fund):
    st.title("⚠️ Risk Analytics")

    c1,c2 = st.columns(2)
    sel_cat  = c1.multiselect("Category", sorted(perf["category"].dropna().unique()),
                              default=sorted(perf["category"].dropna().unique()))
    sel_risk = c2.multiselect("Risk", sorted(perf["risk_level"].dropna().unique()),
                              default=sorted(perf["risk_level"].dropna().unique()))

    pf = perf[perf["category"].isin(sel_cat) & perf["risk_level"].isin(sel_risk)]
    st.divider()

    k = st.columns(5)
    k[0].metric("Avg Vol %",    f"{pf['std_dev_ann_pct'].mean():.1f}%")
    k[1].metric("Avg MaxDD %",  f"{pf['max_drawdown_pct'].mean():.1f}%")
    k[2].metric("Avg Sharpe",   f"{pf['sharpe_ratio'].mean():.3f}")
    k[3].metric("Avg Beta",     f"{pf['beta'].mean():.3f}")
    k[4].metric("Avg Sortino",  f"{pf['sortino_ratio'].mean():.3f}")
    st.divider()

    c_v, c_m = st.columns(2)
    with c_v:
        st.subheader("Volatility Ranking")
        vs = pf.sort_values("std_dev_ann_pct", ascending=True)
        fig = go.Figure(go.Bar(x=vs["std_dev_ann_pct"], y=[n[:25] for n in vs["scheme_name"]],
                               orientation="h",
                               marker_color=[RISK_COLORS.get(r,"#888") for r in vs["risk_level"]],
                               text=[f"{v:.1f}%" for v in vs["std_dev_ann_pct"]],
                               textposition="outside"))
        fig.update_layout(height=420, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                          xaxis_title="Annualised Vol %")
        st.plotly_chart(fig, use_container_width=True)

    with c_m:
        st.subheader("Max Drawdown Ranking")
        ms = pf.sort_values("max_drawdown_pct")
        fig2 = go.Figure(go.Bar(x=ms["max_drawdown_pct"], y=[n[:25] for n in ms["scheme_name"]],
                                orientation="h",
                                marker_color=[RISK_COLORS.get(r,"#888") for r in ms["risk_level"]],
                                text=[f"{v:.1f}%" for v in ms["max_drawdown_pct"]],
                                textposition="outside"))
        fig2.update_layout(height=420, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                           xaxis_title="Max Drawdown %")
        st.plotly_chart(fig2, use_container_width=True)

    # Drawdown history
    st.subheader("Drawdown History — All Equity Funds")
    eq_codes = fund[fund["category"]=="Equity"]["scheme_code"].values
    fig3 = go.Figure()
    for code in eq_codes:
        f = nav[nav["scheme_code"]==code].sort_values("date")
        if len(f) < 100: continue
        peak = f["nav"].cummax()
        dd   = (f["nav"] - peak) / peak * 100
        fig3.add_trace(go.Scatter(x=f["date"], y=dd,
            name=fund.loc[fund["scheme_code"]==code,"scheme_name"].values[0][:22],
            mode="lines", line=dict(width=1), fill="tozeroy", opacity=0.3))
    fig3.add_hline(y=0, line_color="white", line_dash="dot", opacity=0.3)
    fig3.update_layout(height=360, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                       yaxis_title="Drawdown %",
                       legend=dict(orientation="h", font=dict(size=7)))
    st.plotly_chart(fig3, use_container_width=True)

    # Full risk table
    st.subheader("Full Risk Metrics Table")
    rtbl = pf[["scheme_name","sub_category","risk_level","std_dev_ann_pct",
               "max_drawdown_pct","sharpe_ratio","sortino_ratio","beta","alpha","expense_ratio_pct"]].copy()
    rtbl.columns = ["Fund","Sub-Cat","Risk","Vol%","MaxDD%","Sharpe","Sortino","Beta","Alpha%","ER%"]
    for c in ["Vol%","MaxDD%","Alpha%","ER%"]: rtbl[c] = rtbl[c].round(2)
    for c in ["Sharpe","Sortino","Beta"]: rtbl[c] = rtbl[c].round(3)
    st.dataframe(rtbl, use_container_width=True, height=400)


def page_industry(txn, sip, fol, aum, cat):
    st.title("🏭 Industry Analytics")

    c1,c2 = st.columns(2)
    with c1:
        st.subheader("Monthly SIP Inflows (₹ Crore)")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=sip["month"], y=sip["sip_inflow_crore"],
                                 mode="lines+markers", fill="tozeroy",
                                 line=dict(color=ACCENT, width=2), marker=dict(size=3)))
        # Annotate max
        mx = sip.loc[sip["sip_inflow_crore"].idxmax()]
        fig.add_annotation(x=mx["month"], y=mx["sip_inflow_crore"],
                           text=f"ATH: ₹{mx['sip_inflow_crore']:,.0f} Cr",
                           showarrow=True, arrowhead=2, font=dict(color="green",size=10))
        fig.update_layout(height=340, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                          yaxis_title="₹ Crore")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Folio Count Growth (Crore)")
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=fol["month"], y=fol["total_folios_crore"],
                                  name="Total", mode="lines+markers",
                                  line=dict(color=NAVY, width=2.5)))
        fig2.add_trace(go.Scatter(x=fol["month"], y=fol["equity_folios_crore"],
                                  name="Equity", fill="tozeroy",
                                  line=dict(color=GREEN, width=1.5), opacity=0.7))
        fig2.update_layout(height=340, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                           yaxis_title="Crore Folios")
        st.plotly_chart(fig2, use_container_width=True)

    # AUM by fund house grouped bar
    st.subheader("AUM by Fund House (₹ Lakh Crore)")
    aum["year"] = aum["date"].dt.year
    aum_y = aum.groupby(["year","fund_house"])["aum_lakh_crore"].sum().reset_index()
    fig3  = px.bar(aum_y, x="fund_house", y="aum_lakh_crore", color="year",
                   barmode="group", text_auto=".1f",
                   labels={"aum_lakh_crore":"AUM (₹ Lakh Cr)","fund_house":"Fund House"})
    fig3.update_layout(height=380, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                       xaxis_tickangle=-30)
    st.plotly_chart(fig3, use_container_width=True)

    # Category inflow heatmap
    st.subheader("Category Inflow Heatmap (₹ Crore)")
    cat["month_str"] = cat["month"].dt.strftime("%b-%y")
    pivot = cat.pivot_table(index="category", columns="month_str",
                            values="net_inflow_crore", aggfunc="sum")
    month_order = cat.sort_values("month")["month_str"].unique()
    pivot = pivot.reindex(columns=month_order)
    fig4 = px.imshow(pivot, text_auto=".0f", aspect="auto",
                     color_continuous_scale="RdYlGn", color_continuous_midpoint=0,
                     labels=dict(color="Net Inflow ₹Cr"))
    fig4.update_layout(height=380, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    fig4.update_xaxes(tickangle=-40)
    st.plotly_chart(fig4, use_container_width=True)

    # Investor demographics
    st.subheader("Investor Transactions Analysis")
    cd1, cd2, cd3 = st.columns(3)
    with cd1:
        age_c = txn["age_group"].value_counts().reset_index()
        age_c.columns = ["age","count"]
        fig5 = px.pie(age_c, names="age", values="count", hole=0.4,
                      title="Age Group Distribution")
        fig5.update_layout(height=280, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig5, use_container_width=True)
    with cd2:
        gen_c = txn.groupby("gender")["amount_inr"].sum().reset_index()
        fig6 = px.pie(gen_c, names="gender", values="amount_inr",
                      hole=0.4, title="Investment by Gender")
        fig6.update_layout(height=280, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig6, use_container_width=True)
    with cd3:
        tier = txn.groupby("city_tier")["amount_inr"].sum().reset_index()
        fig7 = px.pie(tier, names="city_tier", values="amount_inr",
                      hole=0.4, title="T30 vs B30 Split",
                      color_discrete_map={"T30":"#27ae60","B30":"#e67e22"})
        fig7.update_layout(height=280, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig7, use_container_width=True)

    # SIP by state
    st.subheader("SIP Investment by State")
    st_sip = (txn[txn["transaction_type"]=="SIP"]
              .groupby("state")["amount_inr"].sum()
              .sort_values(ascending=True).reset_index())
    st_sip["crore"] = st_sip["amount_inr"] / 1e7
    fig8 = px.bar(st_sip, x="crore", y="state", orientation="h",
                  text=st_sip["crore"].apply(lambda x: f"₹{x:.0f}Cr"),
                  color="crore", color_continuous_scale="Blues")
    fig8.update_layout(height=420, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                       xaxis_title="SIP Amount (₹ Crore)")
    fig8.update_traces(textposition="outside")
    st.plotly_chart(fig8, use_container_width=True)


def page_portfolio(nav, fund, perf):
    st.title("🎯 Portfolio Optimiser")

    eq_fund = fund[fund["category"].isin(["Equity","Hybrid","Index"])]
    sel = st.multiselect("Select Funds (2-10 for optimisation)",
                         eq_fund["scheme_name"].tolist(),
                         default=eq_fund["scheme_name"].tolist()[:5])
    inv = st.number_input("Investment Amount (₹)", 10000, 10000000, 100000, 10000)

    if len(sel) < 2:
        st.warning("Select at least 2 funds"); return

    codes = eq_fund[eq_fund["scheme_name"].isin(sel)]["scheme_code"].values
    nav_f = nav[nav["scheme_code"].isin(codes)].copy()
    pivot = nav_f.pivot_table(index="date", columns="scheme_code", values="daily_return")
    pivot = pivot.dropna(axis=1, thresh=int(len(pivot)*0.9)).dropna()

    n       = pivot.shape[1]
    mu_vec  = pivot.mean().values * TRADING_DAYS
    cov_mat = pivot.cov().values  * TRADING_DAYS
    fund_names = [fund.loc[fund["scheme_code"]==c,"scheme_name"].values[0] for c in pivot.columns]

    def pstats(w):
        r = w @ mu_vec; v = np.sqrt(w @ cov_mat @ w); return r, v
    def neg_sh(w):
        r,v = pstats(w); return -(r-RISK_FREE)/v if v>0 else 0

    cons   = [{"type":"eq","fun":lambda w: np.sum(w)-1}]
    bounds = [(0,1)]*n
    init   = np.ones(n)/n
    res_s  = minimize(neg_sh,        init, method="SLSQP", bounds=bounds, constraints=cons)
    res_m  = minimize(lambda w: pstats(w)[1], init, method="SLSQP", bounds=bounds, constraints=cons)
    opt_rs, opt_vs = pstats(res_s.x)
    opt_rm, opt_vm = pstats(res_m.x)

    k = st.columns(4)
    k[0].metric("Max Sharpe Return", f"{opt_rs*100:.1f}%")
    k[1].metric("Max Sharpe Vol",    f"{opt_vs*100:.1f}%")
    k[2].metric("Min Vol Return",    f"{opt_rm*100:.1f}%")
    k[3].metric("Min Volatility",    f"{opt_vm*100:.1f}%")
    st.divider()

    c_ef, c_wt = st.columns(2)
    with c_ef:
        st.subheader("Efficient Frontier")
        np.random.seed(42)
        sim_r, sim_v, sim_sr = [], [], []
        for _ in range(2000):
            w = np.random.dirichlet(np.ones(n))
            r, v = pstats(w)
            sim_r.append(r); sim_v.append(v)
            sim_sr.append((r-RISK_FREE)/v if v>0 else 0)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=sim_v, y=sim_r, mode="markers",
            marker=dict(color=sim_sr, colorscale="RdYlGn", size=4, opacity=0.4,
                        colorbar=dict(title="Sharpe")), name="Portfolios"))
        fig.add_trace(go.Scatter(x=[opt_vs], y=[opt_rs], mode="markers",
            marker=dict(symbol="star", size=18, color="gold", line=dict(color="black",width=1)),
            name=f"Max Sharpe ({(opt_rs-RISK_FREE)/opt_vs:.2f})"))
        fig.add_trace(go.Scatter(x=[opt_vm], y=[opt_rm], mode="markers",
            marker=dict(symbol="diamond", size=14, color="cyan", line=dict(color="black",width=1)),
            name="Min Vol"))
        fig.update_layout(height=380, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                          xaxis_title="Volatility", yaxis_title="Return")
        st.plotly_chart(fig, use_container_width=True)

    with c_wt:
        st.subheader("Optimal Weights")
        tab1, tab2 = st.tabs(["Max Sharpe", "Min Volatility"])
        for tab, wts, lbl in [(tab1, res_s.x, "Max Sharpe"), (tab2, res_m.x, "Min Vol")]:
            with tab:
                wdf = pd.DataFrame({"Fund":[n[:28] for n in fund_names],
                                    "Weight%":(wts*100).round(2),
                                    "Amount (₹)":(wts*inv).round(0).astype(int)})
                wdf = wdf[wdf["Weight%"]>0.5].sort_values("Weight%", ascending=False)
                fig_p = px.pie(wdf, names="Fund", values="Weight%", hole=0.38)
                fig_p.update_layout(height=260, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                tab.plotly_chart(fig_p, use_container_width=True)
                tab.dataframe(wdf, use_container_width=True)

    # SIP Calculator
    st.subheader("💰 SIP Calculator")
    sc1, sc2, sc3 = st.columns(3)
    monthly_sip = sc1.number_input("Monthly SIP (₹)", 500, 1000000, 10000, 500)
    sip_years   = sc2.slider("Period (Years)", 1, 30, 10)
    exp_ret     = sc3.slider("Expected Return %", 5, 30, 12)

    months      = sip_years * 12
    mr          = (1 + exp_ret/100)**(1/12) - 1
    fv          = monthly_sip * (((1+mr)**months - 1) / mr) * (1+mr)
    invested    = monthly_sip * months
    gain        = fv - invested

    kk = st.columns(4)
    kk[0].metric("Invested",    f"₹{invested:,.0f}")
    kk[1].metric("Future Value",f"₹{fv:,.0f}")
    kk[2].metric("Total Gain",  f"₹{gain:,.0f}")
    kk[3].metric("Wealth Ratio",f"{fv/invested:.2f}x")

    dates_sip = pd.date_range(pd.Timestamp.today(), periods=months, freq="ME")
    fv_curve  = [monthly_sip * (((1+mr)**m - 1)/mr)*(1+mr) for m in range(1, months+1)]
    inv_curve = [monthly_sip * m for m in range(1, months+1)]
    fig_sip = go.Figure()
    fig_sip.add_trace(go.Scatter(x=dates_sip, y=fv_curve, name="Portfolio Value",
                                 fill="tozeroy", line=dict(color=GREEN)))
    fig_sip.add_trace(go.Scatter(x=dates_sip, y=inv_curve, name="Amount Invested",
                                 line=dict(color=ORANGE, dash="dash")))
    fig_sip.update_layout(height=300, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                          yaxis_title="₹ Value")
    st.plotly_chart(fig_sip, use_container_width=True)


def page_comparison(fund, nav, perf):
    st.title("🔍 Fund Comparison")

    names = fund["scheme_name"].tolist()
    c1,c2 = st.columns(2)
    fa = c1.selectbox("Fund A", names, index=0)
    fb = c2.selectbox("Fund B", names, index=min(3, len(names)-1))

    if fa == fb:
        st.warning("Select two different funds."); return

    ca = int(fund.loc[fund["scheme_name"]==fa,"scheme_code"].iloc[0])
    cb = int(fund.loc[fund["scheme_name"]==fb,"scheme_code"].iloc[0])

    pa = perf[perf["scheme_code"]==ca].iloc[0] if len(perf[perf["scheme_code"]==ca]) else None
    pb = perf[perf["scheme_code"]==cb].iloc[0] if len(perf[perf["scheme_code"]==cb]) else None
    st.divider()

    if pa is not None and pb is not None:
        st.subheader("Side-by-Side Metrics Comparison")
        metrics = [
            ("1Y Return %",       "return_1yr_pct",   True,  True),
            ("3Y Return %",       "return_3yr_pct",   True,  True),
            ("5Y Return %",       "return_5yr_pct",   True,  True),
            ("Volatility %",      "std_dev_ann_pct",  True,  False),
            ("Max Drawdown %",    "max_drawdown_pct", True,  False),
            ("Sharpe Ratio",      "sharpe_ratio",     False, True),
            ("Sortino Ratio",     "sortino_ratio",    False, True),
            ("Beta",              "beta",             False, None),
            ("Alpha %",           "alpha",            True,  True),
            ("Expense Ratio %",   "expense_ratio_pct",True,  False),
        ]
        rows = {"Metric":[], fa[:20]:[], fb[:20]:[], "Winner":[]}
        for lbl, col, is_pct, hb in metrics:
            va = pa.get(col); vb = pb.get(col)
            if va is None or pd.isna(va): continue
            sc = 100 if is_pct else 1
            fmta = f"{va*sc:.2f}"; fmtb = f"{vb*sc:.2f}" if not pd.isna(vb) else "N/A"
            winner = (fa[:15] if (hb is True and va>vb) or (hb is False and abs(va)<abs(vb))
                      else fb[:15] if hb is not None else "--")
            rows["Metric"].append(lbl)
            rows[fa[:20]].append(fmta)
            rows[fb[:20]].append(fmtb)
            rows["Winner"].append(f"★ {winner}")
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

    # NAV chart
    st.subheader("NAV Comparison (Indexed=100)")
    nav_a = nav[nav["scheme_code"]==ca].sort_values("date")
    nav_b = nav[nav["scheme_code"]==cb].sort_values("date")
    if not nav_a.empty and not nav_b.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=nav_a["date"], y=nav_a["nav"]/nav_a["nav"].iloc[0]*100,
                                 name=fa[:28], line=dict(color=ACCENT, width=2)))
        fig.add_trace(go.Scatter(x=nav_b["date"], y=nav_b["nav"]/nav_b["nav"].iloc[0]*100,
                                 name=fb[:28], line=dict(color=ORANGE, width=2)))
        fig.add_hline(y=100, line_dash="dot", line_color="gray", opacity=0.4)
        fig.update_layout(height=380, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                          yaxis_title="Indexed NAV")
        st.plotly_chart(fig, use_container_width=True)

    # Radar
    if pa is not None and pb is not None:
        st.subheader("Performance Radar")
        rcols = ["return_3yr_pct","sharpe_ratio","sortino_ratio","r_squared"]
        rlbls = ["3Y Return","Sharpe","Sortino","R2"]
        va_l  = [pa.get(c,0) or 0 for c in rcols]
        vb_l  = [pb.get(c,0) or 0 for c in rcols]
        mx    = [max(abs(a),abs(b))+1e-9 for a,b in zip(va_l, vb_l)]
        na_l  = [v/m for v,m in zip(va_l,mx)]
        nb_l  = [v/m for v,m in zip(vb_l,mx)]
        fig_r = go.Figure()
        fig_r.add_trace(go.Scatterpolar(r=na_l+[na_l[0]], theta=rlbls+[rlbls[0]],
                                        fill="toself", name=fa[:20], line=dict(color=ACCENT)))
        fig_r.add_trace(go.Scatterpolar(r=nb_l+[nb_l[0]], theta=rlbls+[rlbls[0]],
                                        fill="toself", name=fb[:20], line=dict(color=ORANGE), opacity=0.7))
        fig_r.update_layout(height=360, polar=dict(radialaxis=dict(visible=True)),
                            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_r, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════════════════════

def main():
    st.set_page_config(page_title="Bluestock MF Analytics", page_icon="📊",
                       layout="wide", initial_sidebar_state="expanded")
    st.markdown("""<style>
        .block-container{padding-top:1rem}
        [data-testid="metric-container"]{background:#1a1d23;border:1px solid #2d3139;
            border-radius:8px;padding:12px 16px}
        .stMetric label{font-size:0.75rem!important;color:#a0a8b8!important}
    </style>""", unsafe_allow_html=True)

    fund, nav, perf, txn, aum, sip, fol, bm, cat, ptf, scorecard = load()

    with st.sidebar:
        st.title("Bluestock MF")
        st.caption("40 Funds | 5 Years | 46K NAV rows")
        st.divider()
        page = st.radio("Navigation", [
            "📊 Executive Summary",
            "📈 Fund Performance",
            "⚠️ Risk Analytics",
            "🏭 Industry Analytics",
            "🎯 Portfolio Optimiser",
            "🔍 Fund Comparison",
        ])
        st.divider()
        st.caption("Data: AMFI India")
        st.caption(f"DB: {DB.name}")

    if   "Executive"   in page: page_executive(fund, nav, perf, txn, sip, fol, scorecard)
    elif "Performance" in page: page_nav_performance(fund, nav, bm)
    elif "Risk"        in page: page_risk(perf, nav, fund)
    elif "Industry"    in page: page_industry(txn, sip, fol, aum, cat)
    elif "Portfolio"   in page: page_portfolio(nav, fund, perf)
    elif "Comparison"  in page: page_comparison(fund, nav, perf)

if __name__ == "__main__":
    main()
