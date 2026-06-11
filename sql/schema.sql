-- =============================================================================
-- schema.sql
-- Bluestock MF Capstone — Day 2 Star Schema
-- Database: data/db/bluestock_mf.db
-- =============================================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ── DIMENSION: Fund ───────────────────────────────────────────────────────────
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
    date_key    TEXT PRIMARY KEY,
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
    nav_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_code  INTEGER REFERENCES dim_fund(scheme_code),
    date_key     TEXT    REFERENCES dim_date(date_key),
    nav          REAL    NOT NULL,
    daily_return REAL,
    log_return   REAL,
    UNIQUE(scheme_code, date_key)
);

-- ── FACT: Investor Transactions ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fact_transactions (
    txn_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    investor_id        TEXT,
    date_key           TEXT  REFERENCES dim_date(date_key),
    scheme_code        INTEGER REFERENCES dim_fund(scheme_code),
    transaction_type   TEXT  CHECK(transaction_type IN ('SIP','Lumpsum','Redemption')),
    amount_inr         REAL  NOT NULL,
    state              TEXT,
    city               TEXT,
    city_tier          TEXT  CHECK(city_tier IN ('T30','B30')),
    age_group          TEXT,
    gender             TEXT,
    annual_income_lakh REAL,
    payment_mode       TEXT,
    kyc_status         TEXT  CHECK(kyc_status IN ('Verified','Pending'))
);

-- ── FACT: Scheme Performance ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fact_performance (
    perf_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_code       INTEGER REFERENCES dim_fund(scheme_code),
    return_1yr_pct    REAL,
    return_3yr_pct    REAL,
    return_5yr_pct    REAL,
    benchmark_3yr_pct REAL,
    alpha             REAL,
    beta              REAL,
    sharpe_ratio      REAL,
    sortino_ratio     REAL,
    std_dev_ann_pct   REAL,
    max_drawdown_pct  REAL,
    aum_crore         INTEGER,
    expense_ratio_pct REAL,
    morningstar_rating INTEGER,
    risk_grade        TEXT,
    UNIQUE(scheme_code)
);

-- ── FACT: AUM by Fund House ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fact_aum (
    aum_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    date_key       TEXT REFERENCES dim_date(date_key),
    fund_house     TEXT NOT NULL,
    aum_lakh_crore REAL,
    aum_crore      INTEGER,
    num_schemes    INTEGER,
    UNIQUE(date_key, fund_house)
);

-- ── REFERENCE TABLES ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ref_sip_inflows (
    month              TEXT PRIMARY KEY,
    sip_inflow_crore   REAL,
    sip_accounts_crore REAL,
    yoy_growth_pct     REAL,
    yoy_growth_flag    TEXT
);

CREATE TABLE IF NOT EXISTS ref_category_inflows (
    month      TEXT,
    category   TEXT,
    inflow_crore  REAL,
    outflow_crore REAL,
    net_inflow_crore REAL,
    PRIMARY KEY (month, category)
);

CREATE TABLE IF NOT EXISTS ref_folio_count (
    month                TEXT PRIMARY KEY,
    total_folios_crore   REAL,
    equity_folios_crore  REAL,
    debt_folios_crore    REAL,
    hybrid_folios_crore  REAL,
    others_folios_crore  REAL,
    component_sum        REAL,
    total_check_ok       INTEGER
);

CREATE TABLE IF NOT EXISTS ref_portfolio_holdings (
    holding_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_code    INTEGER REFERENCES dim_fund(scheme_code),
    portfolio_date TEXT,
    stock_name     TEXT,
    sector         TEXT,
    weight_pct     REAL,
    market_value_cr REAL
);

CREATE TABLE IF NOT EXISTS ref_benchmark_indices (
    bench_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    date          TEXT,
    index_name    TEXT,
    close_value   REAL,
    daily_return  REAL,
    UNIQUE(date, index_name)
);

-- ── INDEXES ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_nav_scheme_date ON fact_nav(scheme_code, date_key);
CREATE INDEX IF NOT EXISTS idx_nav_date        ON fact_nav(date_key);
CREATE INDEX IF NOT EXISTS idx_txn_date        ON fact_transactions(date_key);
CREATE INDEX IF NOT EXISTS idx_txn_scheme      ON fact_transactions(scheme_code);
CREATE INDEX IF NOT EXISTS idx_txn_state       ON fact_transactions(state);
CREATE INDEX IF NOT EXISTS idx_txn_type        ON fact_transactions(transaction_type);
CREATE INDEX IF NOT EXISTS idx_aum_date        ON fact_aum(date_key);
CREATE INDEX IF NOT EXISTS idx_fund_category   ON dim_fund(category);
CREATE INDEX IF NOT EXISTS idx_fund_amc        ON dim_fund(amc_name);
CREATE INDEX IF NOT EXISTS idx_bench_name_date ON ref_benchmark_indices(index_name, date);
