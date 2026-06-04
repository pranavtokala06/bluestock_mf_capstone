# Bluestock Mutual Fund Analytics Capstone

> End-to-end data engineering + analytics project covering ETL, SQLite, EDA,
> performance metrics, Power BI dashboards, advanced analytics, and reporting.

---

## Project Structure

```
bluestock_mf_capstone/
├── source_code/
│   ├── scripts/          # Python ETL & analytics scripts (D1, D4, D6, B1–B5)
│   ├── notebooks/        # Jupyter notebooks (D3, D4, D6)
│   ├── sql/              # Schema, queries, indexes
│   ├── dashboard/        # Power BI / Tableau files (D5)
│   └── streamlit_app/    # Streamlit web app (B2)
├── datasets/
│   ├── raw/              # Original fetched / synthetic NAV CSVs
│   ├── processed/        # Cleaned + enriched NAV CSVs
│   ├── analytics/        # Analytics-ready flat files for D3–D5
│   ├── exports/          # Final exports for dashboards & reports
│   └── db/               # SQLite database (D2) — NOT committed to git
├── documentation/        # Reports, data dictionary, API docs
├── ppt_slides/           # Final presentation (D7)
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
| D1 | ETL Pipeline Script   | `source_code/scripts/etl_pipeline.py`               | ✅ Day 1 |
| D2 | SQLite Database       | `datasets/db/bluestock_mf.db`                       | ✅ Day 1 |
| D3 | EDA Notebook          | `source_code/notebooks/03_eda_analysis.ipynb`       | 🔜 Day 2 |
| D4 | Performance Metrics   | `source_code/notebooks/04_performance_analytics.ipynb` | 🔜 Day 3 |
| D5 | Interactive Dashboard | `source_code/dashboard/bluestock_mf.pbix`           | 🔜 Day 4 |
| D6 | Advanced Analytics    | `source_code/notebooks/05_advanced_analytics.ipynb` | 🔜 Day 5 |
| D7 | Final Report + Slides | `documentation/Final_Report.pdf` + `ppt_slides/`    | 🔜 Day 6 |

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
