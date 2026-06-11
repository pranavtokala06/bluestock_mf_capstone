-- =============================================================================
-- queries.sql
-- Bluestock MF Capstone — Day 2 Analytical Queries
-- All queries run against data/db/bluestock_mf.db
-- =============================================================================

-- ── Q1: Top 5 Funds by AUM ────────────────────────────────────────────────────
-- Shows the 5 largest funds by current AUM from fact_performance
SELECT
    f.scheme_code,
    f.scheme_name,
    f.amc_name,
    f.sub_category,
    p.aum_crore,
    ROUND(p.aum_crore / 1000.0, 2)     AS aum_thousand_crore,
    p.expense_ratio_pct,
    p.return_3yr_pct
FROM fact_performance p
JOIN dim_fund f ON p.scheme_code = f.scheme_code
ORDER BY p.aum_crore DESC
LIMIT 5;

-- ── Q2: Average NAV Per Month (All Funds) ─────────────────────────────────────
-- Monthly average NAV across all 40 funds — shows market trend
SELECT
    d.year,
    d.month,
    d.month_name,
    ROUND(AVG(n.nav), 4)           AS avg_nav,
    ROUND(MIN(n.nav), 4)           AS min_nav,
    ROUND(MAX(n.nav), 4)           AS max_nav,
    COUNT(DISTINCT n.scheme_code)  AS funds_reporting
FROM fact_nav n
JOIN dim_date d ON n.date_key = d.date_key
GROUP BY d.year, d.month
ORDER BY d.year, d.month;

-- ── Q3: SIP Year-on-Year Growth ───────────────────────────────────────────────
-- YoY SIP inflow growth by year — shows industry momentum
SELECT
    strftime('%Y', month) AS year,
    ROUND(SUM(sip_inflow_crore), 2)        AS total_sip_crore,
    ROUND(AVG(sip_inflow_crore), 2)        AS avg_monthly_sip,
    ROUND(MAX(sip_inflow_crore), 2)        AS peak_month_sip,
    COUNT(*)                                AS months_in_year,
    ROUND(AVG(yoy_growth_pct), 2)          AS avg_yoy_growth_pct
FROM ref_sip_inflows
GROUP BY strftime('%Y', month)
ORDER BY year;

-- ── Q4: Transactions by State ─────────────────────────────────────────────────
-- Total SIP + investment amount by state — geographic penetration
SELECT
    state,
    COUNT(*)                                          AS txn_count,
    ROUND(SUM(amount_inr) / 1e7, 2)                  AS total_crore,
    ROUND(AVG(amount_inr), 2)                         AS avg_ticket_size,
    SUM(CASE WHEN transaction_type='SIP'      THEN 1 ELSE 0 END) AS sip_count,
    SUM(CASE WHEN transaction_type='Lumpsum'  THEN 1 ELSE 0 END) AS lumpsum_count,
    SUM(CASE WHEN transaction_type='Redemption' THEN 1 ELSE 0 END) AS redemption_count
FROM fact_transactions
GROUP BY state
ORDER BY total_crore DESC;

-- ── Q5: Funds with Expense Ratio < 1% ─────────────────────────────────────────
-- Low-cost funds — important for long-term investor returns
SELECT
    f.scheme_code,
    f.scheme_name,
    f.amc_name,
    f.sub_category,
    f.plan,
    p.expense_ratio_pct,
    p.return_3yr_pct,
    p.sharpe_ratio,
    p.morningstar_rating
FROM fact_performance p
JOIN dim_fund f ON p.scheme_code = f.scheme_code
WHERE p.expense_ratio_pct < 1.0
ORDER BY p.expense_ratio_pct ASC;

-- ── Q6: Category-wise Net Inflows (Latest 12 Months) ─────────────────────────
-- Which fund categories are gaining/losing money
SELECT
    category,
    ROUND(SUM(inflow_crore), 2)      AS total_inflow,
    ROUND(SUM(outflow_crore), 2)     AS total_outflow,
    ROUND(SUM(net_inflow_crore), 2)  AS net_inflow,
    COUNT(DISTINCT month)            AS months
FROM ref_category_inflows
GROUP BY category
ORDER BY net_inflow DESC;

-- ── Q7: Fund House AUM Dominance (Latest Year) ────────────────────────────────
-- Market share by AMC for 2025
SELECT
    fund_house,
    ROUND(SUM(aum_lakh_crore), 2)          AS total_aum_lakh_crore,
    ROUND(SUM(aum_lakh_crore) /
        SUM(SUM(aum_lakh_crore)) OVER() * 100, 2) AS market_share_pct,
    AVG(num_schemes)                        AS avg_schemes
FROM fact_aum
WHERE date_key LIKE '2025%'
GROUP BY fund_house
ORDER BY total_aum_lakh_crore DESC;

-- ── Q8: Top 10 Funds by 3-Year CAGR with Risk-Adjusted Score ─────────────────
-- Best performing funds balancing return and risk
SELECT
    f.scheme_name,
    f.sub_category,
    f.amc_name,
    f.risk_level,
    p.return_3yr_pct,
    p.sharpe_ratio,
    p.sortino_ratio,
    p.max_drawdown_pct,
    p.alpha,
    p.beta,
    p.morningstar_rating,
    -- Composite score: 40% return + 35% sharpe + 25% drawdown (inverted)
    ROUND(
        0.40 * (p.return_3yr_pct / MAX(p.return_3yr_pct) OVER()) +
        0.35 * (p.sharpe_ratio   / MAX(p.sharpe_ratio)   OVER()) +
        0.25 * (1 + p.max_drawdown_pct / MIN(p.max_drawdown_pct) OVER())
    , 4) AS composite_score
FROM fact_performance p
JOIN dim_fund f ON p.scheme_code = f.scheme_code
ORDER BY p.return_3yr_pct DESC
LIMIT 10;

-- ── Q9: SIP Investor Age and Gender Demographics ──────────────────────────────
-- SIP penetration by age group and gender
SELECT
    age_group,
    gender,
    COUNT(*)                              AS sip_transactions,
    ROUND(AVG(amount_inr), 2)            AS avg_sip_amount,
    ROUND(SUM(amount_inr) / 1e7, 2)     AS total_crore,
    ROUND(AVG(annual_income_lakh), 2)    AS avg_annual_income_lakh,
    SUM(CASE WHEN kyc_status='Verified' THEN 1 ELSE 0 END) AS kyc_verified_count
FROM fact_transactions
WHERE transaction_type = 'SIP'
GROUP BY age_group, gender
ORDER BY age_group, gender;

-- ── Q10: Folio Count Growth Rate by Quarter ───────────────────────────────────
-- Industry participant growth showing retail investor adoption
SELECT
    strftime('%Y', month)                    AS year,
    CASE
        WHEN CAST(strftime('%m', month) AS INT) <= 3  THEN 'Q1'
        WHEN CAST(strftime('%m', month) AS INT) <= 6  THEN 'Q2'
        WHEN CAST(strftime('%m', month) AS INT) <= 9  THEN 'Q3'
        ELSE 'Q4'
    END                                       AS quarter,
    MAX(total_folios_crore)                  AS end_folios_crore,
    MIN(total_folios_crore)                  AS start_folios_crore,
    ROUND(MAX(total_folios_crore) -
          MIN(total_folios_crore), 2)         AS net_new_folios_crore,
    MAX(equity_folios_crore)                 AS equity_folios_crore
FROM ref_folio_count
GROUP BY year, quarter
ORDER BY year, quarter;
