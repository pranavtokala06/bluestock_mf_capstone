# Data Dictionary
## Bluestock Mutual Fund Analytics Capstone

---

## Table: fund_master

One row per mutual fund scheme.

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| scheme_code | INTEGER PK | AMFI scheme code | 120503 |
| scheme_name | TEXT | Full fund name | Axis Bluechip Fund - Regular Plan - Growth |
| category_id | INTEGER FK | → category_master | 3 |
| amc_id | INTEGER FK | → fund_house_master | 2 |
| sub_category | TEXT | SEBI sub-category | Large Cap |
| benchmark | TEXT | Benchmark index name | Nifty 100 TRI |
| risk_level | TEXT | SEBI risk rating | Moderately High |
| inception_date | TEXT | Launch date (YYYY-MM-DD) | 2010-01-05 |
| expense_ratio | REAL | Annual expense % | 1.75 |
| exit_load | TEXT | Exit load description | 1% if redeemed within 1Y |
| fund_manager | TEXT | Fund manager name | Jinesh Gopani |
| plan | TEXT | Regular / Direct | Regular |
| min_sip_amount | REAL | Minimum SIP (₹) | 500 |
| min_lumpsum_amount | REAL | Minimum lump sum (₹) | 5000 |

---

## Table: nav_history

Daily NAV time-series. Core fact table.

| Column | Type | Description | Notes |
|--------|------|-------------|-------|
| nav_id | INTEGER PK | Auto-increment row ID | — |
| scheme_code | INTEGER FK | → fund_master | — |
| date | TEXT | Trading date (YYYY-MM-DD) | Business days only |
| nav | REAL | Net Asset Value (₹) | Per unit |
| daily_return | REAL | (nav_t / nav_{t-1}) - 1 | Null for first row |
| log_return | REAL | ln(nav_t / nav_{t-1}) | Null for first row |
| rolling_30d_vol | REAL | 30-day rolling vol (annualised) | Min 20 obs needed |
| rolling_90d_vol | REAL | 90-day rolling vol (annualised) | Min 60 obs needed |
| rolling_252d_vol | REAL | 252-day rolling vol (annualised) | Min 200 obs needed |
| week52_high | REAL | Highest NAV in trailing 252 days | — |
| week52_low | REAL | Lowest NAV in trailing 252 days | — |
| is_return_outlier | INTEGER | 1 if \|daily_return\| > 30% | Data quality flag |

---

## Table: performance_metrics

Pre-computed analytics per fund × period.

| Column | Type | Description | Notes |
|--------|------|-------------|-------|
| scheme_code | INTEGER FK | → fund_master | — |
| as_of_date | TEXT | Calculation end date | Latest NAV date |
| period_label | TEXT | 1Y / 3Y / 5Y / Inception | — |
| cagr | REAL | Compound Annual Growth Rate | Uses trading days, not calendar |
| absolute_return | REAL | (end/start - 1) | Raw total return |
| volatility_ann | REAL | Annualised std dev of daily returns | × √252 |
| max_drawdown | REAL | Max peak-to-trough decline | Negative value |
| sharpe_ratio | REAL | (CAGR - Rf) / volatility | Rf = 6.5% |
| sortino_ratio | REAL | (CAGR - Rf) / downside_std | Only negative returns |
| treynor_ratio | REAL | (CAGR - Rf) / beta | — |
| alpha | REAL | Jensen's alpha (annualised) | OLS regression |
| beta | REAL | Market beta vs benchmark | OLS regression |
| r_squared | REAL | R² vs benchmark | 0 to 1 |
| tracking_error | REAL | Std dev of (fund - benchmark) returns | Annualised |
| information_ratio | REAL | Alpha / tracking_error | — |
| skewness | REAL | Return distribution skewness | Negative = left tail |
| kurtosis | REAL | Excess kurtosis | >3 = fat tails |
| risk_free_rate | REAL | Rf used in calculations | Default 0.065 |

---

## Table: benchmark_nav

Daily index values for 10 benchmark indices.

| Column | Type | Description |
|--------|------|-------------|
| benchmark_name | TEXT | Index name (e.g. "Nifty 50 TRI") |
| date | TEXT | Trading date (YYYY-MM-DD) |
| index_value | REAL | Index level |

---

## View: vw_executive_summary

Full fund snapshot with latest NAV and 1Y/3Y/5Y CAGR on one row.  
**Use for:** Executive summary page, fund tables, KPI cards.

---

## View: vw_fund_performance

Daily time-series with all metadata joined.  
**Use for:** NAV trend charts, rolling volatility, return analysis.

---

## View: vw_risk_dashboard

Performance metrics with risk metadata joined.  
**Use for:** Risk comparison charts, volatility rankings, alpha/beta scatter.

---

## View: vw_category_performance

Aggregated metrics grouped by category × period.  
**Use for:** Category comparison bar charts, period comparison tables.

---

## View: vw_amc_performance

Aggregated metrics grouped by AMC × period.  
**Use for:** AMC comparison charts.

---

## View: vw_monthly_returns

Monthly return % for every fund by year-month.  
**Use for:** Calendar heatmaps, seasonal analysis.

---

## Key Definitions

**CAGR** — Compound Annual Growth Rate.  
Formula: `(end_nav / start_nav)^(1/years) - 1`  
Years calculated using **trading days ÷ 252** (not calendar days).

**Sharpe Ratio** — Risk-adjusted return per unit of total risk.  
Formula: `(CAGR - Rf) / annualised_volatility`  
Rf = 6.5% p.a. (India 10-yr G-Sec proxy).

**Sortino Ratio** — Like Sharpe but only penalises downside risk.  
Formula: `(CAGR - Rf) / downside_deviation`

**Max Drawdown** — Worst peak-to-trough decline in the period.  
Formula: `min((nav - cummax(nav)) / cummax(nav))`

**Beta** — Sensitivity to benchmark movements.  
Beta > 1: more volatile than benchmark.  
Beta < 1: less volatile than benchmark.

**Alpha (Jensen's)** — Excess return over what beta alone predicts.  
Positive alpha = fund manager added value.

**Tracking Error** — How closely a fund follows its benchmark.  
Lower = more index-like. Higher = more active.

**Information Ratio** — Alpha per unit of tracking error.  
Higher = better active management efficiency.
