# Bluestock Mutual Fund Analytics Capstone

> End-to-end data engineering + analytics project covering ETL, SQLite, EDA,
> performance metrics, Power BI dashboards, advanced analytics, and reporting.

---

## Project Structure

```
bluestock_mf_capstone/
├── source_code/
│   ├── scripts/          # Python ETL & analytics scripts 
│   ├── notebooks/        # Jupyter notebooks 
│   ├── sql/              # Schema, queries, indexes
│   ├── dashboard/        # Power BI / Tableau files 
│   └── streamlit_app/    # Streamlit web app
├── datasets/
│   ├── raw/              # Original fetched / synthetic NAV CSVs
│   ├── processed/        # Cleaned + enriched NAV CSVs
│   ├── analytics/        # Analytics-ready flat files 
│   ├── exports/          # Final exports for dashboards & reports
│   └── db/               # SQLite database  — NOT committed to git
├── documentation/        # Reports, data dictionary, API docs
├── ppt_slides/           # Final presentation 
├── tests/                # Pytest unit tests
└── logs/                 # ETL run logs & quality reports
```

---

## Quick Start

### 1. Clone & install

```bash
git clone https://github.com/<your-username>/bluestock_mf_capstone.git
cd bluestock_mf_capstone
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run ETL Pipeline

```bash
# Auto-detect: tries live API first, falls back to synthetic
python source_code/scripts/etl_pipeline.py

# Force synthetic (offline mode)
python source_code/scripts/etl_pipeline.py --synthetic

# Force live API (requires internet access to mfapi.in)
python source_code/scripts/etl_pipeline.py --live
```

### 3. Run Tests

```bash
pytest tests/ -v --cov=source_code/scripts
```

---

## Deliverables

| ID | Deliverable           | File(s)                                              | Status |
|----|-----------------------|------------------------------------------------------|--------|
| | ETL Pipeline Script   | `source_code/scripts/etl_pipeline.py`               | |
| | SQLite Database       | `datasets/db/bluestock_mf.db`                       | |
| | EDA Notebook          | `source_code/notebooks/03_eda_analysis.ipynb`       | |
| | Performance Metrics   | `source_code/notebooks/04_performance_analytics.ipynb` | |
| | Interactive Dashboard | `source_code/dashboard/bluestock_mf.pbix`           | |
| | Advanced Analytics    | `source_code/notebooks/05_advanced_analytics.ipynb` | |
| | Final Report + Slides | `documentation/Final_Report.pdf` + `ppt_slides/`    | |

---

## Data Source

Primary: **mfapi.in** — free, public REST API for Indian mutual fund NAV data.  
Fallback: **Geometric Brownian Motion** synthetic generator (seeded, reproducible).

---

## Engineering Standards

- `pathlib.Path` for all file operations — zero hard-coded paths
- `logging` to both console and rotating log files
- Full type hints + docstrings on every function
- Exception handling at every I/O boundary
- PEP 8 compliant

---

## License

MIT — see `LICENSE`

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
