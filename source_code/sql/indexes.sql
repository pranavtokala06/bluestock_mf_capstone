-- =============================================================================
-- indexes.sql
-- Bluestock Mutual Fund Analytics Capstone — Performance Indexes
--
-- Run AFTER schema.sql and after data is loaded.
-- These indexes make Power BI queries (D5) and analytics notebooks (D3/D4/D6)
-- run significantly faster on large datasets.
-- =============================================================================

-- ── nav_history (most queried table) ─────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_nav_scheme_date    ON nav_history (scheme_code, date);
CREATE INDEX IF NOT EXISTS idx_nav_date           ON nav_history (date);
CREATE INDEX IF NOT EXISTS idx_nav_scheme         ON nav_history (scheme_code);
CREATE INDEX IF NOT EXISTS idx_nav_outlier        ON nav_history (is_return_outlier) WHERE is_return_outlier = 1;

-- ── benchmark_nav ─────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_bench_name_date    ON benchmark_nav (benchmark_name, date);
CREATE INDEX IF NOT EXISTS idx_bench_date         ON benchmark_nav (date);

-- ── performance_metrics ───────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_perf_scheme_period ON performance_metrics (scheme_code, period_label);
CREATE INDEX IF NOT EXISTS idx_perf_period        ON performance_metrics (period_label);
CREATE INDEX IF NOT EXISTS idx_perf_as_of_date    ON performance_metrics (as_of_date);

-- ── fund_master ───────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_fund_category      ON fund_master (category_id);
CREATE INDEX IF NOT EXISTS idx_fund_amc           ON fund_master (amc_id);
CREATE INDEX IF NOT EXISTS idx_fund_risk          ON fund_master (risk_level);

-- ── ANALYSE to update query planner statistics ────────────────────────────────
ANALYZE;
