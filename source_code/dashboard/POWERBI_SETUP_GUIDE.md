# Power BI Dashboard Setup Guide
## Bluestock Mutual Fund Analytics Capstone — D5

---

## Overview

The Power BI dashboard connects directly to `datasets/db/bluestock_mf.db`  
(SQLite) and uses 6 pre-built views as data sources. No transformation needed
inside Power BI — all calculations are done in the DB.

---

## Step 1 — Connect Power BI to SQLite

1. Open Power BI Desktop
2. Click **Get Data → More → Database → ODBC**
3. Install the **SQLite ODBC Driver** if not installed:
   - Download: http://www.ch-werner.de/sqliteodbc/
   - Or use: https://github.com/softace/sqliteodbc
4. Create a DSN pointing to `datasets/db/bluestock_mf.db`
5. In Power BI → **Get Data → ODBC → select your DSN**
6. Select all 6 views + tables listed below

**Alternative (simpler): Use Python connector**
1. Get Data → Python Script
2. Paste this code:
```python
import sqlite3, pandas as pd
conn = sqlite3.connect(r"C:\path\to\datasets\db\bluestock_mf.db")
df = pd.read_sql("SELECT * FROM vw_executive_summary", conn)
```

---

## Step 2 — Tables / Views to Import

| Name | Type | Used On Page |
|------|------|-------------|
| `vw_executive_summary` | View | Page 1 |
| `vw_fund_performance` | View | Page 2 |
| `vw_risk_dashboard` | View | Page 3 |
| `vw_category_performance` | View | Page 1, 3 |
| `vw_amc_performance` | View | Page 1 |
| `vw_monthly_returns` | View | Page 2 |
| `fund_master` | Table | Slicer dimension |
| `category_master` | Table | Slicer dimension |
| `fund_house_master` | Table | Slicer dimension |
| `benchmark_nav` | Table | Page 2 |

---

## Step 3 — Data Model (Relationships)

Set up these relationships in Power BI Model view:

```
fund_master[scheme_code]      →  vw_executive_summary[scheme_code]  (1:*)
fund_master[scheme_code]      →  vw_fund_performance[scheme_code]   (1:*)
fund_master[scheme_code]      →  vw_risk_dashboard[scheme_code]     (1:*)
fund_master[scheme_code]      →  vw_monthly_returns[scheme_code]    (1:*)
category_master[category_id]  →  fund_master[category_id]           (1:*)
fund_house_master[amc_id]     →  fund_master[amc_id]               (1:*)
```

---

## Step 4 — DAX Measures

Create these measures in Power BI:

```dax
// Avg CAGR 1Y (%)
Avg CAGR 1Y % = 
AVERAGE(vw_executive_summary[cagr_1y]) * 100

// Best Fund by CAGR
Best Fund 1Y = 
CALCULATE(
    FIRSTNONBLANK(vw_executive_summary[scheme_name], 1),
    TOPN(1, vw_executive_summary, vw_executive_summary[cagr_1y], DESC)
)

// Avg Sharpe Ratio
Avg Sharpe 1Y = 
AVERAGE(vw_executive_summary[sharpe_1y])

// Total Funds
Fund Count = 
DISTINCTCOUNT(fund_master[scheme_code])

// Avg Max Drawdown (%)
Avg Max DD % = 
AVERAGE(vw_risk_dashboard[max_drawdown]) * 100

// Sharpe > 1 count
Funds Sharpe > 1 = 
CALCULATE(
    COUNTROWS(vw_executive_summary),
    vw_executive_summary[sharpe_1y] > 1
)
```

---

## Step 5 — Dashboard Pages

### Page 1: Executive Summary

**Slicers:** Category | Risk Level | AMC | Period (1Y/3Y/5Y)

**Visuals:**
- 6 KPI cards: Fund Count, Avg CAGR, Best CAGR, Best Sharpe, Avg Vol, Avg MDD
- Clustered bar chart: Top 10 funds by CAGR 1Y (from `vw_executive_summary`)
- Donut chart: Fund count by sub_category
- Scatter plot: volatility_1y vs cagr_1y, coloured by risk_level
- Table: Full fund snapshot with conditional formatting on CAGR columns

### Page 2: Fund Performance

**Slicers:** Fund Name | Date Range | Category

**Visuals:**
- Line chart: nav over time (from `vw_fund_performance`) — one line per fund
- Line chart: daily_return over time
- Line chart: rolling_90d_vol over time
- Heatmap table: monthly_return_pct by year × month (from `vw_monthly_returns`)
- Line chart: fund NAV indexed vs benchmark (use `benchmark_nav`)

### Page 3: Risk Analytics

**Slicers:** Period | Risk Level | AMC

**Visuals:**
- Bar chart: volatility_ann ranked (from `vw_risk_dashboard`)
- Bar chart: max_drawdown ranked
- Scatter: beta vs alpha_1y
- Clustered bar: sharpe vs sortino
- KPI cards: Avg Vol, Avg MDD, Avg Sharpe, Avg Beta
- Table: full risk metrics

### Page 4: Portfolio & Category

**Slicers:** Category | Period

**Visuals:**
- Clustered bar: avg_cagr_pct by sub_category (from `vw_category_performance`)
- Matrix table: avg_cagr_pct × sub_category × period_label
- Bar chart: AMC performance comparison (from `vw_amc_performance`)
- Treemap: fund count by category/sub_category

---

## Step 6 — Formatting

- **Theme:** Dark (Slate/Midnight) — matches Streamlit app
- **Font:** Segoe UI, size 10-12
- **Colours:**
  - Equity: #1f77b4
  - Debt: #ff7f0e
  - Hybrid: #2ca02c
  - Index: #9467bd
  - Risk Low: #27ae60
  - Risk High: #e74c3c
- **Conditional formatting:** 
  - CAGR columns: green (>15%) → yellow (0-15%) → red (<0%)
  - MDD columns: red gradient (more negative = darker red)

---

## Alternative: Use the Streamlit App (B2)

If Power BI is unavailable, the Streamlit app provides all the same interactive
visuals and runs locally:

```bash
pip install streamlit plotly
streamlit run source_code/streamlit_app/app.py
```

Open http://localhost:8501 in your browser.

---

## Files for Dashboard

| File | Location | Purpose |
|------|----------|---------|
| `bluestock_mf.db` | `datasets/db/` | Main data source |
| `nav_all_funds_export.csv` | `datasets/exports/` | Fallback flat file |
| `performance_metrics_export.csv` | `datasets/exports/` | Metrics flat file |
| `analytics_ready.csv` | `datasets/analytics/` | Full analytics flat file |
