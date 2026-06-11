"""
app.py
======
Bluestock Mutual Fund Analytics Capstone
Streamlit Interactive Dashboard — B2 Bonus + D5 Companion

Pages
-----
1  Executive Summary    — KPI cards, fund snapshot table, top/bottom performers
2  Fund Performance     — NAV trends, returns, benchmark comparison
3  Risk Analytics       — volatility, drawdown, VaR, risk-return scatter
4  Portfolio Optimiser  — Markowitz frontier, optimal weights, SIP calculator
5  Fund Comparison      — side-by-side multi-fund comparison

Run
---
    streamlit run source_code/streamlit_app/app.py

Author : Bluestock Capstone Team
Date   : 2025
"""

from __future__ import annotations

import sqlite3
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats as sp_stats
from scipy.optimize import minimize

warnings.filterwarnings("ignore")

# ── Streamlit import (guarded so scripts can import helpers without streamlit)
try:
    import streamlit as st
    HAS_ST = True
except ImportError:
    HAS_ST = False

# ─────────────────────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH  = BASE_DIR / "datasets" / "db" / "bluestock_mf.db"

# ─────────────────────────────────────────────────────────────────────────────
# THEME CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
BLUE       = "#1f77b4"
ORANGE     = "#ff7f0e"
GREEN      = "#2ca02c"
RED        = "#d62728"
TEAL       = "#17becf"
PURPLE     = "#9467bd"
BG         = "#0e1117"
CARD_BG    = "#1a1d23"
ACCENT     = "#00c4ff"

RISK_COLORS = {
    "Low":              "#27ae60",
    "Moderate":         "#f1c40f",
    "Moderately High":  "#e67e22",
    "High":             "#e74c3c",
    "Very High":        "#8e44ad",
}

RISK_FREE   = 0.065
TRADING_DAYS = 252


# ─────────────────────────────────────────────────────────────────────────────
# DATA LAYER  — all DB reads go through here
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_executive_summary() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query("SELECT * FROM vw_executive_summary", conn)


@st.cache_data(ttl=3600)
def load_nav_history(scheme_codes: tuple | None = None) -> pd.DataFrame:
    where = ""
    if scheme_codes:
        codes = ",".join(str(c) for c in scheme_codes)
        where = f"WHERE nh.scheme_code IN ({codes})"
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(f"""
            SELECT * FROM vw_fund_performance {where} ORDER BY scheme_code, date
        """, conn, parse_dates=["date"])


@st.cache_data(ttl=3600)
def load_performance_metrics() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query("""
            SELECT pm.*, fm.scheme_name, cm.category, cm.sub_category,
                   fhm.amc_name, fm.risk_level
            FROM performance_metrics pm
            JOIN fund_master fm ON pm.scheme_code=fm.scheme_code
            JOIN category_master cm ON fm.category_id=cm.category_id
            JOIN fund_house_master fhm ON fm.amc_id=fhm.amc_id
        """, conn)


@st.cache_data(ttl=3600)
def load_monthly_returns() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query("SELECT * FROM vw_monthly_returns", conn)


@st.cache_data(ttl=3600)
def load_benchmark_nav() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(
            "SELECT * FROM benchmark_nav ORDER BY benchmark_name, date",
            conn, parse_dates=["date"]
        )


@st.cache_data(ttl=3600)
def load_fund_list() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query("""
            SELECT fm.scheme_code, fm.scheme_name, cm.category,
                   cm.sub_category, fhm.amc_name, fm.risk_level, fm.benchmark
            FROM fund_master fm
            JOIN category_master cm ON fm.category_id=cm.category_id
            JOIN fund_house_master fhm ON fm.amc_id=fhm.amc_id
            ORDER BY cm.category, cm.sub_category, fm.scheme_name
        """, conn)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def fmt_pct(v: float | None, decimals: int = 2) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "N/A"
    return f"{v * 100:.{decimals}f}%"


def fmt_ratio(v: float | None, decimals: int = 3) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "N/A"
    return f"{v:.{decimals}f}"


def delta_color(v: float | None) -> str:
    if v is None or np.isnan(v):
        return "off"
    return "normal" if v >= 0 else "inverse"


def kpi_card(col, label: str, value: str, delta: str | None = None) -> None:
    col.metric(label=label, value=value, delta=delta)


def risk_badge(risk: str) -> str:
    color = RISK_COLORS.get(risk, "#888")
    return f'<span style="background:{color};color:white;padding:2px 8px;border-radius:4px;font-size:12px">{risk}</span>'


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 1 — EXECUTIVE SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def page_executive_summary() -> None:
    st.title("📊 Executive Summary")
    st.caption("Live snapshot of all 19 mutual funds in the Bluestock universe")

    exec_df = load_executive_summary()
    pm_df   = load_performance_metrics()

    # ── Slicers ───────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        sel_cat = st.multiselect("Category", sorted(exec_df["category"].dropna().unique()),
                                 default=sorted(exec_df["category"].dropna().unique()))
    with col2:
        sel_risk = st.multiselect("Risk Level", sorted(exec_df["risk_level"].dropna().unique()),
                                  default=sorted(exec_df["risk_level"].dropna().unique()))
    with col3:
        sel_amc = st.multiselect("AMC", sorted(exec_df["amc_name"].dropna().unique()),
                                 default=sorted(exec_df["amc_name"].dropna().unique()))
    with col4:
        sel_period = st.selectbox("Performance Period", ["1Y", "3Y", "5Y", "Inception"], index=0)

    # Filter
    filtered = exec_df[
        (exec_df["category"].isin(sel_cat)) &
        (exec_df["risk_level"].isin(sel_risk)) &
        (exec_df["amc_name"].isin(sel_amc))
    ].copy()

    cagr_col = f"cagr_{sel_period.lower().replace('ception','ception')}"
    if cagr_col not in filtered.columns:
        cagr_col = "cagr_1y"

    st.divider()

    # ── KPI Row ───────────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Total Funds",       f"{len(filtered)}")
    k2.metric("Categories",        f"{filtered['category'].nunique()}")
    k3.metric("AMCs",              f"{filtered['amc_name'].nunique()}")
    k4.metric("Avg 1Y CAGR",       fmt_pct(filtered['cagr_1y'].mean()))
    k5.metric("Best 1Y CAGR",      fmt_pct(filtered['cagr_1y'].max()))
    k6.metric("Best Sharpe (1Y)",  fmt_ratio(filtered['sharpe_1y'].max()))

    st.divider()

    # ── Top/Bottom bar charts ─────────────────────────────────────────────────
    col_top, col_bot = st.columns(2)

    with col_top:
        st.subheader(f"🏆 Top 5 Funds — {sel_period} CAGR")
        top5 = filtered.sort_values(cagr_col, ascending=False).head(5)
        if not top5.empty and cagr_col in top5.columns:
            fig = px.bar(top5, x=cagr_col, y="scheme_name",
                         orientation="h", text=top5[cagr_col].apply(lambda x: fmt_pct(x)),
                         color=cagr_col, color_continuous_scale="Greens",
                         labels={cagr_col: "CAGR", "scheme_name": ""})
            fig.update_layout(height=280, showlegend=False,
                              plot_bgcolor="rgba(0,0,0,0)",
                              paper_bgcolor="rgba(0,0,0,0)",
                              yaxis=dict(tickfont=dict(size=10)))
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)

    with col_bot:
        st.subheader(f"⚠️ Bottom 5 Funds — {sel_period} CAGR")
        bot5 = filtered.sort_values(cagr_col).head(5)
        if not bot5.empty and cagr_col in bot5.columns:
            fig2 = px.bar(bot5, x=cagr_col, y="scheme_name",
                          orientation="h", text=bot5[cagr_col].apply(lambda x: fmt_pct(x)),
                          color=cagr_col, color_continuous_scale="Reds_r",
                          labels={cagr_col: "CAGR", "scheme_name": ""})
            fig2.update_layout(height=280, showlegend=False,
                               plot_bgcolor="rgba(0,0,0,0)",
                               paper_bgcolor="rgba(0,0,0,0)",
                               yaxis=dict(tickfont=dict(size=10)))
            fig2.update_traces(textposition="outside")
            st.plotly_chart(fig2, use_container_width=True)

    # ── Category donut ────────────────────────────────────────────────────────
    col_donut, col_scatter = st.columns(2)
    with col_donut:
        st.subheader("📂 Fund Universe Breakdown")
        cat_counts = filtered.groupby("sub_category").size().reset_index(name="count")
        fig3 = px.pie(cat_counts, names="sub_category", values="count",
                      hole=0.45, color_discrete_sequence=px.colors.qualitative.Set3)
        fig3.update_layout(height=320, plot_bgcolor="rgba(0,0,0,0)",
                           paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig3, use_container_width=True)

    with col_scatter:
        st.subheader("⚖️ Risk vs Return (1Y)")
        pm_1y = load_performance_metrics()
        pm_1y = pm_1y[pm_1y["period_label"] == "1Y"].copy()
        pm_1y = pm_1y[pm_1y["category"].isin(sel_cat)].copy()
        if not pm_1y.empty:
            fig4 = px.scatter(pm_1y, x="volatility_ann", y="cagr",
                              color="risk_level", size="sharpe_ratio",
                              hover_name="scheme_name",
                              hover_data={"sharpe_ratio": ":.3f",
                                          "max_drawdown": ":.3f"},
                              color_discrete_map=RISK_COLORS,
                              labels={"volatility_ann": "Volatility (Ann.)",
                                      "cagr": "1Y CAGR",
                                      "risk_level": "Risk Level"})
            fig4.update_layout(height=320, plot_bgcolor="rgba(0,0,0,0)",
                               paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig4, use_container_width=True)

    # ── Full fund table ───────────────────────────────────────────────────────
    st.subheader("📋 Full Fund Snapshot")
    display = filtered[[
        "scheme_name", "sub_category", "amc_name", "risk_level",
        "current_nav", "nav_date", "cagr_1y", "cagr_3y", "cagr_5y",
        "sharpe_1y", "max_drawdown_1y", "volatility_1y"
    ]].copy()
    display.columns = [
        "Fund", "Sub-Category", "AMC", "Risk",
        "NAV", "NAV Date", "CAGR 1Y", "CAGR 3Y", "CAGR 5Y",
        "Sharpe 1Y", "Max DD 1Y", "Vol 1Y"
    ]
    for col in ["CAGR 1Y", "CAGR 3Y", "CAGR 5Y", "Max DD 1Y", "Vol 1Y"]:
        display[col] = display[col].apply(fmt_pct)
    display["Sharpe 1Y"] = display["Sharpe 1Y"].apply(fmt_ratio)
    display["NAV"] = display["NAV"].apply(lambda x: f"₹{x:,.2f}" if pd.notna(x) else "N/A")
    st.dataframe(display, use_container_width=True, height=480)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 2 — FUND PERFORMANCE
# ─────────────────────────────────────────────────────────────────────────────

def page_fund_performance() -> None:
    st.title("📈 Fund Performance")
    st.caption("NAV trends, returns over time, and benchmark comparison")

    funds_df = load_fund_list()

    # ── Slicers ───────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns([3, 2, 2])
    with col1:
        sel_funds = st.multiselect(
            "Select Funds (up to 6)",
            options=funds_df["scheme_name"].tolist(),
            default=funds_df["scheme_name"].tolist()[:3],
            max_selections=6
        )
    with col2:
        date_from = st.date_input("From Date", value=pd.to_datetime("2022-01-01"))
    with col3:
        date_to = st.date_input("To Date", value=pd.to_datetime("2026-06-01"))

    if not sel_funds:
        st.warning("Select at least one fund.")
        return

    sel_codes = tuple(funds_df[funds_df["scheme_name"].isin(sel_funds)]["scheme_code"].tolist())
    nav_df    = load_nav_history(sel_codes)
    nav_df    = nav_df[(nav_df["date"] >= pd.Timestamp(date_from)) &
                       (nav_df["date"] <= pd.Timestamp(date_to))].copy()

    if nav_df.empty:
        st.warning("No data for selected filters.")
        return

    st.divider()

    # ── KPI row ───────────────────────────────────────────────────────────────
    pm = load_performance_metrics()
    pm_1y = pm[(pm["period_label"] == "1Y") & (pm["scheme_name"].isin(sel_funds))]

    if not pm_1y.empty:
        cols_kpi = st.columns(len(pm_1y))
        for col, (_, row) in zip(cols_kpi, pm_1y.iterrows()):
            with col:
                cagr_val = fmt_pct(row["cagr"])
                col.metric(label=row["scheme_name"][:22],
                           value=f"CAGR {cagr_val}",
                           delta=fmt_ratio(row["sharpe_ratio"]) + " Sharpe")

    st.divider()

    # ── NAV trend (indexed to 100) ────────────────────────────────────────────
    st.subheader("📊 Indexed NAV Trend (Base = 100 at start date)")
    fig = go.Figure()
    for code in sel_codes:
        fund = nav_df[nav_df["scheme_code"] == code].sort_values("date")
        if fund.empty:
            continue
        indexed = fund["nav"] / fund["nav"].iloc[0] * 100
        name    = fund["scheme_name"].iloc[0]
        fig.add_trace(go.Scatter(
            x=fund["date"], y=indexed, mode="lines",
            name=name[:30], line=dict(width=2), hovertemplate="%{y:.2f}"
        ))
    fig.add_hline(y=100, line_dash="dot", line_color="gray", opacity=0.5)
    fig.update_layout(height=420, plot_bgcolor="rgba(0,0,0,0)",
                      paper_bgcolor="rgba(0,0,0,0)",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02),
                      xaxis_title="Date", yaxis_title="Indexed NAV")
    st.plotly_chart(fig, use_container_width=True)

    # ── Rolling returns ───────────────────────────────────────────────────────
    col_roll, col_vol = st.columns(2)
    with col_roll:
        st.subheader("🔄 Rolling 1-Year Return")
        fig2 = go.Figure()
        for code in sel_codes:
            fund = nav_df[nav_df["scheme_code"] == code].sort_values("date").set_index("date")
            if len(fund) < 252:
                continue
            rolling_ret = fund["nav"].pct_change(252) * 100
            fig2.add_trace(go.Scatter(
                x=rolling_ret.index, y=rolling_ret.values,
                mode="lines", name=fund["scheme_name"].iloc[0][:25],
                line=dict(width=1.5)
            ))
        fig2.add_hline(y=0, line_color="gray", line_dash="dot")
        fig2.update_layout(height=320, plot_bgcolor="rgba(0,0,0,0)",
                           paper_bgcolor="rgba(0,0,0,0)",
                           xaxis_title="Date", yaxis_title="1Y Return %")
        st.plotly_chart(fig2, use_container_width=True)

    with col_vol:
        st.subheader("📉 Rolling 90-Day Volatility")
        fig3 = go.Figure()
        for code in sel_codes:
            fund = nav_df[nav_df["scheme_code"] == code].sort_values("date")
            if fund.empty:
                continue
            vol_col = fund["rolling_90d_vol"] * 100
            fig3.add_trace(go.Scatter(
                x=fund["date"], y=vol_col,
                mode="lines", name=fund["scheme_name"].iloc[0][:25],
                line=dict(width=1.5)
            ))
        fig3.update_layout(height=320, plot_bgcolor="rgba(0,0,0,0)",
                           paper_bgcolor="rgba(0,0,0,0)",
                           xaxis_title="Date", yaxis_title="Volatility %")
        st.plotly_chart(fig3, use_container_width=True)

    # ── Benchmark comparison ──────────────────────────────────────────────────
    st.subheader("🆚 Fund vs Benchmark (Indexed)")
    if len(sel_codes) == 1:
        fund_info = funds_df[funds_df["scheme_code"] == sel_codes[0]].iloc[0]
        bench_name = fund_info["benchmark"]
        bench_df   = load_benchmark_nav()
        bench_fund = bench_df[bench_df["benchmark_name"] == bench_name].copy()
        bench_fund = bench_fund[(bench_fund["date"] >= pd.Timestamp(date_from)) &
                                (bench_fund["date"] <= pd.Timestamp(date_to))]
        fund_nav   = nav_df[nav_df["scheme_code"] == sel_codes[0]].sort_values("date")

        if not bench_fund.empty and not fund_nav.empty:
            fig4 = go.Figure()
            idx_fund  = fund_nav["nav"] / fund_nav["nav"].iloc[0] * 100
            fig4.add_trace(go.Scatter(x=fund_nav["date"], y=idx_fund,
                                      name=fund_nav["scheme_name"].iloc[0][:30],
                                      line=dict(color=BLUE, width=2)))
            idx_bench = bench_fund["index_value"] / bench_fund["index_value"].iloc[0] * 100
            fig4.add_trace(go.Scatter(x=bench_fund["date"], y=idx_bench,
                                      name=bench_name,
                                      line=dict(color=ORANGE, width=2, dash="dash")))
            fig4.update_layout(height=360, plot_bgcolor="rgba(0,0,0,0)",
                               paper_bgcolor="rgba(0,0,0,0)",
                               yaxis_title="Indexed (Base=100)", xaxis_title="Date")
            st.plotly_chart(fig4, use_container_width=True)
    else:
        st.info("Select exactly 1 fund to see benchmark comparison.")

    # ── Monthly return heatmap ────────────────────────────────────────────────
    if len(sel_funds) == 1:
        st.subheader("🗓️ Monthly Return Heatmap")
        monthly_df = load_monthly_returns()
        fund_monthly = monthly_df[monthly_df["scheme_name"] == sel_funds[0]].copy()
        if not fund_monthly.empty:
            pivot = fund_monthly.pivot_table(
                index="year", columns="month", values="monthly_return_pct"
            )
            pivot.columns = ["Jan","Feb","Mar","Apr","May","Jun",
                             "Jul","Aug","Sep","Oct","Nov","Dec"][:len(pivot.columns)]
            fig5 = px.imshow(pivot, text_auto=".1f", aspect="auto",
                             color_continuous_scale="RdYlGn",
                             color_continuous_midpoint=0,
                             labels=dict(color="Return %"))
            fig5.update_layout(height=280, plot_bgcolor="rgba(0,0,0,0)",
                               paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig5, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 3 — RISK ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────

def page_risk_analytics() -> None:
    st.title("⚠️ Risk Analytics")
    st.caption("Volatility, drawdowns, Value at Risk, and risk-adjusted metrics")

    pm   = load_performance_metrics()
    nav  = load_nav_history()

    # ── Slicers ───────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        sel_period = st.selectbox("Period", ["1Y", "3Y", "5Y", "Inception"])
    with col2:
        sel_cat = st.multiselect("Category",
                                 sorted(pm["category"].dropna().unique()),
                                 default=sorted(pm["category"].dropna().unique()))
    with col3:
        sel_risk = st.multiselect("Risk Level",
                                  sorted(pm["risk_level"].dropna().unique()),
                                  default=sorted(pm["risk_level"].dropna().unique()))

    pm_f = pm[(pm["period_label"] == sel_period) &
              (pm["category"].isin(sel_cat)) &
              (pm["risk_level"].isin(sel_risk))].copy()

    if pm_f.empty:
        st.warning("No data for filters.")
        return

    st.divider()

    # ── Risk KPIs ─────────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Avg Volatility",   fmt_pct(pm_f["volatility_ann"].mean()))
    k2.metric("Avg Max Drawdown", fmt_pct(pm_f["max_drawdown"].mean()))
    k3.metric("Avg Sharpe",       fmt_ratio(pm_f["sharpe_ratio"].mean()))
    k4.metric("Avg Beta",         fmt_ratio(pm_f["beta"].mean()))
    k5.metric("Avg Sortino",      fmt_ratio(pm_f["sortino_ratio"].mean()))

    st.divider()

    # ── Volatility ranking ────────────────────────────────────────────────────
    col_vol, col_mdd = st.columns(2)
    with col_vol:
        st.subheader(f"📊 Volatility Ranking ({sel_period})")
        vol_sort = pm_f.sort_values("volatility_ann", ascending=True)
        colors   = [RISK_COLORS.get(r, "#888") for r in vol_sort["risk_level"]]
        fig = go.Figure(go.Bar(
            x=vol_sort["volatility_ann"] * 100,
            y=[n[:28] for n in vol_sort["scheme_name"]],
            orientation="h",
            marker_color=colors,
            text=[f"{v*100:.1f}%" for v in vol_sort["volatility_ann"]],
            textposition="outside"
        ))
        fig.update_layout(height=420, plot_bgcolor="rgba(0,0,0,0)",
                          paper_bgcolor="rgba(0,0,0,0)",
                          xaxis_title="Annualised Volatility %",
                          yaxis=dict(tickfont=dict(size=9)))
        st.plotly_chart(fig, use_container_width=True)

    with col_mdd:
        st.subheader(f"📉 Max Drawdown Ranking ({sel_period})")
        mdd_sort = pm_f.sort_values("max_drawdown")
        colors2  = [RISK_COLORS.get(r, "#888") for r in mdd_sort["risk_level"]]
        fig2 = go.Figure(go.Bar(
            x=mdd_sort["max_drawdown"] * 100,
            y=[n[:28] for n in mdd_sort["scheme_name"]],
            orientation="h",
            marker_color=colors2,
            text=[f"{v*100:.1f}%" for v in mdd_sort["max_drawdown"]],
            textposition="outside"
        ))
        fig2.update_layout(height=420, plot_bgcolor="rgba(0,0,0,0)",
                           paper_bgcolor="rgba(0,0,0,0)",
                           xaxis_title="Max Drawdown %",
                           yaxis=dict(tickfont=dict(size=9)))
        st.plotly_chart(fig2, use_container_width=True)

    # ── Drawdown history chart ────────────────────────────────────────────────
    st.subheader("📉 Drawdown History — Equity Funds")
    equity_nav = nav[nav["category"] == "Equity"].copy()
    fig3 = go.Figure()
    for code in equity_nav["scheme_code"].unique():
        fund = equity_nav[equity_nav["scheme_code"] == code].sort_values("date")
        if len(fund) < 100:
            continue
        peak = fund["nav"].cummax()
        dd   = (fund["nav"] - peak) / peak * 100
        fig3.add_trace(go.Scatter(
            x=fund["date"], y=dd,
            mode="lines", name=fund["scheme_name"].iloc[0][:25],
            line=dict(width=1.2), fill="tozeroy", opacity=0.3
        ))
    fig3.add_hline(y=0, line_color="white", line_dash="dot", opacity=0.3)
    fig3.update_layout(height=360, plot_bgcolor="rgba(0,0,0,0)",
                       paper_bgcolor="rgba(0,0,0,0)",
                       yaxis_title="Drawdown %", xaxis_title="Date",
                       legend=dict(orientation="h", yanchor="bottom", y=1.02,
                                   font=dict(size=8)))
    st.plotly_chart(fig3, use_container_width=True)

    # ── VaR analysis ──────────────────────────────────────────────────────────
    st.subheader("🎯 Value at Risk (Daily, 95% Confidence)")
    var_results = []
    for code in equity_nav["scheme_code"].unique():
        rets = equity_nav[equity_nav["scheme_code"] == code]["daily_return"].dropna()
        if len(rets) < 60:
            continue
        name     = equity_nav[equity_nav["scheme_code"] == code]["scheme_name"].iloc[0]
        hist_var = np.percentile(rets, 5)
        cvar     = rets[rets <= hist_var].mean()
        var_results.append({
            "Fund":       name[:30],
            "Hist VaR %": round(hist_var * 100, 3),
            "CVaR %":     round(cvar * 100, 3),
        })

    var_df = pd.DataFrame(var_results).sort_values("Hist VaR %")
    fig4 = go.Figure()
    fig4.add_trace(go.Bar(name="Historical VaR %", x=var_df["Fund"],
                          y=var_df["Hist VaR %"], marker_color=ORANGE))
    fig4.add_trace(go.Bar(name="CVaR %", x=var_df["Fund"],
                          y=var_df["CVaR %"], marker_color=RED))
    fig4.update_layout(barmode="group", height=360,
                       plot_bgcolor="rgba(0,0,0,0)",
                       paper_bgcolor="rgba(0,0,0,0)",
                       yaxis_title="Daily VaR %",
                       xaxis=dict(tickangle=-30, tickfont=dict(size=9)))
    st.plotly_chart(fig4, use_container_width=True)

    # ── Risk metrics table ────────────────────────────────────────────────────
    st.subheader(f"📋 Full Risk Metrics Table ({sel_period})")
    risk_tbl = pm_f[[
        "scheme_name", "sub_category", "risk_level",
        "volatility_ann", "max_drawdown", "sharpe_ratio",
        "sortino_ratio", "beta", "alpha", "r_squared", "tracking_error"
    ]].copy()
    risk_tbl.columns = ["Fund", "Sub-Cat", "Risk",
                        "Vol %", "Max DD %", "Sharpe",
                        "Sortino", "Beta", "Alpha %", "R²", "TE %"]
    for col in ["Vol %", "Max DD %", "Alpha %", "TE %"]:
        risk_tbl[col] = (risk_tbl[col] * 100).round(2).astype(str) + "%"
    for col in ["Sharpe", "Sortino", "Beta", "R²"]:
        risk_tbl[col] = risk_tbl[col].round(3)
    st.dataframe(risk_tbl, use_container_width=True, height=400)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 4 — PORTFOLIO OPTIMISER
# ─────────────────────────────────────────────────────────────────────────────

def page_portfolio_optimiser() -> None:
    st.title("🎯 Portfolio Optimiser")
    st.caption("Markowitz Mean-Variance Optimisation + SIP Calculator")

    funds_df = load_fund_list()
    nav_df   = load_nav_history()

    # ── Slicers ───────────────────────────────────────────────────────────────
    col1, col2 = st.columns([4, 2])
    with col1:
        sel_funds = st.multiselect(
            "Select Funds for Portfolio (2–10)",
            options=funds_df[funds_df["category"].isin(["Equity","Hybrid","Index"])]["scheme_name"].tolist(),
            default=funds_df[funds_df["category"] == "Equity"]["scheme_name"].tolist()[:5]
        )
    with col2:
        investment = st.number_input("Investment Amount (₹)", min_value=10000,
                                     max_value=10000000, value=100000, step=10000)

    if len(sel_funds) < 2:
        st.warning("Select at least 2 funds to optimise a portfolio.")
        return

    sel_codes = tuple(funds_df[funds_df["scheme_name"].isin(sel_funds)]["scheme_code"].tolist())
    nav_f     = nav_df[nav_df["scheme_code"].isin(sel_codes)].copy()

    returns_pivot = nav_f.pivot_table(
        index="date", columns="scheme_name", values="daily_return"
    ).dropna(how="all").ffill().dropna()

    # Keep only selected funds with enough data
    returns_pivot = returns_pivot[[c for c in sel_funds if c in returns_pivot.columns]]
    returns_pivot = returns_pivot.dropna(axis=1, thresh=int(len(returns_pivot) * 0.9))
    returns_pivot = returns_pivot.dropna()

    if returns_pivot.shape[1] < 2:
        st.warning("Insufficient data for optimisation.")
        return

    n      = returns_pivot.shape[1]
    mu_vec = returns_pivot.mean().values * TRADING_DAYS
    cov    = returns_pivot.cov().values  * TRADING_DAYS

    def portfolio_stats(w):
        ret = w @ mu_vec
        vol = np.sqrt(w @ cov @ w)
        return ret, vol

    def neg_sharpe(w):
        r, v = portfolio_stats(w)
        return -(r - RISK_FREE) / v if v > 0 else 0

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    bounds      = [(0.0, 1.0)] * n
    init        = np.ones(n) / n

    res_s = minimize(neg_sharpe, init, method="SLSQP", bounds=bounds, constraints=constraints)
    res_m = minimize(lambda w: portfolio_stats(w)[1], init, method="SLSQP",
                     bounds=bounds, constraints=constraints)

    opt_ret_s, opt_vol_s = portfolio_stats(res_s.x)
    opt_ret_m, opt_vol_m = portfolio_stats(res_m.x)

    st.divider()

    # ── KPIs ──────────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Max Sharpe Return", fmt_pct(opt_ret_s))
    k2.metric("Max Sharpe Vol",    fmt_pct(opt_vol_s))
    k3.metric("Min Vol Return",    fmt_pct(opt_ret_m))
    k4.metric("Min Vol",           fmt_pct(opt_vol_m))

    st.divider()

    # ── Efficient frontier ────────────────────────────────────────────────────
    col_ef, col_wt = st.columns(2)
    with col_ef:
        st.subheader("📐 Efficient Frontier")
        np.random.seed(42)
        n_sim = 2000
        sim_r, sim_v, sim_sr = [], [], []
        for _ in range(n_sim):
            w = np.random.dirichlet(np.ones(n))
            r, v = portfolio_stats(w)
            sim_r.append(r); sim_v.append(v)
            sim_sr.append((r - RISK_FREE) / v if v > 0 else 0)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=sim_v, y=sim_r, mode="markers",
            marker=dict(color=sim_sr, colorscale="RdYlGn", size=4,
                        opacity=0.5, colorbar=dict(title="Sharpe")),
            name="Random Portfolios", hovertemplate="Vol:%{x:.3f} Ret:%{y:.3f}"
        ))
        fig.add_trace(go.Scatter(
            x=[opt_vol_s], y=[opt_ret_s], mode="markers",
            marker=dict(symbol="star", size=18, color="gold",
                        line=dict(color="black", width=1)),
            name=f"Max Sharpe ({(opt_ret_s-RISK_FREE)/opt_vol_s:.2f})"
        ))
        fig.add_trace(go.Scatter(
            x=[opt_vol_m], y=[opt_ret_m], mode="markers",
            marker=dict(symbol="diamond", size=14, color="cyan",
                        line=dict(color="black", width=1)),
            name="Min Volatility"
        ))
        fig.update_layout(height=400, plot_bgcolor="rgba(0,0,0,0)",
                          paper_bgcolor="rgba(0,0,0,0)",
                          xaxis_title="Annualised Volatility",
                          yaxis_title="Annualised Return")
        st.plotly_chart(fig, use_container_width=True)

    with col_wt:
        st.subheader("⚖️ Optimal Portfolio Weights")
        tab_s, tab_m = st.tabs(["Max Sharpe", "Min Volatility"])
        for tab, weights, label in [(tab_s, res_s.x, "Max Sharpe"),
                                     (tab_m, res_m.x, "Min Vol")]:
            with tab:
                wt_df = pd.DataFrame({
                    "Fund":   [n[:30] for n in returns_pivot.columns],
                    "Weight": (weights * 100).round(2),
                    "Amount ₹": (weights * investment).round(0).astype(int)
                }).sort_values("Weight", ascending=False)

                fig_pie = px.pie(wt_df[wt_df["Weight"] > 0.5],
                                 names="Fund", values="Weight",
                                 hole=0.4,
                                 color_discrete_sequence=px.colors.qualitative.Set2)
                fig_pie.update_layout(height=280,
                                      plot_bgcolor="rgba(0,0,0,0)",
                                      paper_bgcolor="rgba(0,0,0,0)")
                tab.plotly_chart(fig_pie, use_container_width=True)
                tab.dataframe(wt_df, use_container_width=True)

    # ── SIP Calculator ────────────────────────────────────────────────────────
    st.subheader("💰 SIP Calculator")
    col_sip1, col_sip2, col_sip3 = st.columns(3)
    with col_sip1:
        monthly_sip = st.number_input("Monthly SIP (₹)", min_value=500,
                                      max_value=1000000, value=10000, step=500)
    with col_sip2:
        sip_years = st.slider("Investment Period (Years)", 1, 30, 10)
    with col_sip3:
        exp_return = st.slider("Expected Annual Return (%)", 5, 30, 12)

    months      = sip_years * 12
    monthly_ret = (1 + exp_return / 100) ** (1 / 12) - 1
    fv          = monthly_sip * (((1 + monthly_ret) ** months - 1) / monthly_ret) * (1 + monthly_ret)
    invested    = monthly_sip * months
    gain        = fv - invested
    cagr_sip    = ((fv / invested) ** (1 / sip_years) - 1) * 100

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Invested",   f"₹{invested:,.0f}")
    k2.metric("Future Value",     f"₹{fv:,.0f}")
    k3.metric("Total Gain",       f"₹{gain:,.0f}")
    k4.metric("CAGR",             f"{cagr_sip:.1f}%")

    # SIP growth chart
    running = []
    nav_running = []
    for m in range(1, months + 1):
        nav_running.append(monthly_sip * (((1 + monthly_ret) ** m - 1) / monthly_ret) * (1 + monthly_ret))
        running.append(monthly_sip * m)

    fig_sip = go.Figure()
    dates_sip = pd.date_range(pd.Timestamp.today(), periods=months, freq="ME")
    fig_sip.add_trace(go.Scatter(x=dates_sip, y=nav_running, name="Portfolio Value",
                                  fill="tozeroy", line=dict(color=GREEN)))
    fig_sip.add_trace(go.Scatter(x=dates_sip, y=running, name="Amount Invested",
                                  line=dict(color=ORANGE, dash="dash")))
    fig_sip.update_layout(height=300, plot_bgcolor="rgba(0,0,0,0)",
                          paper_bgcolor="rgba(0,0,0,0)",
                          yaxis_title="₹ Value", xaxis_title="Date")
    st.plotly_chart(fig_sip, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 5 — FUND COMPARISON
# ─────────────────────────────────────────────────────────────────────────────

def page_fund_comparison() -> None:
    st.title("🔍 Fund Comparison")
    st.caption("Side-by-side comparison of any two funds across all metrics")

    funds_df = load_fund_list()
    fund_names = funds_df["scheme_name"].tolist()

    col1, col2 = st.columns(2)
    with col1:
        fund_a = st.selectbox("Fund A", fund_names, index=0)
    with col2:
        fund_b = st.selectbox("Fund B", fund_names, index=min(3, len(fund_names)-1))

    if fund_a == fund_b:
        st.warning("Please select two different funds.")
        return

    code_a = int(funds_df[funds_df["scheme_name"] == fund_a]["scheme_code"].iloc[0])
    code_b = int(funds_df[funds_df["scheme_name"] == fund_b]["scheme_code"].iloc[0])

    pm   = load_performance_metrics()
    nav  = load_nav_history((code_a, code_b))

    st.divider()

    # ── Metrics comparison ────────────────────────────────────────────────────
    sel_period = st.selectbox("Period for Metrics", ["1Y", "3Y", "5Y", "Inception"])
    pm_a = pm[(pm["scheme_code"] == code_a) & (pm["period_label"] == sel_period)]
    pm_b = pm[(pm["scheme_code"] == code_b) & (pm["period_label"] == sel_period)]

    if not pm_a.empty and not pm_b.empty:
        metrics = [
            ("CAGR %",       "cagr",          True,  True),
            ("Volatility %", "volatility_ann", True,  False),
            ("Max Drawdown %","max_drawdown",  True,  False),
            ("Sharpe Ratio", "sharpe_ratio",  False, True),
            ("Sortino Ratio","sortino_ratio",  False, True),
            ("Beta",         "beta",           False, None),
            ("Alpha %",      "alpha",          True,  True),
            ("R²",           "r_squared",      False, True),
        ]
        row_data = {"Metric": [], fund_a[:20]: [], fund_b[:20]: [], "Winner": []}
        for label, col, is_pct, higher_better in metrics:
            va = pm_a[col].iloc[0] if col in pm_a.columns else None
            vb = pm_b[col].iloc[0] if col in pm_b.columns else None
            if va is None or vb is None:
                continue
            scale = 100 if is_pct else 1
            fmt   = f"{va*scale:.2f}" + ("%" if is_pct else "")
            fmt_b = f"{vb*scale:.2f}" + ("%" if is_pct else "")
            if higher_better is True:
                winner = fund_a[:15] if va > vb else fund_b[:15]
            elif higher_better is False:
                winner = fund_a[:15] if abs(va) < abs(vb) else fund_b[:15]
            else:
                winner = "—"
            row_data["Metric"].append(label)
            row_data[fund_a[:20]].append(fmt)
            row_data[fund_b[:20]].append(fmt_b)
            row_data["Winner"].append(f"🏆 {winner}")

        cmp_df = pd.DataFrame(row_data)
        st.dataframe(cmp_df, use_container_width=True)

    # ── NAV comparison chart ──────────────────────────────────────────────────
    st.subheader("📊 NAV Comparison (Indexed to 100)")
    nav_a = nav[nav["scheme_code"] == code_a].sort_values("date")
    nav_b = nav[nav["scheme_code"] == code_b].sort_values("date")

    if not nav_a.empty and not nav_b.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=nav_a["date"],
            y=nav_a["nav"] / nav_a["nav"].iloc[0] * 100,
            name=fund_a[:30], line=dict(color=BLUE, width=2)
        ))
        fig.add_trace(go.Scatter(
            x=nav_b["date"],
            y=nav_b["nav"] / nav_b["nav"].iloc[0] * 100,
            name=fund_b[:30], line=dict(color=ORANGE, width=2)
        ))
        fig.add_hline(y=100, line_dash="dot", line_color="gray", opacity=0.4)
        fig.update_layout(height=400, plot_bgcolor="rgba(0,0,0,0)",
                          paper_bgcolor="rgba(0,0,0,0)",
                          yaxis_title="Indexed NAV", xaxis_title="Date")
        st.plotly_chart(fig, use_container_width=True)

    # ── Radar chart ───────────────────────────────────────────────────────────
    if not pm_a.empty and not pm_b.empty:
        st.subheader("🕸️ Performance Radar")
        radar_metrics = ["cagr", "sharpe_ratio", "sortino_ratio", "r_squared"]
        radar_labels  = ["CAGR", "Sharpe", "Sortino", "R²"]

        vals_a = [pm_a[m].iloc[0] for m in radar_metrics]
        vals_b = [pm_b[m].iloc[0] for m in radar_metrics]

        # Normalise 0-1
        maxv = [max(abs(a), abs(b)) + 1e-9 for a, b in zip(vals_a, vals_b)]
        na   = [v / mx for v, mx in zip(vals_a, maxv)]
        nb   = [v / mx for v, mx in zip(vals_b, maxv)]

        fig_r = go.Figure()
        fig_r.add_trace(go.Scatterpolar(r=na + [na[0]], theta=radar_labels + [radar_labels[0]],
                                        fill="toself", name=fund_a[:20],
                                        line=dict(color=BLUE)))
        fig_r.add_trace(go.Scatterpolar(r=nb + [nb[0]], theta=radar_labels + [radar_labels[0]],
                                        fill="toself", name=fund_b[:20],
                                        line=dict(color=ORANGE), opacity=0.7))
        fig_r.update_layout(height=380, polar=dict(radialaxis=dict(visible=True)),
                            plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_r, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="Bluestock MF Analytics",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # ── Custom CSS ────────────────────────────────────────────────────────────
    st.markdown("""
        <style>
        .block-container { padding-top: 1rem; padding-bottom: 0; }
        [data-testid="metric-container"] {
            background: #1a1d23;
            border: 1px solid #2d3139;
            border-radius: 8px;
            padding: 12px 16px;
        }
        .stMetric label { font-size: 0.75rem !important; color: #a0a8b8 !important; }
        </style>
    """, unsafe_allow_html=True)

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.image("https://raw.githubusercontent.com/simple-icons/simple-icons/develop/"
                 "icons/googleanalytics.svg", width=40)
        st.title("Bluestock MF")
        st.caption("Mutual Fund Analytics Capstone")
        st.divider()

        page = st.radio("Navigation", [
            "📊 Executive Summary",
            "📈 Fund Performance",
            "⚠️ Risk Analytics",
            "🎯 Portfolio Optimiser",
            "🔍 Fund Comparison",
        ])

        st.divider()
        st.caption("Data: AMFI India via mfapi.in")
        st.caption("19 Funds | 5 Years | 70K+ NAV rows")
        st.caption(f"DB: {DB_PATH.name}")

    # ── Route ─────────────────────────────────────────────────────────────────
    if   "Executive"  in page: page_executive_summary()
    elif "Performance" in page: page_fund_performance()
    elif "Risk"        in page: page_risk_analytics()
    elif "Portfolio"   in page: page_portfolio_optimiser()
    elif "Comparison"  in page: page_fund_comparison()


if __name__ == "__main__":
    main()
