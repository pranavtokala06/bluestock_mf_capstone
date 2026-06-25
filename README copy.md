# Bluestock Mutual Fund Analytics Capstone
## Complete Submission — Days 1 through 5

---

## Project Structure

```
bluestock_mf_capstone/
├── data/
│   ├── raw/                          10 original CSVs
│   ├── processed/                    12 cleaned output CSVs
│   ├── charts/                       21 exported PNG charts
│   └── db/                           bluestock_mf.db
├── notebooks/
│   ├── Day2_Clean_Load.ipynb         D2 cleaning + 10 SQL queries
│   ├── Day3_EDA_Analysis.ipynb       D3 EDA 15 charts + findings
│   └── Day4_Performance_Analytics.ipynb  D4 metrics + scorecard
├── scripts/
│   ├── day2_clean_and_load.py        D2 cleaning + star schema load
│   └── day5_dashboard.py             D5 Streamlit 6-page dashboard
├── sql/
│   ├── schema.sql                    D2 star schema DDL
│   └── queries.sql                   D2 10 analytical queries
├── documentation/
│   └── data_dictionary.md            all columns and definitions
├── CHANGELOG.md
├── requirements.txt
└── README.md
```

---

## Deliverables

| Day | Deliverable | File | Status |
|-----|-------------|------|--------|
| D1 | ETL Pipeline | etl_pipeline.py + csv_ingestion_adapter.py | Submitted |
| D2 | SQLite DB + 10 CSVs + schema + queries + dictionary | data/db/ + sql/ + documentation/ | Done |
| D3 | EDA Notebook + 15 charts | Day3_EDA_Analysis.ipynb + data/charts/ | Done |
| D4 | Performance Notebook + scorecard + alpha_beta + benchmark chart | Day4_Performance_Analytics.ipynb | Done |
| D5 | Streamlit Dashboard | scripts/day5_dashboard.py | Done |

---

## Database Star Schema

dim_fund (40) + dim_date (1,297) -> fact_nav (46,000)
                                 -> fact_transactions (32,778)
                                 -> fact_performance (40)
                                 -> fact_aum (90)

Reference: ref_sip_inflows, ref_category_inflows, ref_folio_count,
           ref_portfolio_holdings, ref_benchmark_indices

---

## Key Numbers

40 funds | 46,000 NAV rows | 32,778 transactions | 7 benchmarks
21 charts | 10 SQL queries | 11 DB tables | 15 funds with Sharpe >= 1.0
