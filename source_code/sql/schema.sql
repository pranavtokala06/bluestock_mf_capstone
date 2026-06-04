-- =============================================================================
-- schema.sql
-- Bluestock Mutual Fund Analytics Capstone — SQLite Schema (D2)
--
-- Tables
-- ------
--   category_master     — fund categories & sub-categories
--   fund_house_master   — AMC / fund house registry
--   fund_master         — one row per mutual fund scheme
--   nav_history         — daily NAV time-series (core fact table)
--   benchmark_nav       — benchmark index series
--   performance_metrics — pre-computed analytics (populated by D4 script)
--   risk_master         — risk level definitions
--   etl_run_log         — ETL audit trail
--
-- Design principles
-- -----------------
--   * 3NF normalisation
--   * Foreign keys enforced
--   * Composite UNIQUE constraints prevent duplicates on re-run
--   * Indexes on all join/filter columns for fast dashboard queries (D5)
-- =============================================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ─────────────────────────────────────────────────────────────────────────────
-- DIMENSION TABLES
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS risk_master (
    risk_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    risk_level TEXT    NOT NULL UNIQUE,
    risk_order INTEGER NOT NULL     -- 1=Low … 5=Very High (for sorting)
);

INSERT OR IGNORE INTO risk_master (risk_level, risk_order) VALUES
    ('Low',              1),
    ('Moderately Low',   2),
    ('Moderate',         3),
    ('Moderately High',  4),
    ('High',             5),
    ('Very High',        6);

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS category_master (
    category_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    category     TEXT NOT NULL,          -- Equity | Debt | Hybrid | Index
    sub_category TEXT NOT NULL,          -- Large Cap | Mid Cap | Liquid …
    UNIQUE (category, sub_category)
);

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS fund_house_master (
    amc_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    amc_name TEXT    NOT NULL UNIQUE     -- HDFC MF | Axis MF | Mirae Asset MF …
);

-- ─────────────────────────────────────────────────────────────────────────────
-- CORE DIMENSION — FUND
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS fund_master (
    scheme_code    INTEGER PRIMARY KEY,
    scheme_name    TEXT    NOT NULL,
    category_id    INTEGER REFERENCES category_master(category_id),
    amc_id         INTEGER REFERENCES fund_house_master(amc_id),
    sub_category   TEXT,
    benchmark      TEXT,
    risk_level     TEXT    REFERENCES risk_master(risk_level),
    inception_date TEXT,                 -- ISO date string YYYY-MM-DD
    aum_cr         REAL,                 -- AUM in crores (optional, for enrichment)
    expense_ratio  REAL,                 -- % p.a. (optional)
    exit_load      TEXT,                 -- e.g. "1% if redeemed within 1 year"
    created_at     TEXT    DEFAULT (datetime('now')),
    updated_at     TEXT    DEFAULT (datetime('now'))
);

-- ─────────────────────────────────────────────────────────────────────────────
-- FACT TABLE — NAV HISTORY
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nav_history (
    nav_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_code         INTEGER NOT NULL REFERENCES fund_master(scheme_code),
    date                TEXT    NOT NULL,   -- ISO date YYYY-MM-DD
    nav                 REAL    NOT NULL,
    daily_return        REAL,               -- (nav_t / nav_t-1) - 1
    log_return          REAL,               -- ln(nav_t / nav_t-1)
    rolling_30d_vol     REAL,               -- annualised 30-day rolling vol
    rolling_90d_vol     REAL,               -- annualised 90-day rolling vol
    rolling_252d_vol    REAL,               -- annualised 252-day rolling vol
    week52_high         REAL,               -- trailing 52-week high NAV
    week52_low          REAL,               -- trailing 52-week low NAV
    is_return_outlier   INTEGER DEFAULT 0,  -- 1 if |daily_return| > 30%
    UNIQUE (scheme_code, date)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- FACT TABLE — BENCHMARK INDEX
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS benchmark_nav (
    bench_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    benchmark_name  TEXT NOT NULL,
    date            TEXT NOT NULL,
    index_value     REAL NOT NULL,
    daily_return    REAL,                   -- populated by compute_metrics.py
    UNIQUE (benchmark_name, date)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- ANALYTICS TABLE — PERFORMANCE METRICS  (populated by D4)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS performance_metrics (
    metric_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_code     INTEGER NOT NULL REFERENCES fund_master(scheme_code),
    as_of_date      TEXT    NOT NULL,       -- last date of calculation window
    period_label    TEXT    NOT NULL,       -- '1Y' | '3Y' | '5Y' | 'Inception'
    -- Return metrics
    cagr            REAL,                   -- Compound Annual Growth Rate
    absolute_return REAL,                   -- (end_nav/start_nav - 1) * 100
    -- Risk metrics
    volatility_ann  REAL,                   -- annualised daily std dev
    max_drawdown    REAL,                   -- maximum peak-to-trough decline
    -- Risk-adjusted
    sharpe_ratio    REAL,                   -- (CAGR - Rf) / vol
    sortino_ratio   REAL,                   -- (CAGR - Rf) / downside_std
    treynor_ratio   REAL,                   -- (CAGR - Rf) / beta
    -- vs Benchmark
    alpha           REAL,                   -- Jensen's alpha
    beta            REAL,                   -- market beta
    r_squared       REAL,                   -- R² vs benchmark
    tracking_error  REAL,                   -- std(fund_return - bench_return)
    information_ratio REAL,                 -- alpha / tracking_error
    -- Distribution
    skewness        REAL,
    kurtosis        REAL,
    -- Assumptions
    risk_free_rate  REAL    DEFAULT 0.065,  -- 6.5% p.a. (India 10yr G-Sec proxy)
    computed_at     TEXT    DEFAULT (datetime('now')),
    UNIQUE (scheme_code, as_of_date, period_label)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- AUDIT TABLE
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS etl_run_log (
    run_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_timestamp   TEXT DEFAULT (datetime('now')),
    source          TEXT,                   -- 'mfapi.in' | 'synthetic'
    funds_loaded    INTEGER,
    total_nav_rows  INTEGER,
    status          TEXT,                   -- 'SUCCESS' | 'PARTIAL' | 'FAILED'
    notes           TEXT
);

-- ─────────────────────────────────────────────────────────────────────────────
-- INDEXES
-- ─────────────────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_nav_scheme_date   ON nav_history     (scheme_code, date);
CREATE INDEX IF NOT EXISTS idx_nav_date          ON nav_history     (date);
CREATE INDEX IF NOT EXISTS idx_nav_scheme        ON nav_history     (scheme_code);
CREATE INDEX IF NOT EXISTS idx_bench_name_date   ON benchmark_nav   (benchmark_name, date);
CREATE INDEX IF NOT EXISTS idx_perf_scheme_period ON performance_metrics (scheme_code, period_label);
CREATE INDEX IF NOT EXISTS idx_fund_category     ON fund_master     (category_id);
CREATE INDEX IF NOT EXISTS idx_fund_amc          ON fund_master     (amc_id);
