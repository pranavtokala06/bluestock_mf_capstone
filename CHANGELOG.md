# CHANGELOG
## Bluestock Mutual Fund Analytics Capstone

---

## Day 1 — ETL Pipeline (Submitted)
**Deliverable:** D1 — `etl_pipeline.py`, `csv_ingestion_adapter.py`

### What was built
- `source_code/scripts/etl_pipeline.py` — Live API ETL via mfapi.in with GBM fallback
- `source_code/scripts/csv_ingestion_adapter.py` — Drop-in adapter for your 10 CSVs
- `source_code/scripts/live_nav_fetch.py` — Incremental daily NAV refresh
- Initial SQLite DB with 19 synthetic funds (rebuilt in Day 2 with all 40 real funds)
- `source_code/sql/schema.sql` — Initial schema (replaced by star schema in Day 2)
- `tests/test_etl.py` — 31 unit tests (all passing)
- `requirements.txt`, `.gitignore`, `README.md`

### Key decisions
- Dual-mode extract: live API → synthetic fallback, controlled by `--synthetic` / `--live` flag
- Geometric Brownian Motion for synthetic data seeded by scheme_code (reproducible)
- `pathlib.Path` throughout, zero hardcoded paths
- ETL run audit log in `etl_run_log` table

---

## Day 2 — Data Cleaning + SQLite Star Schema
**Deliverable:** D2 — 10 cleaned CSVs, `bluestock_mf.db`, `schema.sql`, `queries.sql`, `data_dictionary.md`

### New files
| File | Description |
|------|-------------|
| `scripts/day2_clean_and_load.py` | Master cleaning + loading script |
| `sql/schema.sql` | Star schema DDL (rebuilt) |
| `sql/queries.sql` | 10 analytical SQL queries |
| `documentation/data_dictionary.md` | Full column documentation |
| `notebooks/Day2_Clean_Load.ipynb` | Verification notebook |
| `data/processed/01_fund_master_clean.csv` | 40 funds cleaned |
| `data/processed/02_nav_history_clean.csv` | 46,000 rows cleaned |
| `data/processed/03_aum_by_fund_house_clean.csv` | 90 rows |
| `data/processed/04_monthly_sip_inflows_clean.csv` | 48 months |
| `data/processed/05_category_inflows_clean.csv` | 144 rows |
| `data/processed/06_industry_folio_count_clean.csv` | 21 months |
| `data/processed/07_scheme_performance_clean.csv` | 40 funds |
| `data/processed/08_investor_transactions_clean.csv` | 32,778 rows |
| `data/processed/09_portfolio_holdings_clean.csv` | 322 holdings |
| `data/processed/10_benchmark_indices_clean.csv` | 8,050 rows |

### Cleaning applied per file
| File | Cleaning Steps |
|------|----------------|
| `fund_master` | Rename amfi_code→scheme_code, parse launch_date, validate expense_ratio 0.1–2.5% |
| `nav_history` | Parse dates, remove weekends, ffill missing business days (max 3), dedup, validate nav>0, compute daily_return + log_return |
| `aum` | Parse dates, validate aum>0, dedup |
| `sip_inflows` | Parse month to datetime, flag yoy_growth nulls for first 12 months (no prior year — expected) |
| `category_inflows` | Parse month, standardise category names |
| `folio_count` | Parse month, validate component sum ≈ total |
| `scheme_performance` | All return cols to numeric, anomaly flag for \|return\|>50%, expense_ratio range check |
| `transactions` | transaction_type→SIP/Lumpsum/Redemption (title case), validate amount>0, kyc_status enum {Verified,Pending}, city_tier→T30/B30 uppercase |
| `portfolio_holdings` | Parse portfolio_date, validate weight_pct>0 |
| `benchmark_indices` | Parse date, remove weekends, validate close_value>0, compute daily_return |

### Star schema tables
| Table | Type | Rows | Description |
|-------|------|------|-------------|
| `dim_fund` | Dimension | 40 | Fund master |
| `dim_date` | Dimension | 1,297 | Calendar dimension |
| `fact_nav` | Fact | 46,000 | Daily NAV |
| `fact_transactions` | Fact | 32,778 | Investor transactions |
| `fact_performance` | Fact | 40 | Scheme metrics |
| `fact_aum` | Fact | 90 | AUM by fund house |
| `ref_sip_inflows` | Reference | 48 | Monthly SIP data |
| `ref_category_inflows` | Reference | 144 | Category flows |
| `ref_folio_count` | Reference | 21 | Industry folios |
| `ref_portfolio_holdings` | Reference | 322 | Stock holdings |
| `ref_benchmark_indices` | Reference | 8,050 | Index data |

### 10 SQL Queries
- Q1: Top 5 funds by AUM
- Q2: Average NAV per month (all funds)
- Q3: SIP Year-on-Year growth by year
- Q4: Transactions by state (geographic penetration)
- Q5: Funds with expense ratio < 1%
- Q6: Category-wise net inflows (latest months)
- Q7: Fund house AUM market share (2025)
- Q8: Top 10 funds by 3Y CAGR with composite score
- Q9: SIP investor age and gender demographics
- Q10: Folio count growth rate by quarter

### Changed from Day 1
- DB rebuilt from scratch with all 40 real funds (was 19 synthetic)
- Schema changed from basic tables to proper star schema
- Added `dim_date` dimension table
- Renamed `scheme_code` from `amfi_code` throughout

---

## Day 3 — Exploratory Data Analysis (EDA)
**Deliverable:** D3 — `Day3_EDA_Analysis.ipynb`, 15+ exported PNG charts

### New files
| File | Description |
|------|-------------|
| `notebooks/Day3_EDA_Analysis.ipynb` | Full EDA notebook with 15 chart cells |
| `data/charts/chart01_nav_trends.png` | NAV indexed trends all 40 funds |
| `data/charts/chart02_aum_by_fundhouse.png` | AUM grouped bar by fund house |
| `data/charts/chart03_sip_timeseries.png` | SIP inflows with Rs.31,002 Cr annotation |
| `data/charts/chart04_category_inflow_heatmap.png` | Category net inflow heatmap |
| `data/charts/chart05_investor_demographics.png` | Age, SIP boxplot, gender split |
| `data/charts/chart06_geographic.png` | SIP by state + T30 vs B30 |
| `data/charts/chart07_folio_growth.png` | Folio count 13.26→26.12 Cr |
| `data/charts/chart08_correlation_matrix.png` | Return correlation 10 funds |
| `data/charts/chart09_sector_allocation.png` | Sector allocation donut |
| `data/charts/chart10_returns_distribution.png` | Return dist + Sharpe chart |
| `data/charts/chart11_sip_by_age.png` | Avg SIP by age group |
| `data/charts/chart12_aum_by_category.png` | AUM by category pie |
| `data/charts/chart13_folio_stacked.png` | Folio stacked area by category |
| `data/charts/chart14_t30_b30_types.png` | T30 vs B30 by transaction type |
| `data/charts/chart15_volatility_heatmap.png` | Monthly vol heatmap |

### 10 Key EDA Findings (in notebook Markdown)
1. Equity dominates folios at 65% of 26.1 Cr total
2. SIP grew 2.7x from Rs.11,500 Cr to Rs.31,002 Cr (Jan 2022–Dec 2025)
3. SBI MF commands ~18% AUM market share at Rs.12.5+ Lakh Crore
4. Maharashtra + Karnataka + Delhi NCR = >50% of SIP inflows
5. Inter-equity correlation 0.4–0.75; small-cap vs debt near 0
6. Financial Services = ~28% of average equity fund allocation
7. 26-35 age group has highest SIP count; avg ticket ~Rs.7,500
8. Debt category shows consistent net outflows as investors shift to equity
9. Mid/Small-cap volatility spike in Jun-Sep 2024 (FII selloff period)
10. Folio count nearly doubled (13.26→26.12 Cr) in 3 years

---

## Day 4 — Fund Performance Analytics
**Deliverable:** D4 — `Day4_Performance_Analytics.ipynb`, `fund_scorecard.csv`, `alpha_beta.csv`, benchmark chart PNG

### New files
| File | Description |
|------|-------------|
| `notebooks/Day4_Performance_Analytics.ipynb` | Full performance analytics notebook |
| `data/processed/fund_scorecard.csv` | Composite scored + ranked 40 funds |
| `data/processed/alpha_beta.csv` | OLS alpha/beta vs NIFTY100 for 40 funds |
| `data/charts/chart_benchmark_comparison.png` | Top 5 funds vs NIFTY50 & NIFTY100 |
| `data/charts/chart_d4_daily_returns.png` | Return distribution + per-fund avg |
| `data/charts/chart_d4_sharpe_sortino.png` | Sharpe vs Sortino all 40 funds |
| `data/charts/chart_d4_alpha_beta.png` | Jensen's Alpha bar chart |
| `data/charts/chart_d4_drawdown_history.png` | Drawdown history equity funds |
| `data/charts/chart_d4_fund_scorecard.png` | Top 20 composite scorecard bar |

### Metrics computed (from NAV data)
| Metric | Method |
|--------|--------|
| CAGR 1Y/3Y/5Y/Inception | (end_nav/start_nav)^(1/years) − 1. Uses trading days ÷ 252 |
| Sharpe Ratio | (Ann.Return − 6.5%) / Ann.Std.Dev. × √252 |
| Sortino Ratio | Same but denominator = downside std dev only (negative days) |
| Alpha (Jensen's) | OLS intercept × 252 — vs NIFTY100 excess returns |
| Beta | OLS slope of fund excess returns on NIFTY100 excess returns |
| Max Drawdown | min((nav − cummax(nav)) / cummax(nav)) per fund |
| Tracking Error | std(fund_return − NIFTY100_return) × √252 |

### Fund Scorecard formula
```
Composite Score = 0.30 × 3Y Return Rank
               + 0.25 × Sharpe Ratio Rank
               + 0.20 × Alpha Rank
               + 0.15 × Expense Ratio Rank (inverse — lower is better)
               + 0.10 × Max Drawdown Rank  (inverse — smaller |MDD| is better)
```
All ranks normalised 0–100. Score range: 0–100.

---

## Day 5 — Interactive Streamlit Dashboard
**Deliverable:** D5 — `scripts/day5_dashboard.py`

### New files
| File | Description |
|------|-------------|
| `scripts/day5_dashboard.py` | 629-line Streamlit dashboard |

### 6 Dashboard Pages
| Page | Content |
|------|---------|
| Executive Summary | KPI cards, top/bottom performers, category donut, risk-return scatter, full fund table. Slicers: Category, Risk, AMC |
| Fund Performance | Indexed NAV trends, rolling 1Y return, rolling 90d volatility. Slicers: Fund, Date range |
| Risk Analytics | Volatility ranking, max drawdown ranking, drawdown history, full risk table. Slicers: Category, Risk |
| Industry Analytics | SIP time-series (ATH annotation), folio growth, AUM by fund house, category heatmap, demographics, SIP by state |
| Portfolio Optimiser | Markowitz efficient frontier (2,000 simulations), Max Sharpe + Min Vol portfolios, SIP calculator |
| Fund Comparison | Side-by-side metrics, winner highlighting, indexed NAV comparison, radar chart |

### Run command
```bash
streamlit run scripts/day5_dashboard.py
# Opens at http://localhost:8501
```

---
