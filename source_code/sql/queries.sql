-- =============================================================================
-- queries.sql
-- Bluestock Mutual Fund Analytics Capstone — Reusable Analytical Queries
--
-- Sections
-- --------
--   Q1  Fund overview / master data
--   Q2  Latest NAV per fund
--   Q3  NAV history & returns
--   Q4  Rolling performance
--   Q5  Cross-fund comparisons
--   Q6  Category & AMC aggregations
--   Q7  Benchmark comparisons
--   Q8  Risk analytics
--   Q9  Dashboard-ready views
--  Q10  Data quality checks
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- Q1 FUND OVERVIEW
-- ─────────────────────────────────────────────────────────────────────────────

-- All funds with category and AMC info
SELECT
    fm.scheme_code,
    fm.scheme_name,
    cm.category,
    cm.sub_category,
    fhm.amc_name,
    fm.benchmark,
    fm.risk_level,
    fm.inception_date
FROM fund_master fm
LEFT JOIN category_master  cm  ON fm.category_id = cm.category_id
LEFT JOIN fund_house_master fhm ON fm.amc_id      = fhm.amc_id
ORDER BY cm.category, cm.sub_category, fm.scheme_name;

-- ─────────────────────────────────────────────────────────────────────────────
-- Q2 LATEST NAV PER FUND
-- ─────────────────────────────────────────────────────────────────────────────

-- Most recent NAV for every fund (for a "live snapshot" dashboard card)
SELECT
    nh.scheme_code,
    fm.scheme_name,
    cm.sub_category,
    fhm.amc_name,
    nh.date            AS nav_date,
    nh.nav,
    nh.daily_return,
    nh.week52_high,
    nh.week52_low,
    ROUND((nh.nav - nh.week52_low)  / nh.week52_low  * 100, 2) AS pct_above_52wk_low,
    ROUND((nh.week52_high - nh.nav) / nh.week52_high * 100, 2) AS pct_below_52wk_high
FROM nav_history nh
INNER JOIN (
    SELECT scheme_code, MAX(date) AS max_date
    FROM nav_history
    GROUP BY scheme_code
) latest ON nh.scheme_code = latest.scheme_code AND nh.date = latest.max_date
LEFT JOIN fund_master      fm  ON nh.scheme_code = fm.scheme_code
LEFT JOIN category_master  cm  ON fm.category_id  = cm.category_id
LEFT JOIN fund_house_master fhm ON fm.amc_id       = fhm.amc_id
ORDER BY cm.category, cm.sub_category, fm.scheme_name;

-- ─────────────────────────────────────────────────────────────────────────────
-- Q3 NAV HISTORY & RETURNS
-- ─────────────────────────────────────────────────────────────────────────────

-- Full daily NAV + returns for a specific fund  (parameterise :scheme_code)
SELECT
    nh.date,
    nh.nav,
    nh.daily_return,
    nh.log_return,
    nh.rolling_30d_vol,
    nh.rolling_90d_vol,
    nh.rolling_252d_vol,
    nh.week52_high,
    nh.week52_low
FROM nav_history nh
WHERE nh.scheme_code = :scheme_code   -- e.g. 120503
ORDER BY nh.date;

-- ─────────────────────────────────────────────────────────────────────────────
-- Q4 ROLLING PERFORMANCE  (1Y, 3Y, 5Y absolute returns)
-- ─────────────────────────────────────────────────────────────────────────────

-- Absolute return over last 1 year per fund
WITH latest AS (
    SELECT scheme_code, MAX(date) AS max_date FROM nav_history GROUP BY scheme_code
),
one_yr_ago AS (
    SELECT
        nh.scheme_code,
        nh.nav  AS nav_1y_ago
    FROM nav_history nh
    INNER JOIN latest l ON nh.scheme_code = l.scheme_code
    WHERE nh.date = (
        SELECT MAX(date) FROM nav_history n2
        WHERE n2.scheme_code = nh.scheme_code
          AND n2.date <= date(l.max_date, '-365 days')
    )
),
current_nav AS (
    SELECT nh.scheme_code, nh.nav AS nav_current, nh.date AS nav_date
    FROM nav_history nh
    INNER JOIN latest l ON nh.scheme_code = l.scheme_code AND nh.date = l.max_date
)
SELECT
    cn.scheme_code,
    fm.scheme_name,
    cm.sub_category,
    cn.nav_date,
    cn.nav_current,
    oy.nav_1y_ago,
    ROUND((cn.nav_current / oy.nav_1y_ago - 1) * 100, 2) AS return_1y_pct
FROM current_nav cn
JOIN one_yr_ago   oy  ON cn.scheme_code = oy.scheme_code
LEFT JOIN fund_master     fm  ON cn.scheme_code = fm.scheme_code
LEFT JOIN category_master cm  ON fm.category_id  = cm.category_id
ORDER BY return_1y_pct DESC;

-- ─────────────────────────────────────────────────────────────────────────────
-- Q5 CROSS-FUND COMPARISON — CAGR ACROSS PERIODS
-- ─────────────────────────────────────────────────────────────────────────────

-- Pre-computed performance_metrics (available after D4 is run)
SELECT
    pm.scheme_code,
    fm.scheme_name,
    cm.sub_category,
    fhm.amc_name,
    fm.risk_level,
    pm.period_label,
    ROUND(pm.cagr            * 100, 2) AS cagr_pct,
    ROUND(pm.volatility_ann  * 100, 2) AS volatility_pct,
    ROUND(pm.max_drawdown    * 100, 2) AS max_drawdown_pct,
    ROUND(pm.sharpe_ratio,         3)  AS sharpe_ratio,
    ROUND(pm.sortino_ratio,        3)  AS sortino_ratio,
    ROUND(pm.alpha           * 100, 2) AS alpha_pct,
    ROUND(pm.beta,                 3)  AS beta,
    pm.as_of_date
FROM performance_metrics pm
LEFT JOIN fund_master      fm  ON pm.scheme_code = fm.scheme_code
LEFT JOIN category_master  cm  ON fm.category_id  = cm.category_id
LEFT JOIN fund_house_master fhm ON fm.amc_id       = fhm.amc_id
ORDER BY pm.period_label, pm.cagr DESC;

-- ─────────────────────────────────────────────────────────────────────────────
-- Q6 CATEGORY & AMC AGGREGATIONS
-- ─────────────────────────────────────────────────────────────────────────────

-- Average CAGR by sub-category (for D5 bar chart)
SELECT
    cm.sub_category,
    pm.period_label,
    ROUND(AVG(pm.cagr)          * 100, 2) AS avg_cagr_pct,
    ROUND(AVG(pm.sharpe_ratio),        3) AS avg_sharpe,
    ROUND(AVG(pm.volatility_ann)* 100, 2) AS avg_vol_pct,
    COUNT(*)                               AS fund_count
FROM performance_metrics pm
LEFT JOIN fund_master     fm ON pm.scheme_code = fm.scheme_code
LEFT JOIN category_master cm ON fm.category_id  = cm.category_id
GROUP BY cm.sub_category, pm.period_label
ORDER BY pm.period_label, avg_cagr_pct DESC;

-- Fund count and category breakdown by AMC
SELECT
    fhm.amc_name,
    cm.category,
    COUNT(*)  AS fund_count
FROM fund_master fm
LEFT JOIN fund_house_master fhm ON fm.amc_id      = fhm.amc_id
LEFT JOIN category_master   cm  ON fm.category_id = cm.category_id
GROUP BY fhm.amc_name, cm.category
ORDER BY fhm.amc_name, cm.category;

-- ─────────────────────────────────────────────────────────────────────────────
-- Q7 BENCHMARK COMPARISON
-- ─────────────────────────────────────────────────────────────────────────────

-- Fund NAV vs benchmark index — for a given scheme  (:scheme_code)
-- Normalised to 100 at the earliest common date
WITH fund_data AS (
    SELECT date, nav
    FROM nav_history
    WHERE scheme_code = :scheme_code
),
bench_data AS (
    SELECT bn.date, bn.index_value
    FROM benchmark_nav bn
    JOIN fund_master fm ON fm.benchmark = bn.benchmark_name
    WHERE fm.scheme_code = :scheme_code
),
base AS (
    SELECT
        MIN(fd.date) AS base_date
    FROM fund_data fd
    JOIN bench_data bd ON fd.date = bd.date
),
base_values AS (
    SELECT
        fd.nav            AS base_nav,
        bd.index_value    AS base_index
    FROM fund_data fd
    JOIN bench_data bd ON fd.date = bd.date
    JOIN base b         ON fd.date = b.base_date
)
SELECT
    fd.date,
    ROUND(fd.nav         / bv.base_nav   * 100, 4) AS fund_indexed,
    ROUND(bd.index_value / bv.base_index * 100, 4) AS bench_indexed
FROM fund_data  fd
JOIN bench_data bd ON fd.date = bd.date
CROSS JOIN base_values bv
ORDER BY fd.date;

-- ─────────────────────────────────────────────────────────────────────────────
-- Q8 RISK ANALYTICS
-- ─────────────────────────────────────────────────────────────────────────────

-- Monthly return distribution (for histogram — D3/D5)
SELECT
    nh.scheme_code,
    fm.scheme_name,
    strftime('%Y-%m', nh.date)                AS year_month,
    ROUND(
        (MAX(nh.nav) / MIN(nh.nav) - 1) * 100, 4
    )                                          AS monthly_return_pct
FROM nav_history nh
LEFT JOIN fund_master fm ON nh.scheme_code = fm.scheme_code
GROUP BY nh.scheme_code, strftime('%Y-%m', nh.date)
ORDER BY nh.scheme_code, year_month;

-- Average rolling volatility by risk level (for D5 risk page)
SELECT
    fm.risk_level,
    rm.risk_order,
    ROUND(AVG(nh.rolling_252d_vol) * 100, 2) AS avg_annual_vol_pct,
    ROUND(AVG(nh.rolling_90d_vol)  * 100, 2) AS avg_90d_vol_pct,
    COUNT(DISTINCT nh.scheme_code)            AS fund_count
FROM nav_history nh
LEFT JOIN fund_master fm ON nh.scheme_code = fm.scheme_code
LEFT JOIN risk_master rm ON fm.risk_level   = rm.risk_level
WHERE nh.rolling_252d_vol IS NOT NULL
GROUP BY fm.risk_level, rm.risk_order
ORDER BY rm.risk_order;

-- ─────────────────────────────────────────────────────────────────────────────
-- Q9 DASHBOARD-READY VIEWS
-- ─────────────────────────────────────────────────────────────────────────────

-- Executive Summary view (D5 Page 1)
CREATE VIEW IF NOT EXISTS vw_executive_summary AS
SELECT
    fm.scheme_code,
    fm.scheme_name,
    cm.category,
    cm.sub_category,
    fhm.amc_name,
    fm.risk_level,
    fm.benchmark,
    latest_nav.nav        AS current_nav,
    latest_nav.date       AS nav_date,
    latest_nav.daily_return,
    pm_1y.cagr            AS cagr_1y,
    pm_3y.cagr            AS cagr_3y,
    pm_5y.cagr            AS cagr_5y,
    pm_1y.sharpe_ratio    AS sharpe_1y,
    pm_1y.max_drawdown    AS max_drawdown_1y,
    pm_1y.volatility_ann  AS volatility_1y
FROM fund_master fm
LEFT JOIN category_master  cm  ON fm.category_id = cm.category_id
LEFT JOIN fund_house_master fhm ON fm.amc_id      = fhm.amc_id
LEFT JOIN (
    SELECT nh.scheme_code, nh.nav, nh.date, nh.daily_return
    FROM nav_history nh
    INNER JOIN (SELECT scheme_code, MAX(date) md FROM nav_history GROUP BY scheme_code) x
        ON nh.scheme_code = x.scheme_code AND nh.date = x.md
) latest_nav ON fm.scheme_code = latest_nav.scheme_code
LEFT JOIN performance_metrics pm_1y ON fm.scheme_code = pm_1y.scheme_code AND pm_1y.period_label = '1Y'
LEFT JOIN performance_metrics pm_3y ON fm.scheme_code = pm_3y.scheme_code AND pm_3y.period_label = '3Y'
LEFT JOIN performance_metrics pm_5y ON fm.scheme_code = pm_5y.scheme_code AND pm_5y.period_label = '5Y';

-- Fund performance time-series (D5 Page 2)
CREATE VIEW IF NOT EXISTS vw_fund_performance AS
SELECT
    nh.scheme_code,
    fm.scheme_name,
    cm.category,
    cm.sub_category,
    fhm.amc_name,
    fm.risk_level,
    nh.date,
    nh.nav,
    nh.daily_return,
    nh.rolling_30d_vol,
    nh.rolling_90d_vol,
    nh.rolling_252d_vol,
    nh.week52_high,
    nh.week52_low,
    strftime('%Y',    nh.date) AS year,
    strftime('%m',    nh.date) AS month,
    strftime('%Y-%m', nh.date) AS year_month
FROM nav_history nh
LEFT JOIN fund_master      fm  ON nh.scheme_code = fm.scheme_code
LEFT JOIN category_master  cm  ON fm.category_id  = cm.category_id
LEFT JOIN fund_house_master fhm ON fm.amc_id       = fhm.amc_id;

-- ─────────────────────────────────────────────────────────────────────────────
-- Q10 DATA QUALITY CHECKS
-- ─────────────────────────────────────────────────────────────────────────────

-- Funds with sparse NAV data (< 200 rows)
SELECT
    fm.scheme_code,
    fm.scheme_name,
    COUNT(*) AS nav_row_count
FROM nav_history nh
JOIN fund_master fm ON nh.scheme_code = fm.scheme_code
GROUP BY nh.scheme_code
HAVING COUNT(*) < 200
ORDER BY nav_row_count;

-- Detect gaps > 5 business days (simplified — date diff check)
SELECT
    scheme_code,
    date,
    LAG(date) OVER (PARTITION BY scheme_code ORDER BY date) AS prev_date,
    julianday(date) - julianday(LAG(date) OVER (PARTITION BY scheme_code ORDER BY date)) AS gap_days
FROM nav_history
WHERE gap_days > 5
ORDER BY scheme_code, date;

-- ETL run history
SELECT * FROM etl_run_log ORDER BY run_timestamp DESC LIMIT 20;
