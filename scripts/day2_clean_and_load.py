"""
day2_clean_and_load.py
======================
Bluestock MF Capstone — Day 2
Cleans all 10 CSVs, builds SQLite star schema via SQLAlchemy,
and writes 10 cleaned CSVs to data/processed/.

Day 1 built the ETL pipeline + initial DB with 19 synthetic funds.
Day 2 rebuilds the DB with all 40 real funds from your CSVs,
adds the star schema tables the tasks require, and runs validation.

Run:  python scripts/day2_clean_and_load.py
"""

from __future__ import annotations
import logging, os, sys
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE      = Path(__file__).resolve().parents[1]
RAW       = BASE / "data" / "raw"
PROCESSED = BASE / "data" / "processed"
DB_DIR    = BASE / "data" / "db"
LOG_DIR   = BASE / "logs"
for d in (PROCESSED, DB_DIR, LOG_DIR):
    d.mkdir(parents=True, exist_ok=True)

DB_PATH = DB_DIR / "bluestock_mf.db"
ENGINE  = create_engine(f"sqlite:///{DB_PATH}", echo=False)

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout),
              logging.FileHandler(LOG_DIR / "day2_clean_load.log")]
)
log = logging.getLogger("day2")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — CLEANING FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def clean_fund_master() -> pd.DataFrame:
    """
    01_fund_master.csv
    - Parse launch_date to datetime
    - Standardise category / sub_category casing
    - Validate expense_ratio in (0,3)
    - Rename amfi_code → scheme_code to match Day 1 convention
    """
    log.info("Cleaning fund_master...")
    df = pd.read_csv(RAW / "01_fund_master.csv")

    df = df.rename(columns={"amfi_code": "scheme_code", "fund_house": "amc_name",
                             "expense_ratio_pct": "expense_ratio",
                             "exit_load_pct": "exit_load",
                             "risk_category": "risk_level"})

    df["launch_date"]   = pd.to_datetime(df["launch_date"], errors="coerce")
    df["category"]      = df["category"].str.strip().str.title()
    df["sub_category"]  = df["sub_category"].str.strip()
    df["plan"]          = df["plan"].str.strip().str.title()
    df["risk_level"]    = df["risk_level"].str.strip()
    df["amc_name"]      = df["amc_name"].str.strip()

    # Validate expense ratio
    invalid_er = df[(df["expense_ratio"] < 0.1) | (df["expense_ratio"] > 2.5)]
    if len(invalid_er):
        log.warning(f"  {len(invalid_er)} rows with expense_ratio outside 0.1–2.5%")
    df = df.drop_duplicates("scheme_code")

    log.info(f"  ✅ {len(df)} funds | {df.amc_name.nunique()} AMCs | {df.sub_category.nunique()} sub-cats")
    df.to_csv(PROCESSED / "01_fund_master_clean.csv", index=False)
    return df


def clean_nav_history() -> pd.DataFrame:
    """
    02_nav_history.csv
    - Parse date to datetime, sort by scheme_code + date
    - Remove weekend rows (should be none, but defensive check)
    - Forward-fill missing business days (holidays) up to 3 days
    - Remove duplicates, validate NAV > 0
    - Compute daily_return and log_return
    """
    log.info("Cleaning nav_history...")
    df = pd.read_csv(RAW / "02_nav_history.csv")
    df = df.rename(columns={"amfi_code": "scheme_code"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "nav"])
    df = df[df["nav"] > 0]
    df = df[df["date"].dt.dayofweek < 5]          # drop any weekend rows
    df = df.drop_duplicates(["scheme_code", "date"])
    df = df.sort_values(["scheme_code", "date"]).reset_index(drop=True)

    # Forward-fill missing business days per fund
    filled_frames = []
    for code, grp in df.groupby("scheme_code"):
        grp = grp.set_index("date")
        full_idx = pd.bdate_range(grp.index.min(), grp.index.max())
        grp = grp.reindex(full_idx)
        grp["scheme_code"] = code
        grp["nav"] = grp["nav"].ffill(limit=3)
        grp = grp.dropna(subset=["nav"])
        filled_frames.append(grp.reset_index().rename(columns={"index": "date"}))
    df = pd.concat(filled_frames, ignore_index=True)

    # Derived columns
    df["daily_return"] = df.groupby("scheme_code")["nav"].pct_change()
    df["log_return"]   = np.log(df["nav"] / df.groupby("scheme_code")["nav"].shift(1))

    log.info(f"  ✅ {len(df):,} rows | {df.scheme_code.nunique()} funds | "
             f"{df.date.min().date()} → {df.date.max().date()}")
    df.to_csv(PROCESSED / "02_nav_history_clean.csv", index=False)
    return df


def clean_aum() -> pd.DataFrame:
    """03_aum_by_fund_house.csv — parse dates, validate aum > 0"""
    log.info("Cleaning aum_by_fund_house...")
    df = pd.read_csv(RAW / "03_aum_by_fund_house.csv")
    df["date"]      = pd.to_datetime(df["date"], errors="coerce")
    df["fund_house"] = df["fund_house"].str.strip()
    df = df[df["aum_crore"] > 0].drop_duplicates(["date", "fund_house"])
    df = df.sort_values(["date", "fund_house"]).reset_index(drop=True)
    log.info(f"  ✅ {len(df)} rows | {df.fund_house.nunique()} fund houses | "
             f"{df.date.dt.year.unique().tolist()} years")
    df.to_csv(PROCESSED / "03_aum_by_fund_house_clean.csv", index=False)
    return df


def clean_sip_inflows() -> pd.DataFrame:
    """
    04_monthly_sip_inflows.csv
    - Parse month to datetime (YYYY-MM → first of month)
    - yoy_growth_pct nulls for first 12 months are expected — flag not drop
    """
    log.info("Cleaning monthly_sip_inflows...")
    df = pd.read_csv(RAW / "04_monthly_sip_inflows.csv")
    df["month"] = pd.to_datetime(df["month"] + "-01", format="%Y-%m-%d")
    df = df.sort_values("month").reset_index(drop=True)
    df["yoy_growth_flag"] = df["yoy_growth_pct"].isna().map({True: "no_prior_year", False: "ok"})
    log.info(f"  ✅ {len(df)} months | max SIP ₹{df.sip_inflow_crore.max():,} Cr "
             f"({df.loc[df.sip_inflow_crore.idxmax(), 'month'].strftime('%b %Y')})")
    df.to_csv(PROCESSED / "04_monthly_sip_inflows_clean.csv", index=False)
    return df


def clean_category_inflows() -> pd.DataFrame:
    """05_category_inflows.csv — parse month, standardise category names"""
    log.info("Cleaning category_inflows...")
    df = pd.read_csv(RAW / "05_category_inflows.csv")
    df["month"]    = pd.to_datetime(df["month"] + "-01", format="%Y-%m-%d")
    df["category"] = df["category"].str.strip()
    df = df.sort_values(["month", "category"]).reset_index(drop=True)
    log.info(f"  ✅ {len(df)} rows | {df.category.nunique()} categories | "
             f"{df.month.min().date()} → {df.month.max().date()}")
    df.to_csv(PROCESSED / "05_category_inflows_clean.csv", index=False)
    return df


def clean_folio_count() -> pd.DataFrame:
    """06_industry_folio_count.csv — parse month, validate totals"""
    log.info("Cleaning industry_folio_count...")
    df = pd.read_csv(RAW / "06_industry_folio_count.csv")
    df["month"] = pd.to_datetime(df["month"] + "-01", format="%Y-%m-%d")
    df = df.sort_values("month").reset_index(drop=True)
    # Validate component sum ≈ total
    df["component_sum"] = (df["equity_folios_crore"] + df["debt_folios_crore"] +
                           df["hybrid_folios_crore"] + df["others_folios_crore"])
    df["total_check_ok"] = (abs(df["component_sum"] - df["total_folios_crore"]) < 0.05)
    log.info(f"  ✅ {len(df)} months | {df.total_folios_crore.min()} → "
             f"{df.total_folios_crore.max()} Cr folios")
    df.to_csv(PROCESSED / "06_industry_folio_count_clean.csv", index=False)
    return df


def clean_scheme_performance() -> pd.DataFrame:
    """
    07_scheme_performance.csv
    - Validate all return columns are numeric (no strings)
    - Flag anomalies: |return| > 50%
    - Validate expense_ratio in [0.1, 2.5]
    - Rename amfi_code → scheme_code
    """
    log.info("Cleaning scheme_performance...")
    df = pd.read_csv(RAW / "07_scheme_performance.csv")
    df = df.rename(columns={"amfi_code": "scheme_code"})

    ret_cols = ["return_1yr_pct", "return_3yr_pct", "return_5yr_pct", "benchmark_3yr_pct"]
    for col in ret_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["anomaly_flag"] = (
        (df["return_1yr_pct"].abs() > 50) |
        (df["return_3yr_pct"].abs() > 50) |
        (df["return_5yr_pct"].abs() > 50)
    )
    df["er_valid"] = df["expense_ratio_pct"].between(0.1, 2.5)
    n_anomaly = df["anomaly_flag"].sum()
    n_er_bad  = (~df["er_valid"]).sum()
    log.info(f"  ✅ {len(df)} schemes | anomaly flags={n_anomaly} | "
             f"expense_ratio out-of-range={n_er_bad}")
    df.to_csv(PROCESSED / "07_scheme_performance_clean.csv", index=False)
    return df


def clean_transactions() -> pd.DataFrame:
    """
    08_investor_transactions.csv
    - Parse transaction_date to datetime
    - Standardise transaction_type: SIP / Lumpsum / Redemption (title case)
    - Validate amount_inr > 0
    - Validate kyc_status in {Verified, Pending}
    - Rename amfi_code → scheme_code
    """
    log.info("Cleaning investor_transactions...")
    df = pd.read_csv(RAW / "08_investor_transactions.csv")
    df = df.rename(columns={"amfi_code": "scheme_code"})

    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    df["transaction_type"] = (df["transaction_type"].str.strip()
                               .str.title()
                               .replace({"Sip": "SIP", "Lump Sum": "Lumpsum",
                                         "Lumpsum": "Lumpsum", "Redemption": "Redemption"}))
    VALID_TYPES = {"SIP", "Lumpsum", "Redemption"}
    invalid_type = ~df["transaction_type"].isin(VALID_TYPES)
    if invalid_type.sum():
        log.warning(f"  {invalid_type.sum()} rows with invalid transaction_type — dropping")
        df = df[~invalid_type]

    df = df[df["amount_inr"] > 0]

    VALID_KYC = {"Verified", "Pending"}
    invalid_kyc = ~df["kyc_status"].isin(VALID_KYC)
    if invalid_kyc.sum():
        log.warning(f"  {invalid_kyc.sum()} rows with invalid kyc_status — dropping")
        df = df[~invalid_kyc]

    df["city_tier"]   = df["city_tier"].str.upper().str.strip()
    df["age_group"]   = df["age_group"].str.strip()
    df["gender"]      = df["gender"].str.strip().str.title()
    df["state"]       = df["state"].str.strip()

    df = df.sort_values("transaction_date").reset_index(drop=True)
    log.info(f"  ✅ {len(df):,} rows | types={sorted(df.transaction_type.unique())} | "
             f"kyc={sorted(df.kyc_status.unique())} | "
             f"states={df.state.nunique()} | {df.transaction_date.min().date()} → {df.transaction_date.max().date()}")
    df.to_csv(PROCESSED / "08_investor_transactions_clean.csv", index=False)
    return df


def clean_portfolio_holdings() -> pd.DataFrame:
    """09_portfolio_holdings.csv — parse portfolio_date, validate weight_pct"""
    log.info("Cleaning portfolio_holdings...")
    df = pd.read_csv(RAW / "09_portfolio_holdings.csv")
    df = df.rename(columns={"amfi_code": "scheme_code"})
    df["portfolio_date"] = pd.to_datetime(df["portfolio_date"], errors="coerce")
    df["weight_pct"]     = pd.to_numeric(df["weight_pct"], errors="coerce")
    df["sector"]         = df["sector"].str.strip()
    df = df[df["weight_pct"] > 0].dropna(subset=["weight_pct", "portfolio_date"])
    log.info(f"  ✅ {len(df)} holdings | {df.scheme_code.nunique()} funds | "
             f"{df.sector.nunique()} sectors")
    df.to_csv(PROCESSED / "09_portfolio_holdings_clean.csv", index=False)
    return df


def clean_benchmark() -> pd.DataFrame:
    """10_benchmark_indices.csv — parse date, validate close_value > 0"""
    log.info("Cleaning benchmark_indices...")
    df = pd.read_csv(RAW / "10_benchmark_indices.csv")
    df["date"]        = pd.to_datetime(df["date"], errors="coerce")
    df["index_name"]  = df["index_name"].str.strip()
    df["close_value"] = pd.to_numeric(df["close_value"], errors="coerce")
    df = df[df["close_value"] > 0].dropna()
    df = df[df["date"].dt.dayofweek < 5]
    df = df.drop_duplicates(["date", "index_name"])
    df = df.sort_values(["index_name", "date"]).reset_index(drop=True)
    # Compute daily return per index
    df["daily_return"] = df.groupby("index_name")["close_value"].pct_change()
    log.info(f"  ✅ {len(df):,} rows | {df.index_name.nunique()} indices | "
             f"{df.date.min().date()} → {df.date.max().date()}")
    df.to_csv(PROCESSED / "10_benchmark_indices_clean.csv", index=False)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — STAR SCHEMA CREATION
# ══════════════════════════════════════════════════════════════════════════════

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ── DIMENSION: Fund ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_fund (
    scheme_code         INTEGER PRIMARY KEY,
    scheme_name         TEXT    NOT NULL,
    amc_name            TEXT    NOT NULL,
    category            TEXT,
    sub_category        TEXT,
    plan                TEXT,
    launch_date         TEXT,
    benchmark           TEXT,
    expense_ratio       REAL,
    exit_load           REAL,
    min_sip_amount      INTEGER,
    min_lumpsum_amount  INTEGER,
    fund_manager        TEXT,
    risk_level          TEXT,
    sebi_category_code  TEXT
);

-- ── DIMENSION: Date ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_date (
    date_key    TEXT PRIMARY KEY,   -- YYYY-MM-DD
    year        INTEGER,
    quarter     INTEGER,
    month       INTEGER,
    month_name  TEXT,
    week        INTEGER,
    day_of_week INTEGER,
    is_year_end INTEGER DEFAULT 0
);

-- ── FACT: NAV History ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fact_nav (
    nav_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_code     INTEGER REFERENCES dim_fund(scheme_code),
    date_key        TEXT    REFERENCES dim_date(date_key),
    nav             REAL    NOT NULL,
    daily_return    REAL,
    log_return      REAL,
    UNIQUE(scheme_code, date_key)
);

-- ── FACT: Investor Transactions ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fact_transactions (
    txn_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    investor_id         TEXT,
    date_key            TEXT    REFERENCES dim_date(date_key),
    scheme_code         INTEGER REFERENCES dim_fund(scheme_code),
    transaction_type    TEXT    CHECK(transaction_type IN ('SIP','Lumpsum','Redemption')),
    amount_inr          REAL    NOT NULL,
    state               TEXT,
    city                TEXT,
    city_tier           TEXT    CHECK(city_tier IN ('T30','B30')),
    age_group           TEXT,
    gender              TEXT,
    annual_income_lakh  REAL,
    payment_mode        TEXT,
    kyc_status          TEXT    CHECK(kyc_status IN ('Verified','Pending'))
);

-- ── FACT: Scheme Performance ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fact_performance (
    perf_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_code         INTEGER REFERENCES dim_fund(scheme_code),
    return_1yr_pct      REAL,
    return_3yr_pct      REAL,
    return_5yr_pct      REAL,
    benchmark_3yr_pct   REAL,
    alpha               REAL,
    beta                REAL,
    sharpe_ratio        REAL,
    sortino_ratio       REAL,
    std_dev_ann_pct     REAL,
    max_drawdown_pct    REAL,
    aum_crore           INTEGER,
    expense_ratio_pct   REAL,
    morningstar_rating  INTEGER,
    risk_grade          TEXT,
    UNIQUE(scheme_code)
);

-- ── FACT: AUM by Fund House ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fact_aum (
    aum_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date_key        TEXT    REFERENCES dim_date(date_key),
    fund_house      TEXT    NOT NULL,
    aum_lakh_crore  REAL,
    aum_crore       INTEGER,
    num_schemes     INTEGER,
    UNIQUE(date_key, fund_house)
);

-- ── INDEXES ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_nav_scheme_date   ON fact_nav(scheme_code, date_key);
CREATE INDEX IF NOT EXISTS idx_nav_date          ON fact_nav(date_key);
CREATE INDEX IF NOT EXISTS idx_txn_date          ON fact_transactions(date_key);
CREATE INDEX IF NOT EXISTS idx_txn_scheme        ON fact_transactions(scheme_code);
CREATE INDEX IF NOT EXISTS idx_txn_state         ON fact_transactions(state);
CREATE INDEX IF NOT EXISTS idx_txn_type          ON fact_transactions(transaction_type);
CREATE INDEX IF NOT EXISTS idx_aum_date          ON fact_aum(date_key);
CREATE INDEX IF NOT EXISTS idx_fund_category     ON dim_fund(category);
CREATE INDEX IF NOT EXISTS idx_fund_amc          ON dim_fund(amc_name);
"""


def build_schema():
    log.info("Building star schema...")
    import sqlite3
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA_SQL)
    log.info("  ✅ Star schema created")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — LOAD INTO SQLITE
# ══════════════════════════════════════════════════════════════════════════════

def build_dim_date(nav_df: pd.DataFrame, txn_df: pd.DataFrame,
                   aum_df: pd.DataFrame) -> pd.DataFrame:
    """Build dim_date from all date columns across all fact tables."""
    dates = pd.concat([
        nav_df["date"],
        txn_df["transaction_date"],
        aum_df["date"],
    ]).dropna().dt.normalize().drop_duplicates().sort_values()

    dim = pd.DataFrame({"date_key": dates.dt.strftime("%Y-%m-%d")})
    dim = dim.drop_duplicates("date_key").reset_index(drop=True)
    dim["year"]        = dates.dt.year.values
    dim["quarter"]     = dates.dt.quarter.values
    dim["month"]       = dates.dt.month.values
    dim["month_name"]  = dates.dt.strftime("%b").values
    dim["week"]        = dates.dt.isocalendar().week.astype(int).values
    dim["day_of_week"] = dates.dt.dayofweek.values
    dim["is_year_end"] = ((dim["month"] == 12) & (dim["date_key"].str.endswith("31"))).astype(int)
    return dim


def load_all(fm, nav, aum, sip, cat, fol, sch, txn, ptf, bm):
    log.info("Loading all tables into SQLite...")
    engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

    # dim_date
    dim_date = build_dim_date(nav, txn, aum)
    dim_date.to_sql("dim_date", engine, if_exists="replace", index=False)
    log.info(f"  dim_date       : {len(dim_date):,} rows")

    # dim_fund
    dim_fund = fm[["scheme_code","scheme_name","amc_name","category","sub_category",
                   "plan","launch_date","benchmark","expense_ratio","exit_load",
                   "min_sip_amount","min_lumpsum_amount","fund_manager","risk_level",
                   "sebi_category_code"]].copy()
    dim_fund["launch_date"] = dim_fund["launch_date"].astype(str)
    dim_fund.to_sql("dim_fund", engine, if_exists="replace", index=False)
    log.info(f"  dim_fund       : {len(dim_fund)} rows")

    # fact_nav
    fact_nav = nav[["scheme_code","date","nav","daily_return","log_return"]].copy()
    fact_nav["date_key"] = fact_nav["date"].dt.strftime("%Y-%m-%d")
    fact_nav = fact_nav.drop(columns=["date"])
    fact_nav.to_sql("fact_nav", engine, if_exists="replace", index=False)
    log.info(f"  fact_nav       : {len(fact_nav):,} rows")

    # fact_transactions
    fact_txn = txn.copy()
    fact_txn["date_key"] = fact_txn["transaction_date"].dt.strftime("%Y-%m-%d")
    fact_txn = fact_txn.drop(columns=["transaction_date"])
    fact_txn.to_sql("fact_transactions", engine, if_exists="replace", index=False)
    log.info(f"  fact_transactions: {len(fact_txn):,} rows")

    # fact_performance
    fact_perf = sch[["scheme_code","return_1yr_pct","return_3yr_pct","return_5yr_pct",
                     "benchmark_3yr_pct","alpha","beta","sharpe_ratio","sortino_ratio",
                     "std_dev_ann_pct","max_drawdown_pct","aum_crore",
                     "expense_ratio_pct","morningstar_rating","risk_grade"]].copy()
    fact_perf.to_sql("fact_performance", engine, if_exists="replace", index=False)
    log.info(f"  fact_performance : {len(fact_perf)} rows")

    # fact_aum
    fact_aum = aum.copy()
    fact_aum["date_key"] = fact_aum["date"].dt.strftime("%Y-%m-%d")
    fact_aum = fact_aum.drop(columns=["date"])
    fact_aum.to_sql("fact_aum", engine, if_exists="replace", index=False)
    log.info(f"  fact_aum       : {len(fact_aum)} rows")

    # Extra reference tables (non-star, but useful for queries)
    sip_out = sip.copy()
    sip_out["month"] = sip_out["month"].dt.strftime("%Y-%m-%d")
    sip_out.to_sql("ref_sip_inflows", engine, if_exists="replace", index=False)

    cat_out = cat.copy()
    cat_out["month"] = cat_out["month"].dt.strftime("%Y-%m-%d")
    cat_out.to_sql("ref_category_inflows", engine, if_exists="replace", index=False)

    fol_out = fol.copy()
    fol_out["month"] = fol_out["month"].dt.strftime("%Y-%m-%d")
    fol_out.to_sql("ref_folio_count", engine, if_exists="replace", index=False)

    ptf_out = ptf.copy()
    ptf_out["portfolio_date"] = ptf_out["portfolio_date"].dt.strftime("%Y-%m-%d")
    ptf_out.to_sql("ref_portfolio_holdings", engine, if_exists="replace", index=False)

    bm_out = bm.copy()
    bm_out["date"] = bm_out["date"].dt.strftime("%Y-%m-%d")
    bm_out.to_sql("ref_benchmark_indices", engine, if_exists="replace", index=False)

    log.info("  ref tables     : sip_inflows, category_inflows, folio_count, "
             "portfolio_holdings, benchmark_indices")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

def validate():
    log.info("Validating row counts...")
    import sqlite3
    source_counts = {
        "dim_fund":         40,
        "fact_nav":         46000,   # approx after ffill may be slightly more
        "fact_transactions":32778,
        "fact_performance": 40,
        "fact_aum":         90,
    }
    with sqlite3.connect(DB_PATH) as conn:
        all_ok = True
        for table, expected in source_counts.items():
            actual = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            ok     = "✅" if actual >= expected else "⚠️ "
            if actual < expected:
                all_ok = False
            log.info(f"  {ok} {table:25s}: {actual:,} rows (expected ≥ {expected:,})")
        if all_ok:
            log.info("  All row counts validated ✅")
        else:
            log.warning("  Some counts below expected — check logs")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    log.info("=" * 60)
    log.info("DAY 2 — CLEAN & LOAD PIPELINE START")
    log.info("=" * 60)

    # 1. Clean
    fm  = clean_fund_master()
    nav = clean_nav_history()
    aum = clean_aum()
    sip = clean_sip_inflows()
    cat = clean_category_inflows()
    fol = clean_folio_count()
    sch = clean_scheme_performance()
    txn = clean_transactions()
    ptf = clean_portfolio_holdings()
    bm  = clean_benchmark()

    # 2. Schema
    build_schema()

    # 3. Load
    load_all(fm, nav, aum, sip, cat, fol, sch, txn, ptf, bm)

    # 4. Validate
    validate()

    log.info("=" * 60)
    log.info("DAY 2 COMPLETE")
    log.info(f"  DB  : {DB_PATH}")
    log.info(f"  CSVs: {PROCESSED}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
