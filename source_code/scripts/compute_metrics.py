"""
compute_metrics.py
==================
Bluestock Mutual Fund Analytics Capstone — Performance Metrics Engine (D4)

Computes and stores ALL performance metrics for every fund across all
standard periods (1Y, 3Y, 5Y, Inception) into:
  * SQLite  → performance_metrics table
  * CSV     → datasets/analytics/performance_metrics.csv

Metrics Computed
----------------
Returns      : CAGR, Absolute Return
Risk         : Annualised Volatility, Max Drawdown, Skewness, Kurtosis
Risk-Adj     : Sharpe Ratio, Sortino Ratio, Treynor Ratio
vs Benchmark : Alpha (Jensen's), Beta, R², Tracking Error, Information Ratio

Design
------
* Uses only trading days (pd.bdate_range) — no calendar-day CAGR error
* Risk-free rate = 6.5% p.a. (India 10-yr G-Sec proxy), configurable
* All metrics stored with the period label so Power BI can slice by period
* Idempotent — safe to re-run; uses INSERT OR REPLACE

Author : Bluestock Capstone Team
Date   : 2025
"""

from __future__ import annotations

import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parents[2]
ANALYTICS_DIR = BASE_DIR / "datasets" / "analytics"
DB_DIR        = BASE_DIR / "datasets" / "db"
LOG_DIR       = BASE_DIR / "logs"
for _d in (ANALYTICS_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

DB_PATH = DB_DIR / "bluestock_mf.db"

# ── Config ────────────────────────────────────────────────────────────────────
RISK_FREE_RATE  = 0.065          # 6.5% p.a.
TRADING_DAYS    = 252
MIN_ROWS        = 60             # minimum rows needed to compute metrics
PERIODS: dict[str, int | None] = {
    "1Y":        252,
    "3Y":        756,
    "5Y":        1260,
    "Inception": None,           # None = use all available data
}

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "compute_metrics.log"),
    ],
)
logger = logging.getLogger("compute_metrics")


# ─────────────────────────────────────────────────────────────────────────────
# METRIC CALCULATIONS
# ─────────────────────────────────────────────────────────────────────────────

def cagr(start_nav: float, end_nav: float, trading_days: int) -> float:
    """
    CAGR using actual trading days.
    years = trading_days / 252  (NOT calendar days)
    """
    if start_nav <= 0 or trading_days <= 0:
        return np.nan
    years = trading_days / TRADING_DAYS
    return (end_nav / start_nav) ** (1 / years) - 1


def absolute_return(start_nav: float, end_nav: float) -> float:
    if start_nav <= 0:
        return np.nan
    return (end_nav / start_nav) - 1


def annualised_volatility(daily_returns: pd.Series) -> float:
    """Annualised std dev of daily returns."""
    clean = daily_returns.dropna()
    if len(clean) < 10:
        return np.nan
    return float(clean.std() * np.sqrt(TRADING_DAYS))


def max_drawdown(nav_series: pd.Series) -> float:
    """Maximum peak-to-trough drawdown (negative value)."""
    if len(nav_series) < 2:
        return np.nan
    rolling_max = nav_series.cummax()
    drawdown    = (nav_series - rolling_max) / rolling_max
    return float(drawdown.min())


def sharpe_ratio(fund_cagr: float, volatility: float,
                 rf: float = RISK_FREE_RATE) -> float:
    if volatility <= 0 or np.isnan(volatility):
        return np.nan
    return (fund_cagr - rf) / volatility


def sortino_ratio(daily_returns: pd.Series, fund_cagr: float,
                  rf: float = RISK_FREE_RATE) -> float:
    """Uses downside deviation (returns below 0) as risk measure."""
    clean = daily_returns.dropna()
    if len(clean) < 10:
        return np.nan
    downside = clean[clean < 0]
    if len(downside) < 5:
        return np.nan
    downside_std = float(downside.std() * np.sqrt(TRADING_DAYS))
    if downside_std <= 0:
        return np.nan
    return (fund_cagr - rf) / downside_std


def beta_alpha(fund_returns: pd.Series, bench_returns: pd.Series,
               rf_daily: float) -> tuple[float, float, float]:
    """
    OLS regression of (fund_excess) on (bench_excess).
    Returns (beta, alpha_annualised, r_squared).
    """
    aligned = pd.concat([fund_returns, bench_returns], axis=1).dropna()
    aligned.columns = ["fund", "bench"]
    if len(aligned) < MIN_ROWS:
        return np.nan, np.nan, np.nan

    f_excess = aligned["fund"]  - rf_daily
    b_excess = aligned["bench"] - rf_daily

    slope, intercept, r, _, _ = sp_stats.linregress(b_excess, f_excess)
    beta       = float(slope)
    alpha_ann  = float(intercept * TRADING_DAYS)   # annualise daily alpha
    r_squared  = float(r ** 2)
    return beta, alpha_ann, r_squared


def treynor_ratio(fund_cagr: float, beta: float,
                  rf: float = RISK_FREE_RATE) -> float:
    if np.isnan(beta) or beta == 0:
        return np.nan
    return (fund_cagr - rf) / beta


def tracking_error(fund_returns: pd.Series, bench_returns: pd.Series) -> float:
    diff = (fund_returns - bench_returns).dropna()
    if len(diff) < 10:
        return np.nan
    return float(diff.std() * np.sqrt(TRADING_DAYS))


def information_ratio(alpha: float, te: float) -> float:
    if np.isnan(te) or te <= 0:
        return np.nan
    return alpha / te


def skewness(daily_returns: pd.Series) -> float:
    clean = daily_returns.dropna()
    if len(clean) < 10:
        return np.nan
    return float(sp_stats.skew(clean))


def kurtosis(daily_returns: pd.Series) -> float:
    clean = daily_returns.dropna()
    if len(clean) < 10:
        return np.nan
    return float(sp_stats.kurtosis(clean))   # excess kurtosis


# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADER
# ─────────────────────────────────────────────────────────────────────────────

class MetricsDataLoader:
    """Loads NAV and benchmark data from SQLite for metric computation."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path

    def load_fund_nav(self) -> pd.DataFrame:
        """Load full nav_history with fund metadata."""
        query = """
            SELECT
                nh.scheme_code,
                fm.scheme_name,
                cm.category,
                cm.sub_category,
                fhm.amc_name,
                fm.benchmark,
                fm.risk_level,
                nh.date,
                nh.nav,
                nh.daily_return,
                nh.log_return
            FROM nav_history nh
            LEFT JOIN fund_master      fm  ON nh.scheme_code = fm.scheme_code
            LEFT JOIN category_master  cm  ON fm.category_id  = cm.category_id
            LEFT JOIN fund_house_master fhm ON fm.amc_id       = fhm.amc_id
            ORDER BY nh.scheme_code, nh.date
        """
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn, parse_dates=["date"])
        logger.info("Loaded %d NAV rows for %d funds",
                    len(df), df["scheme_code"].nunique())
        return df

    def load_benchmark_nav(self) -> pd.DataFrame:
        """Load benchmark index series."""
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(
                "SELECT benchmark_name, date, index_value FROM benchmark_nav ORDER BY benchmark_name, date",
                conn, parse_dates=["date"]
            )
        # Compute benchmark daily returns
        df = df.sort_values(["benchmark_name", "date"])
        df["bench_return"] = df.groupby("benchmark_name")["index_value"].pct_change()
        logger.info("Loaded benchmark data: %d series", df["benchmark_name"].nunique())
        return df

    def load_fund_list(self) -> pd.DataFrame:
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(
                """SELECT fm.scheme_code, fm.scheme_name, cm.sub_category,
                          fhm.amc_name, fm.benchmark, fm.risk_level
                   FROM fund_master fm
                   LEFT JOIN category_master  cm  ON fm.category_id=cm.category_id
                   LEFT JOIN fund_house_master fhm ON fm.amc_id=fhm.amc_id""",
                conn
            )


# ─────────────────────────────────────────────────────────────────────────────
# METRICS ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class MetricsEngine:
    """
    Computes all performance metrics for every fund × every period.
    """

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path    = db_path
        self.loader     = MetricsDataLoader(db_path)
        self.rf_daily   = RISK_FREE_RATE / TRADING_DAYS

    def run(self) -> pd.DataFrame:
        """Compute metrics for all funds and all periods. Returns results DataFrame."""
        logger.info("Loading data...")
        nav_df   = self.loader.load_fund_nav()
        bench_df = self.loader.load_benchmark_nav()
        funds    = self.loader.load_fund_list()

        as_of_date = nav_df["date"].max().date().isoformat()
        results: list[dict[str, Any]] = []

        logger.info("Computing metrics for %d funds × %d periods...",
                    len(funds), len(PERIODS))

        for i, fund_row in funds.iterrows():
            sc        = fund_row["scheme_code"]
            bench_name = fund_row["benchmark"]

            # Fund NAV slice
            fund_nav = nav_df[nav_df["scheme_code"] == sc].copy()
            if len(fund_nav) < MIN_ROWS:
                logger.warning("Skipping %s — only %d rows", sc, len(fund_nav))
                continue

            # Benchmark returns aligned to fund dates
            bench_series = bench_df[bench_df["benchmark_name"] == bench_name].set_index("date")["bench_return"]

            for period_label, lookback_days in PERIODS.items():
                # Slice to period window
                if lookback_days is not None:
                    period_nav = fund_nav.tail(lookback_days).copy()
                else:
                    period_nav = fund_nav.copy()

                if len(period_nav) < MIN_ROWS:
                    continue

                period_nav = period_nav.set_index("date")
                fund_returns = period_nav["daily_return"].dropna()

                # Core nav values
                start_nav_val = float(period_nav["nav"].iloc[0])
                end_nav_val   = float(period_nav["nav"].iloc[-1])
                n_trading     = len(period_nav)

                # Align benchmark
                bench_aligned = bench_series.reindex(period_nav.index)

                # ── Compute all metrics ──────────────────────────────────────
                fund_cagr     = cagr(start_nav_val, end_nav_val, n_trading)
                abs_ret       = absolute_return(start_nav_val, end_nav_val)
                vol           = annualised_volatility(fund_returns)
                mdd           = max_drawdown(period_nav["nav"])
                sharpe        = sharpe_ratio(fund_cagr, vol)
                sortino       = sortino_ratio(fund_returns, fund_cagr)
                beta_v, alpha_v, r2 = beta_alpha(fund_returns, bench_aligned, self.rf_daily)
                treynor       = treynor_ratio(fund_cagr, beta_v)
                te            = tracking_error(fund_returns, bench_aligned)
                ir            = information_ratio(alpha_v, te) if not np.isnan(alpha_v) else np.nan
                skew          = skewness(fund_returns)
                kurt          = kurtosis(fund_returns)

                results.append({
                    "scheme_code":      sc,
                    "as_of_date":       as_of_date,
                    "period_label":     period_label,
                    "cagr":             round(fund_cagr,  6) if not np.isnan(fund_cagr)  else None,
                    "absolute_return":  round(abs_ret,    6) if not np.isnan(abs_ret)    else None,
                    "volatility_ann":   round(vol,        6) if not np.isnan(vol)        else None,
                    "max_drawdown":     round(mdd,        6) if not np.isnan(mdd)        else None,
                    "sharpe_ratio":     round(sharpe,     6) if not np.isnan(sharpe)     else None,
                    "sortino_ratio":    round(sortino,    6) if not np.isnan(sortino)    else None,
                    "treynor_ratio":    round(treynor,    6) if not np.isnan(treynor)    else None,
                    "alpha":            round(alpha_v,    6) if not np.isnan(alpha_v)    else None,
                    "beta":             round(beta_v,     6) if not np.isnan(beta_v)     else None,
                    "r_squared":        round(r2,         6) if not np.isnan(r2)         else None,
                    "tracking_error":   round(te,         6) if not np.isnan(te)         else None,
                    "information_ratio":round(ir,         6) if not np.isnan(ir)         else None,
                    "skewness":         round(skew,       6) if not np.isnan(skew)       else None,
                    "kurtosis":         round(kurt,       6) if not np.isnan(kurt)       else None,
                    "risk_free_rate":   RISK_FREE_RATE,
                    "computed_at":      datetime.now().isoformat(),
                })

            if (i + 1) % 10 == 0:
                logger.info("  %d / %d funds processed", i + 1, len(funds))

        df_results = pd.DataFrame(results)
        logger.info("Computed %d metric records", len(df_results))
        return df_results

    def save(self, df: pd.DataFrame) -> None:
        """Save metrics to SQLite and CSV."""
        # ── SQLite ────────────────────────────────────────────────────────────
        with sqlite3.connect(self.db_path) as conn:
            for _, row in df.iterrows():
                conn.execute("""
                    INSERT OR REPLACE INTO performance_metrics
                        (scheme_code, as_of_date, period_label,
                         cagr, absolute_return, volatility_ann, max_drawdown,
                         sharpe_ratio, sortino_ratio, treynor_ratio,
                         alpha, beta, r_squared, tracking_error, information_ratio,
                         skewness, kurtosis, risk_free_rate, computed_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    int(row["scheme_code"]),
                    row["as_of_date"],
                    row["period_label"],
                    row.get("cagr"),
                    row.get("absolute_return"),
                    row.get("volatility_ann"),
                    row.get("max_drawdown"),
                    row.get("sharpe_ratio"),
                    row.get("sortino_ratio"),
                    row.get("treynor_ratio"),
                    row.get("alpha"),
                    row.get("beta"),
                    row.get("r_squared"),
                    row.get("tracking_error"),
                    row.get("information_ratio"),
                    row.get("skewness"),
                    row.get("kurtosis"),
                    row.get("risk_free_rate"),
                    row.get("computed_at"),
                ))
        logger.info("Saved %d rows to performance_metrics table", len(df))

        # ── CSV ───────────────────────────────────────────────────────────────
        csv_path = ANALYTICS_DIR / "performance_metrics.csv"
        df.to_csv(csv_path, index=False)
        logger.info("Saved: %s", csv_path)


# ─────────────────────────────────────────────────────────────────────────────
# VIEWS BUILDER (called after metrics are loaded)
# ─────────────────────────────────────────────────────────────────────────────

def create_views(db_path: Path = DB_PATH) -> None:
    """Create or replace analytical views used by D5 Power BI dashboard."""
    views = {
        "vw_executive_summary": """
            SELECT
                fm.scheme_code,
                fm.scheme_name,
                cm.category,
                cm.sub_category,
                fhm.amc_name,
                fm.risk_level,
                fm.benchmark,
                fm.expense_ratio,
                fm.fund_manager,
                fm.plan,
                ln.nav          AS current_nav,
                ln.date         AS nav_date,
                ln.daily_return,
                ln.week52_high,
                ln.week52_low,
                pm1.cagr            AS cagr_1y,
                pm3.cagr            AS cagr_3y,
                pm5.cagr            AS cagr_5y,
                pmi.cagr            AS cagr_inception,
                pm1.sharpe_ratio    AS sharpe_1y,
                pm1.sortino_ratio   AS sortino_1y,
                pm1.max_drawdown    AS max_drawdown_1y,
                pm1.volatility_ann  AS volatility_1y,
                pm1.alpha           AS alpha_1y,
                pm1.beta            AS beta_1y,
                pm1.r_squared       AS r_squared_1y,
                pm1.information_ratio AS info_ratio_1y
            FROM fund_master fm
            LEFT JOIN category_master  cm  ON fm.category_id = cm.category_id
            LEFT JOIN fund_house_master fhm ON fm.amc_id      = fhm.amc_id
            LEFT JOIN (
                SELECT nh.scheme_code, nh.nav, nh.date, nh.daily_return,
                       nh.week52_high, nh.week52_low
                FROM nav_history nh
                INNER JOIN (
                    SELECT scheme_code, MAX(date) md FROM nav_history GROUP BY scheme_code
                ) x ON nh.scheme_code=x.scheme_code AND nh.date=x.md
            ) ln  ON fm.scheme_code = ln.scheme_code
            LEFT JOIN performance_metrics pm1 ON fm.scheme_code=pm1.scheme_code AND pm1.period_label='1Y'
            LEFT JOIN performance_metrics pm3 ON fm.scheme_code=pm3.scheme_code AND pm3.period_label='3Y'
            LEFT JOIN performance_metrics pm5 ON fm.scheme_code=pm5.scheme_code AND pm5.period_label='5Y'
            LEFT JOIN performance_metrics pmi ON fm.scheme_code=pmi.scheme_code AND pmi.period_label='Inception'
        """,

        "vw_fund_performance": """
            SELECT
                nh.scheme_code,
                fm.scheme_name,
                cm.category,
                cm.sub_category,
                fhm.amc_name,
                fm.risk_level,
                fm.benchmark,
                nh.date,
                nh.nav,
                nh.daily_return,
                nh.log_return,
                nh.rolling_30d_vol,
                nh.rolling_90d_vol,
                nh.rolling_252d_vol,
                nh.week52_high,
                nh.week52_low,
                strftime('%Y',    nh.date) AS year,
                strftime('%m',    nh.date) AS month,
                strftime('%Y-%m', nh.date) AS year_month,
                CAST(strftime('%Y', nh.date) AS INTEGER) AS year_int,
                CAST(strftime('%m', nh.date) AS INTEGER) AS month_int
            FROM nav_history nh
            LEFT JOIN fund_master      fm  ON nh.scheme_code = fm.scheme_code
            LEFT JOIN category_master  cm  ON fm.category_id  = cm.category_id
            LEFT JOIN fund_house_master fhm ON fm.amc_id       = fhm.amc_id
        """,

        "vw_risk_dashboard": """
            SELECT
                fm.scheme_code,
                fm.scheme_name,
                cm.category,
                cm.sub_category,
                fhm.amc_name,
                fm.risk_level,
                rm.risk_order,
                pm.period_label,
                pm.volatility_ann,
                pm.max_drawdown,
                pm.sharpe_ratio,
                pm.sortino_ratio,
                pm.beta,
                pm.alpha,
                pm.skewness,
                pm.kurtosis,
                pm.tracking_error,
                pm.information_ratio
            FROM performance_metrics pm
            LEFT JOIN fund_master      fm  ON pm.scheme_code = fm.scheme_code
            LEFT JOIN category_master  cm  ON fm.category_id  = cm.category_id
            LEFT JOIN fund_house_master fhm ON fm.amc_id       = fhm.amc_id
            LEFT JOIN risk_master      rm  ON fm.risk_level    = rm.risk_level
        """,

        "vw_category_performance": """
            SELECT
                cm.category,
                cm.sub_category,
                pm.period_label,
                COUNT(*)                        AS fund_count,
                ROUND(AVG(pm.cagr)*100,    2)   AS avg_cagr_pct,
                ROUND(MAX(pm.cagr)*100,    2)   AS max_cagr_pct,
                ROUND(MIN(pm.cagr)*100,    2)   AS min_cagr_pct,
                ROUND(AVG(pm.sharpe_ratio),3)   AS avg_sharpe,
                ROUND(AVG(pm.volatility_ann)*100,2) AS avg_vol_pct,
                ROUND(AVG(pm.max_drawdown)*100,2)   AS avg_mdd_pct
            FROM performance_metrics pm
            LEFT JOIN fund_master     fm ON pm.scheme_code = fm.scheme_code
            LEFT JOIN category_master cm ON fm.category_id  = cm.category_id
            GROUP BY cm.category, cm.sub_category, pm.period_label
        """,

        "vw_amc_performance": """
            SELECT
                fhm.amc_name,
                pm.period_label,
                COUNT(*)                        AS fund_count,
                ROUND(AVG(pm.cagr)*100,    2)   AS avg_cagr_pct,
                ROUND(AVG(pm.sharpe_ratio),3)   AS avg_sharpe,
                ROUND(AVG(pm.volatility_ann)*100,2) AS avg_vol_pct
            FROM performance_metrics pm
            LEFT JOIN fund_master      fm  ON pm.scheme_code = fm.scheme_code
            LEFT JOIN fund_house_master fhm ON fm.amc_id      = fhm.amc_id
            GROUP BY fhm.amc_name, pm.period_label
        """,

        "vw_monthly_returns": """
            SELECT
                nh.scheme_code,
                fm.scheme_name,
                cm.category,
                cm.sub_category,
                fhm.amc_name,
                fm.risk_level,
                strftime('%Y',    nh.date) AS year,
                strftime('%m',    nh.date) AS month,
                strftime('%Y-%m', nh.date) AS year_month,
                ROUND(
                    (MAX(nh.nav) / MIN(nh.nav) - 1) * 100, 4
                ) AS monthly_return_pct
            FROM nav_history nh
            LEFT JOIN fund_master      fm  ON nh.scheme_code = fm.scheme_code
            LEFT JOIN category_master  cm  ON fm.category_id  = cm.category_id
            LEFT JOIN fund_house_master fhm ON fm.amc_id       = fhm.amc_id
            GROUP BY nh.scheme_code, strftime('%Y-%m', nh.date)
        """,
    }

    with sqlite3.connect(db_path) as conn:
        for vname, vdef in views.items():
            conn.execute(f"DROP VIEW IF EXISTS {vname}")
            conn.execute(f"CREATE VIEW {vname} AS {vdef}")
            logger.info("View created: %s", vname)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    logger.info("=" * 60)
    logger.info("METRICS ENGINE START  %s", datetime.now().isoformat())
    logger.info("=" * 60)

    engine = MetricsEngine()

    logger.info("Step 1/3: Computing metrics...")
    df = engine.run()

    logger.info("Step 2/3: Saving to DB + CSV...")
    engine.save(df)

    logger.info("Step 3/3: Creating analytical views...")
    create_views()

    # Quick summary
    with sqlite3.connect(DB_PATH) as conn:
        n = conn.execute("SELECT COUNT(*) FROM performance_metrics").fetchone()[0]
        sample = conn.execute("""
            SELECT fm.scheme_name, pm.period_label,
                   ROUND(pm.cagr*100,2) cagr_pct,
                   ROUND(pm.sharpe_ratio,3) sharpe,
                   ROUND(pm.max_drawdown*100,2) mdd_pct
            FROM performance_metrics pm
            JOIN fund_master fm ON pm.scheme_code=fm.scheme_code
            WHERE pm.period_label='1Y'
            ORDER BY pm.cagr DESC LIMIT 5
        """).fetchall()

    print("\n" + "=" * 60)
    print("METRICS SUMMARY")
    print("=" * 60)
    print(f"  Total metric records : {n:,}")
    print(f"  Funds × Periods      : {len(df['scheme_code'].unique())} × {len(PERIODS)}")
    print()
    print("  TOP 5 FUNDS by 1Y CAGR:")
    print(f"  {'Fund':42s} {'CAGR%':>7} {'Sharpe':>8} {'MDD%':>8}")
    print("  " + "-" * 68)
    for r in sample:
        print(f"  {r[0][:42]:42s} {r[2]:>7.2f} {r[3]:>8.3f} {r[4]:>8.2f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
