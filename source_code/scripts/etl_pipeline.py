"""
etl_pipeline.py
================
Bluestock Mutual Fund Analytics Capstone — D1 ETL Pipeline

Orchestrates the full Extract → Transform → Load workflow:
  1. Extract   : Fetches NAV data from mfapi.in (live) or falls back to
                 a realistic synthetic generator (offline / CI environments).
  2. Transform : Cleans, validates, enriches, and normalises the data.
  3. Load      : Writes raw CSVs, processed CSVs, and populates SQLite (D2).

Design Principles
-----------------
* Swap live ↔ synthetic via a single ENV variable:  MF_USE_SYNTHETIC=1
* All paths derived from BASE_DIR — zero hard-coding.
* Every stage emits a data-quality report to logs/.
* Output shapes are frozen contracts consumed by D3–D7.

Author : Bluestock Capstone Team
Date   : 2025
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

# ─────────────────────────────────────────────────────────────
# 0. PATHS & CONFIGURATION
# ─────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parents[2]          # repo root

RAW_DIR       = BASE_DIR / "datasets" / "raw"
PROCESSED_DIR = BASE_DIR / "datasets" / "processed"
ANALYTICS_DIR = BASE_DIR / "datasets" / "analytics"
EXPORTS_DIR   = BASE_DIR / "datasets" / "exports"
DB_DIR        = BASE_DIR / "datasets" / "db"
LOG_DIR       = BASE_DIR / "logs"

for _d in (RAW_DIR, PROCESSED_DIR, ANALYTICS_DIR, EXPORTS_DIR, DB_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

DB_PATH = DB_DIR / "bluestock_mf.db"

# API
MFAPI_BASE      = "https://api.mfapi.in/mf"
REQUEST_TIMEOUT = 15          # seconds per request
REQUEST_DELAY   = 0.25        # polite delay between requests (seconds)

# Synthetic fallback flag
USE_SYNTHETIC = os.environ.get("MF_USE_SYNTHETIC", "0") == "1"

# NAV history window
NAV_YEARS = 5                 # years of history to fetch / generate

# Funds to track — real AMFI scheme codes + metadata
# (scheme_code, scheme_name, category, sub_category, amc_name, benchmark)
FUND_UNIVERSE: list[dict[str, Any]] = [
    # ── Large Cap ────────────────────────────────────────────────────────────
    {"scheme_code": 120503, "scheme_name": "Mirae Asset Large Cap Fund - Regular Plan - Growth",
     "category": "Equity", "sub_category": "Large Cap", "amc_name": "Mirae Asset MF",
     "benchmark": "Nifty 100 TRI", "risk_level": "Moderate"},
    {"scheme_code": 100033, "scheme_name": "Axis Bluechip Fund - Regular Plan - Growth",
     "category": "Equity", "sub_category": "Large Cap", "amc_name": "Axis MF",
     "benchmark": "BSE 100 TRI", "risk_level": "Moderate"},
    {"scheme_code": 101206, "scheme_name": "HDFC Top 100 Fund - Regular Plan - Growth",
     "category": "Equity", "sub_category": "Large Cap", "amc_name": "HDFC MF",
     "benchmark": "Nifty 100 TRI", "risk_level": "Moderate"},
    # ── Mid Cap ──────────────────────────────────────────────────────────────
    {"scheme_code": 118989, "scheme_name": "Kotak Emerging Equity Fund - Regular Plan - Growth",
     "category": "Equity", "sub_category": "Mid Cap", "amc_name": "Kotak MF",
     "benchmark": "Nifty Midcap 150 TRI", "risk_level": "Moderately High"},
    {"scheme_code": 120465, "scheme_name": "Axis Midcap Fund - Regular Plan - Growth",
     "category": "Equity", "sub_category": "Mid Cap", "amc_name": "Axis MF",
     "benchmark": "Nifty Midcap 150 TRI", "risk_level": "Moderately High"},
    {"scheme_code": 100270, "scheme_name": "HDFC Mid-Cap Opportunities Fund - Regular Plan - Growth",
     "category": "Equity", "sub_category": "Mid Cap", "amc_name": "HDFC MF",
     "benchmark": "Nifty Midcap 150 TRI", "risk_level": "Moderately High"},
    # ── Small Cap ────────────────────────────────────────────────────────────
    {"scheme_code": 125497, "scheme_name": "Axis Small Cap Fund - Regular Plan - Growth",
     "category": "Equity", "sub_category": "Small Cap", "amc_name": "Axis MF",
     "benchmark": "Nifty Smallcap 250 TRI", "risk_level": "High"},
    {"scheme_code": 120828, "scheme_name": "SBI Small Cap Fund - Regular Plan - Growth",
     "category": "Equity", "sub_category": "Small Cap", "amc_name": "SBI MF",
     "benchmark": "Nifty Smallcap 250 TRI", "risk_level": "High"},
    # ── Flexi Cap ────────────────────────────────────────────────────────────
    {"scheme_code": 120586, "scheme_name": "Parag Parikh Flexi Cap Fund - Regular Plan - Growth",
     "category": "Equity", "sub_category": "Flexi Cap", "amc_name": "PPFAS MF",
     "benchmark": "Nifty 500 TRI", "risk_level": "Moderately High"},
    {"scheme_code": 100119, "scheme_name": "ICICI Prudential Flexicap Fund - Growth",
     "category": "Equity", "sub_category": "Flexi Cap", "amc_name": "ICICI Prudential MF",
     "benchmark": "Nifty 500 TRI", "risk_level": "Moderately High"},
    # ── ELSS ─────────────────────────────────────────────────────────────────
    {"scheme_code": 120503, "scheme_name": "Mirae Asset ELSS Tax Saver Fund - Regular Plan - Growth",
     "category": "Equity", "sub_category": "ELSS", "amc_name": "Mirae Asset MF",
     "benchmark": "Nifty 500 TRI", "risk_level": "Moderately High"},
    {"scheme_code": 100425, "scheme_name": "Axis Long Term Equity Fund - Regular Plan - Growth",
     "category": "Equity", "sub_category": "ELSS", "amc_name": "Axis MF",
     "benchmark": "Nifty 500 TRI", "risk_level": "Moderately High"},
    # ── Debt ─────────────────────────────────────────────────────────────────
    {"scheme_code": 119551, "scheme_name": "HDFC Short Term Debt Fund - Regular Plan - Growth",
     "category": "Debt", "sub_category": "Short Duration", "amc_name": "HDFC MF",
     "benchmark": "CRISIL Short Term Bond TRI", "risk_level": "Moderate"},
    {"scheme_code": 100024, "scheme_name": "ICICI Prudential Corporate Bond Fund - Growth",
     "category": "Debt", "sub_category": "Corporate Bond", "amc_name": "ICICI Prudential MF",
     "benchmark": "CRISIL Corporate Bond Composite TRI", "risk_level": "Moderate"},
    # ── Hybrid ───────────────────────────────────────────────────────────────
    {"scheme_code": 101539, "scheme_name": "HDFC Balanced Advantage Fund - Regular Plan - Growth",
     "category": "Hybrid", "sub_category": "Balanced Advantage", "amc_name": "HDFC MF",
     "benchmark": "Nifty 50 Hybrid Composite Debt 65:35 TRI", "risk_level": "Moderately High"},
    {"scheme_code": 118701, "scheme_name": "ICICI Prudential Equity & Debt Fund - Growth",
     "category": "Hybrid", "sub_category": "Aggressive Hybrid", "amc_name": "ICICI Prudential MF",
     "benchmark": "Nifty 50 Hybrid Composite Debt 65:35 TRI", "risk_level": "Moderately High"},
    # ── Index ─────────────────────────────────────────────────────────────────
    {"scheme_code": 120716, "scheme_name": "UTI Nifty Index Fund - Regular Plan - Growth",
     "category": "Index", "sub_category": "Large Cap Index", "amc_name": "UTI MF",
     "benchmark": "Nifty 50 TRI", "risk_level": "Moderate"},
    {"scheme_code": 120684, "scheme_name": "HDFC Index Fund - Nifty 50 Plan - Regular Plan",
     "category": "Index", "sub_category": "Large Cap Index", "amc_name": "HDFC MF",
     "benchmark": "Nifty 50 TRI", "risk_level": "Moderate"},
    # ── Liquid ────────────────────────────────────────────────────────────────
    {"scheme_code": 101305, "scheme_name": "Mirae Asset Cash Management Fund - Regular Plan - Growth",
     "category": "Debt", "sub_category": "Liquid", "amc_name": "Mirae Asset MF",
     "benchmark": "Nifty Liquid Index", "risk_level": "Low"},
    {"scheme_code": 100012, "scheme_name": "HDFC Liquid Fund - Regular Plan - Growth",
     "category": "Debt", "sub_category": "Liquid", "amc_name": "HDFC MF",
     "benchmark": "Nifty Liquid Index", "risk_level": "Low"},
]

# Deduplicate by scheme_code (some codes were reused for demo variety)
_seen: set[int] = set()
_unique: list[dict[str, Any]] = []
for _f in FUND_UNIVERSE:
    if _f["scheme_code"] not in _seen:
        _seen.add(_f["scheme_code"])
        _unique.append(_f)
FUND_UNIVERSE = _unique


# ─────────────────────────────────────────────────────────────
# 1. LOGGING
# ─────────────────────────────────────────────────────────────

def setup_logging(log_name: str = "etl_pipeline") -> logging.Logger:
    """Configure and return a named logger writing to file + console."""
    logger = logging.getLogger(log_name)
    logger.setLevel(logging.DEBUG)
    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # File handler
    fh = logging.FileHandler(LOG_DIR / f"{log_name}_{datetime.now():%Y%m%d}.log")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


logger = setup_logging()


# ─────────────────────────────────────────────────────────────
# 2. EXTRACT — LIVE (mfapi.in)
# ─────────────────────────────────────────────────────────────

class MFAPIExtractor:
    """Fetches mutual fund NAV history from https://api.mfapi.in."""

    def __init__(self, base_url: str = MFAPI_BASE, timeout: int = REQUEST_TIMEOUT) -> None:
        self.base_url = base_url
        self.timeout  = timeout
        self.session  = requests.Session()
        self.session.headers.update({"User-Agent": "BluestockCapstone/1.0"})

    # ── Public API ──────────────────────────────────────────────────────────

    def fetch_all_scheme_codes(self) -> pd.DataFrame:
        """Return DataFrame of all scheme codes available on mfapi.in."""
        url = self.base_url
        logger.info("Fetching all scheme codes from %s", url)
        resp = self._get(url)
        records = resp.json()
        df = pd.DataFrame(records)          # columns: schemeCode, schemeName
        df.columns = ["scheme_code", "scheme_name"]
        df["scheme_code"] = df["scheme_code"].astype(int)
        logger.info("Fetched %d scheme codes", len(df))
        return df

    def fetch_nav_history(self, scheme_code: int) -> pd.DataFrame | None:
        """
        Return full NAV history for one scheme as a tidy DataFrame.

        Columns: scheme_code, date, nav
        """
        url = f"{self.base_url}/{scheme_code}"
        logger.debug("Fetching NAV history for scheme_code=%s", scheme_code)
        try:
            resp = self._get(url)
            payload = resp.json()
            meta   = payload.get("meta", {})
            data   = payload.get("data", [])
            if not data:
                logger.warning("No NAV data returned for %s", scheme_code)
                return None

            df = pd.DataFrame(data)             # columns: date, nav
            df["scheme_code"] = scheme_code
            df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y", errors="coerce")
            df["nav"]  = pd.to_numeric(df["nav"], errors="coerce")
            df = df.dropna(subset=["date", "nav"]).sort_values("date").reset_index(drop=True)
            logger.debug("Scheme %s: %d NAV records (meta: %s)", scheme_code, len(df), meta)
            return df[["scheme_code", "date", "nav"]]

        except Exception as exc:
            logger.error("Failed to fetch scheme %s: %s", scheme_code, exc)
            return None

    # ── Private ─────────────────────────────────────────────────────────────

    def _get(self, url: str) -> requests.Response:
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp


# ─────────────────────────────────────────────────────────────
# 3. EXTRACT — SYNTHETIC FALLBACK
# ─────────────────────────────────────────────────────────────

# Category-level parameters  (annual_return_mean, annual_volatility, base_nav)
_CAT_PARAMS: dict[str, dict[str, float]] = {
    "Large Cap":          {"mu": 0.13, "sigma": 0.16, "nav0": 100.0},
    "Mid Cap":            {"mu": 0.17, "sigma": 0.22, "nav0":  50.0},
    "Small Cap":          {"mu": 0.20, "sigma": 0.28, "nav0":  30.0},
    "Flexi Cap":          {"mu": 0.15, "sigma": 0.18, "nav0":  80.0},
    "ELSS":               {"mu": 0.15, "sigma": 0.18, "nav0":  70.0},
    "Short Duration":     {"mu": 0.07, "sigma": 0.03, "nav0": 200.0},
    "Corporate Bond":     {"mu": 0.08, "sigma": 0.04, "nav0": 150.0},
    "Liquid":             {"mu": 0.05, "sigma": 0.005,"nav0": 1000.0},
    "Balanced Advantage": {"mu": 0.12, "sigma": 0.12, "nav0": 120.0},
    "Aggressive Hybrid":  {"mu": 0.14, "sigma": 0.14, "nav0":  90.0},
    "Large Cap Index":    {"mu": 0.12, "sigma": 0.15, "nav0": 140.0},
}


def _business_dates(years: int = NAV_YEARS) -> pd.DatetimeIndex:
    """Return business-day DatetimeIndex for the past `years` years."""
    end   = pd.Timestamp.today().normalize()
    start = end - pd.DateOffset(years=years)
    return pd.bdate_range(start=start, end=end, freq="B")


def generate_synthetic_nav(fund: dict[str, Any], seed: int | None = None) -> pd.DataFrame:
    """
    Generate realistic NAV history using Geometric Brownian Motion (GBM).

    GBM formula:  S(t+dt) = S(t) * exp((mu - 0.5*sigma^2)*dt + sigma*sqrt(dt)*Z)
    where Z ~ N(0,1).

    Parameters
    ----------
    fund : dict   One row from FUND_UNIVERSE.
    seed : int    RNG seed for reproducibility.

    Returns
    -------
    DataFrame with columns: scheme_code, date, nav
    """
    params = _CAT_PARAMS.get(fund["sub_category"], {"mu": 0.12, "sigma": 0.15, "nav0": 100.0})
    mu     = params["mu"]
    sigma  = params["sigma"]
    nav0   = params["nav0"]

    dates = _business_dates()
    n     = len(dates)
    dt    = 1 / 252                        # one trading day

    rng = np.random.default_rng(seed or fund["scheme_code"])
    Z   = rng.standard_normal(n)
    log_returns = (mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * Z
    nav_series  = nav0 * np.exp(np.cumsum(log_returns))

    return pd.DataFrame({
        "scheme_code": fund["scheme_code"],
        "date":        dates,
        "nav":         np.round(nav_series, 4),
    })


def generate_benchmark_nav(benchmark_name: str, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic benchmark index series (e.g. Nifty 50 TRI)."""
    bench_params: dict[str, dict[str, float]] = {
        "Nifty 50 TRI":                          {"mu": 0.12, "sigma": 0.14, "nav0": 10000},
        "Nifty 100 TRI":                         {"mu": 0.12, "sigma": 0.15, "nav0": 10000},
        "Nifty Midcap 150 TRI":                  {"mu": 0.16, "sigma": 0.21, "nav0": 10000},
        "Nifty Smallcap 250 TRI":                {"mu": 0.18, "sigma": 0.26, "nav0": 10000},
        "Nifty 500 TRI":                         {"mu": 0.13, "sigma": 0.16, "nav0": 10000},
        "BSE 100 TRI":                           {"mu": 0.12, "sigma": 0.15, "nav0": 10000},
        "Nifty Liquid Index":                    {"mu": 0.05, "sigma": 0.003,"nav0": 4000},
        "CRISIL Short Term Bond TRI":            {"mu": 0.07, "sigma": 0.025,"nav0": 3000},
        "CRISIL Corporate Bond Composite TRI":   {"mu": 0.08, "sigma": 0.035,"nav0": 3500},
        "Nifty 50 Hybrid Composite Debt 65:35 TRI": {"mu": 0.10, "sigma": 0.10,"nav0": 5000},
    }
    p   = bench_params.get(benchmark_name, {"mu": 0.12, "sigma": 0.15, "nav0": 10000})
    dates = _business_dates()
    n   = len(dates)
    dt  = 1 / 252
    rng = np.random.default_rng(seed)
    Z   = rng.standard_normal(n)
    log_returns = (p["mu"] - 0.5 * p["sigma"] ** 2) * dt + p["sigma"] * np.sqrt(dt) * Z
    idx_series  = p["nav0"] * np.exp(np.cumsum(log_returns))
    return pd.DataFrame({
        "benchmark_name": benchmark_name,
        "date":           dates,
        "index_value":    np.round(idx_series, 4),
    })


class SyntheticExtractor:
    """Generates offline NAV data using GBM — mirrors MFAPIExtractor interface."""

    def fetch_nav_history(self, fund: dict[str, Any]) -> pd.DataFrame:
        logger.debug("Generating synthetic NAV for scheme_code=%s", fund["scheme_code"])
        return generate_synthetic_nav(fund)


# ─────────────────────────────────────────────────────────────
# 4. TRANSFORM
# ─────────────────────────────────────────────────────────────

class DataTransformer:
    """
    Cleans, validates, and enriches raw NAV DataFrames.

    Transformations applied
    -----------------------
    T1  Deduplicate by (scheme_code, date)
    T2  Remove rows with NAV <= 0
    T3  Fill isolated missing dates with forward fill (max 3 days)
    T4  Cap outlier daily returns at ±30% (data quality flag)
    T5  Add daily_return, log_return columns
    T6  Add rolling_30d_vol, rolling_90d_vol, rolling_252d_vol
    T7  Add 52-week high / low
    T8  Add month, year, quarter columns
    T9  Merge fund metadata (category, AMC, benchmark, risk)
    """

    def __init__(self, fund_meta: pd.DataFrame) -> None:
        self.fund_meta = fund_meta          # scheme_code → metadata

    def transform(self, raw_nav: pd.DataFrame) -> pd.DataFrame:
        """Full transformation pipeline for one fund's NAV DataFrame."""
        df = raw_nav.copy()

        # T1 – dedup
        df = df.drop_duplicates(subset=["scheme_code", "date"]).sort_values("date")

        # T2 – non-positive NAV
        before = len(df)
        df = df[df["nav"] > 0]
        if len(df) < before:
            logger.warning("Removed %d non-positive NAV rows", before - len(df))

        # T3 – reindex to business days, ffill up to 3
        df = df.set_index("date")
        full_idx = pd.bdate_range(df.index.min(), df.index.max(), freq="B")
        df = df.reindex(full_idx)
        df["scheme_code"] = df["scheme_code"].ffill()
        df["nav"] = df["nav"].ffill(limit=3)
        df = df.dropna(subset=["nav"]).reset_index().rename(columns={"index": "date"})

        # T4 – outlier cap (flag column)
        df["daily_return"] = df["nav"].pct_change()
        df["is_return_outlier"] = df["daily_return"].abs() > 0.30
        n_outliers = df["is_return_outlier"].sum()
        if n_outliers:
            logger.warning("Flagged %d outlier daily-return rows (>30%%)", n_outliers)

        # T5 – returns
        df["log_return"] = np.log(df["nav"] / df["nav"].shift(1))

        # T6 – rolling volatility (annualised)
        df["rolling_30d_vol"]  = df["daily_return"].rolling(30,  min_periods=20).std() * np.sqrt(252)
        df["rolling_90d_vol"]  = df["daily_return"].rolling(90,  min_periods=60).std() * np.sqrt(252)
        df["rolling_252d_vol"] = df["daily_return"].rolling(252, min_periods=200).std() * np.sqrt(252)

        # T7 – 52-week high / low
        df["week52_high"] = df["nav"].rolling(252, min_periods=1).max()
        df["week52_low"]  = df["nav"].rolling(252, min_periods=1).min()

        # T8 – calendar
        df["year"]    = df["date"].dt.year
        df["month"]   = df["date"].dt.month
        df["quarter"] = df["date"].dt.quarter
        df["month_name"] = df["date"].dt.strftime("%b")

        # T9 – metadata merge
        meta_cols = ["scheme_code", "scheme_name", "category", "sub_category",
                     "amc_name", "benchmark", "risk_level"]
        df = df.merge(
            self.fund_meta[meta_cols],
            on="scheme_code",
            how="left",
        )

        return df

    @staticmethod
    def quality_report(df: pd.DataFrame, fund_name: str) -> dict[str, Any]:
        """Return a dict summarising data quality metrics."""
        return {
            "fund_name":          fund_name,
            "total_rows":         len(df),
            "date_min":           str(df["date"].min().date()),
            "date_max":           str(df["date"].max().date()),
            "nav_min":            round(float(df["nav"].min()), 4),
            "nav_max":            round(float(df["nav"].max()), 4),
            "null_nav_count":     int(df["nav"].isna().sum()),
            "null_return_count":  int(df["daily_return"].isna().sum()),
            "outlier_count":      int(df["is_return_outlier"].sum()),
            "missing_dates_pct":  round(df["nav"].isna().mean() * 100, 2),
        }


# ─────────────────────────────────────────────────────────────
# 5. LOAD — CSV
# ─────────────────────────────────────────────────────────────

class CSVLoader:
    """Writes raw and processed CSVs to the datasets/ hierarchy."""

    @staticmethod
    def save_raw(df: pd.DataFrame, scheme_code: int) -> Path:
        path = RAW_DIR / f"nav_raw_{scheme_code}.csv"
        df.to_csv(path, index=False)
        logger.debug("Raw CSV saved: %s (%d rows)", path.name, len(df))
        return path

    @staticmethod
    def save_processed(df: pd.DataFrame, scheme_code: int) -> Path:
        path = PROCESSED_DIR / f"nav_processed_{scheme_code}.csv"
        df.to_csv(path, index=False)
        logger.debug("Processed CSV saved: %s (%d rows)", path.name, len(df))
        return path

    @staticmethod
    def save_combined(df: pd.DataFrame, name: str, folder: Path) -> Path:
        path = folder / f"{name}.csv"
        df.to_csv(path, index=False)
        logger.info("Combined CSV saved: %s (%d rows, %d cols)", path.name, len(df), len(df.columns))
        return path


# ─────────────────────────────────────────────────────────────
# 6. LOAD — SQLITE  (D2 foundation)
# ─────────────────────────────────────────────────────────────

class SQLiteLoader:
    """
    Loads transformed data into SQLite.

    Tables created / updated
    ------------------------
    fund_master        — one row per fund (metadata)
    nav_history        — full daily NAV time-series
    category_master    — distinct categories
    fund_house_master  — distinct AMCs
    benchmark_nav      — benchmark index time-series
    etl_run_log        — audit log of every ETL execution
    """

    CREATE_STATEMENTS = {
        "category_master": """
            CREATE TABLE IF NOT EXISTS category_master (
                category_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                category      TEXT NOT NULL,
                sub_category  TEXT NOT NULL,
                UNIQUE (category, sub_category)
            )""",
        "fund_house_master": """
            CREATE TABLE IF NOT EXISTS fund_house_master (
                amc_id    INTEGER PRIMARY KEY AUTOINCREMENT,
                amc_name  TEXT NOT NULL UNIQUE
            )""",
        "fund_master": """
            CREATE TABLE IF NOT EXISTS fund_master (
                scheme_code   INTEGER PRIMARY KEY,
                scheme_name   TEXT    NOT NULL,
                category_id   INTEGER REFERENCES category_master(category_id),
                amc_id        INTEGER REFERENCES fund_house_master(amc_id),
                sub_category  TEXT,
                benchmark     TEXT,
                risk_level    TEXT,
                inception_date TEXT,
                created_at    TEXT DEFAULT (datetime('now'))
            )""",
        "nav_history": """
            CREATE TABLE IF NOT EXISTS nav_history (
                nav_id         INTEGER PRIMARY KEY AUTOINCREMENT,
                scheme_code    INTEGER NOT NULL REFERENCES fund_master(scheme_code),
                date           TEXT    NOT NULL,
                nav            REAL    NOT NULL,
                daily_return   REAL,
                log_return     REAL,
                rolling_30d_vol  REAL,
                rolling_90d_vol  REAL,
                rolling_252d_vol REAL,
                week52_high    REAL,
                week52_low     REAL,
                is_return_outlier INTEGER DEFAULT 0,
                UNIQUE (scheme_code, date)
            )""",
        "benchmark_nav": """
            CREATE TABLE IF NOT EXISTS benchmark_nav (
                bench_id        INTEGER PRIMARY KEY AUTOINCREMENT,
                benchmark_name  TEXT NOT NULL,
                date            TEXT NOT NULL,
                index_value     REAL NOT NULL,
                UNIQUE (benchmark_name, date)
            )""",
        "etl_run_log": """
            CREATE TABLE IF NOT EXISTS etl_run_log (
                run_id         INTEGER PRIMARY KEY AUTOINCREMENT,
                run_timestamp  TEXT DEFAULT (datetime('now')),
                source         TEXT,
                funds_loaded   INTEGER,
                total_nav_rows INTEGER,
                status         TEXT,
                notes          TEXT
            )""",
    }

    INDEX_STATEMENTS = [
        "CREATE INDEX IF NOT EXISTS idx_nav_scheme_date ON nav_history (scheme_code, date)",
        "CREATE INDEX IF NOT EXISTS idx_nav_date ON nav_history (date)",
        "CREATE INDEX IF NOT EXISTS idx_bench_name_date ON benchmark_nav (benchmark_name, date)",
        "CREATE INDEX IF NOT EXISTS idx_fund_category ON fund_master (category_id)",
    ]

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._init_schema()

    # ── Schema ──────────────────────────────────────────────────────────────

    def _init_schema(self) -> None:
        with self._conn() as conn:
            for stmt in self.CREATE_STATEMENTS.values():
                conn.execute(stmt)
            for idx in self.INDEX_STATEMENTS:
                conn.execute(idx)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
        logger.info("SQLite schema initialised: %s", self.db_path)

    # ── Loaders ─────────────────────────────────────────────────────────────

    def load_fund_master(self, fund_meta: pd.DataFrame) -> None:
        """Upsert all funds into fund_master, category_master, fund_house_master."""
        with self._conn() as conn:
            for _, row in fund_meta.iterrows():
                # category_master
                conn.execute(
                    "INSERT OR IGNORE INTO category_master (category, sub_category) VALUES (?,?)",
                    (row["category"], row["sub_category"]),
                )
                cat_id = conn.execute(
                    "SELECT category_id FROM category_master WHERE category=? AND sub_category=?",
                    (row["category"], row["sub_category"]),
                ).fetchone()[0]

                # fund_house_master
                conn.execute(
                    "INSERT OR IGNORE INTO fund_house_master (amc_name) VALUES (?)",
                    (row["amc_name"],),
                )
                amc_id = conn.execute(
                    "SELECT amc_id FROM fund_house_master WHERE amc_name=?",
                    (row["amc_name"],),
                ).fetchone()[0]

                # fund_master
                conn.execute("""
                    INSERT OR REPLACE INTO fund_master
                        (scheme_code, scheme_name, category_id, amc_id,
                         sub_category, benchmark, risk_level)
                    VALUES (?,?,?,?,?,?,?)
                """, (
                    int(row["scheme_code"]), row["scheme_name"],
                    cat_id, amc_id,
                    row["sub_category"], row["benchmark"], row["risk_level"],
                ))
        logger.info("fund_master loaded: %d funds", len(fund_meta))

    def load_nav_history(self, df: pd.DataFrame) -> int:
        """
        Bulk insert NAV rows into nav_history using INSERT OR IGNORE.
        Returns number of new rows inserted.
        """
        cols = [
            "scheme_code", "date", "nav", "daily_return", "log_return",
            "rolling_30d_vol", "rolling_90d_vol", "rolling_252d_vol",
            "week52_high", "week52_low", "is_return_outlier",
        ]
        df_sub = df[cols].copy()
        df_sub["date"] = df_sub["date"].astype(str)
        df_sub["is_return_outlier"] = df_sub["is_return_outlier"].astype(int)

        rows = [tuple(r) for r in df_sub.itertuples(index=False)]
        with self._conn() as conn:
            before = conn.execute("SELECT COUNT(*) FROM nav_history WHERE scheme_code=?",
                                  (int(df_sub["scheme_code"].iloc[0]),)).fetchone()[0]
            conn.executemany("""
                INSERT OR IGNORE INTO nav_history
                    (scheme_code, date, nav, daily_return, log_return,
                     rolling_30d_vol, rolling_90d_vol, rolling_252d_vol,
                     week52_high, week52_low, is_return_outlier)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, rows)
            after = conn.execute("SELECT COUNT(*) FROM nav_history WHERE scheme_code=?",
                                 (int(df_sub["scheme_code"].iloc[0]),)).fetchone()[0]
            inserted = after - before
        logger.debug("nav_history: %d rows inserted for scheme %s",
                     inserted, df_sub["scheme_code"].iloc[0])
        return inserted

    def load_benchmark_nav(self, df: pd.DataFrame) -> None:
        """Insert benchmark index series into benchmark_nav."""
        df_copy = df.copy()
        df_copy["date"] = df_copy["date"].astype(str)
        rows = [tuple(r) for r in df_copy.itertuples(index=False)]
        with self._conn() as conn:
            conn.executemany("""
                INSERT OR IGNORE INTO benchmark_nav (benchmark_name, date, index_value)
                VALUES (?,?,?)
            """, rows)
        logger.info("benchmark_nav loaded: %d rows for %s",
                    len(df_copy), df_copy["benchmark_name"].iloc[0])

    def log_run(self, source: str, funds_loaded: int,
                total_nav_rows: int, status: str, notes: str = "") -> None:
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO etl_run_log (source, funds_loaded, total_nav_rows, status, notes)
                VALUES (?,?,?,?,?)
            """, (source, funds_loaded, total_nav_rows, status, notes))

    # ── Private ─────────────────────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)


# ─────────────────────────────────────────────────────────────
# 7. ORCHESTRATOR
# ─────────────────────────────────────────────────────────────

class ETLPipeline:
    """
    Top-level orchestrator.  Calls Extract → Transform → Load in order.
    """

    def __init__(self, use_synthetic: bool = USE_SYNTHETIC) -> None:
        self.use_synthetic = use_synthetic
        self.fund_meta     = pd.DataFrame(FUND_UNIVERSE)
        self.transformer   = DataTransformer(self.fund_meta)
        self.csv_loader    = CSVLoader()
        self.db_loader     = SQLiteLoader()
        self.live_extractor: MFAPIExtractor | None = None
        if not use_synthetic:
            self.live_extractor = MFAPIExtractor()

        source_label = "synthetic" if use_synthetic else "mfapi.in"
        logger.info("ETL Pipeline initialised  [source=%s, funds=%d]",
                    source_label, len(FUND_UNIVERSE))

    # ── Main entry point ────────────────────────────────────────────────────

    def run(self) -> dict[str, Any]:
        """Execute the full ETL pipeline.  Returns summary statistics."""
        logger.info("=" * 60)
        logger.info("ETL PIPELINE START  %s", datetime.now().isoformat())
        logger.info("=" * 60)

        run_stats = {
            "start_time":    datetime.now().isoformat(),
            "source":        "synthetic" if self.use_synthetic else "mfapi.in",
            "funds_attempted": 0,
            "funds_loaded":    0,
            "total_nav_rows":  0,
            "quality_reports": [],
            "errors":          [],
        }

        # ── Step 1 : Fund master ─────────────────────────────────────────────
        self.db_loader.load_fund_master(self.fund_meta)

        # ── Step 2 : Benchmarks ──────────────────────────────────────────────
        unique_benchmarks = self.fund_meta["benchmark"].unique()
        logger.info("Loading %d benchmark series", len(unique_benchmarks))
        bench_frames: list[pd.DataFrame] = []
        for bname in unique_benchmarks:
            b_df = generate_benchmark_nav(bname)
            bench_frames.append(b_df)
            self.db_loader.load_benchmark_nav(b_df)
        if bench_frames:
            combined_bench = pd.concat(bench_frames, ignore_index=True)
            self.csv_loader.save_combined(combined_bench, "benchmark_nav", RAW_DIR)

        # ── Step 3 : NAV history per fund ────────────────────────────────────
        all_processed: list[pd.DataFrame] = []

        for fund in FUND_UNIVERSE:
            run_stats["funds_attempted"] += 1
            sc = fund["scheme_code"]
            name = fund["scheme_name"][:50]
            logger.info("[%d/%d] Processing: %s (%s)",
                        run_stats["funds_attempted"], len(FUND_UNIVERSE), name, sc)

            raw_df = self._extract(fund)
            if raw_df is None or raw_df.empty:
                run_stats["errors"].append(f"No data: {sc}")
                logger.warning("Skipping %s — no raw data", sc)
                continue

            # Save raw
            self.csv_loader.save_raw(raw_df, sc)

            # Transform
            try:
                processed_df = self.transformer.transform(raw_df)
            except Exception as exc:
                run_stats["errors"].append(f"Transform error {sc}: {exc}")
                logger.error("Transform failed for %s: %s", sc, exc, exc_info=True)
                continue

            # Quality report
            qr = self.transformer.quality_report(processed_df, name)
            run_stats["quality_reports"].append(qr)

            # Save processed
            self.csv_loader.save_processed(processed_df, sc)
            all_processed.append(processed_df)

            # Load to DB
            rows_inserted = self.db_loader.load_nav_history(processed_df)
            run_stats["funds_loaded"]   += 1
            run_stats["total_nav_rows"] += rows_inserted

            if not self.use_synthetic:
                time.sleep(REQUEST_DELAY)   # polite delay for live API

        # ── Step 4 : Combined datasets ───────────────────────────────────────
        if all_processed:
            combined = pd.concat(all_processed, ignore_index=True)
            self.csv_loader.save_combined(combined, "nav_all_funds",      PROCESSED_DIR)
            self.csv_loader.save_combined(combined, "nav_all_funds_export", EXPORTS_DIR)

            # Analytics-ready: only the columns needed by D3/D4/D5/D6
            analytics_cols = [
                "scheme_code", "scheme_name", "date", "nav",
                "category", "sub_category", "amc_name", "benchmark", "risk_level",
                "daily_return", "log_return",
                "rolling_30d_vol", "rolling_90d_vol", "rolling_252d_vol",
                "week52_high", "week52_low",
                "year", "month", "quarter", "month_name",
            ]
            analytics_df = combined[[c for c in analytics_cols if c in combined.columns]]
            self.csv_loader.save_combined(analytics_df, "analytics_ready", ANALYTICS_DIR)

        # ── Step 5 : Quality report JSON ─────────────────────────────────────
        qr_path = LOG_DIR / f"quality_report_{datetime.now():%Y%m%d_%H%M%S}.json"
        with open(qr_path, "w") as f:
            json.dump(run_stats["quality_reports"], f, indent=2)
        logger.info("Quality report saved: %s", qr_path.name)

        # ── Step 6 : DB audit log ────────────────────────────────────────────
        self.db_loader.log_run(
            source         = run_stats["source"],
            funds_loaded   = run_stats["funds_loaded"],
            total_nav_rows = run_stats["total_nav_rows"],
            status         = "SUCCESS" if not run_stats["errors"] else "PARTIAL",
            notes          = "; ".join(run_stats["errors"][:5]),
        )

        run_stats["end_time"] = datetime.now().isoformat()
        logger.info("=" * 60)
        logger.info("ETL PIPELINE COMPLETE")
        logger.info("  Funds loaded   : %d / %d", run_stats["funds_loaded"], run_stats["funds_attempted"])
        logger.info("  NAV rows loaded: %d", run_stats["total_nav_rows"])
        logger.info("  Errors         : %d", len(run_stats["errors"]))
        logger.info("=" * 60)
        return run_stats

    # ── Private ─────────────────────────────────────────────────────────────

    def _extract(self, fund: dict[str, Any]) -> pd.DataFrame | None:
        if self.use_synthetic:
            ext = SyntheticExtractor()
            return ext.fetch_nav_history(fund)
        else:
            assert self.live_extractor is not None
            return self.live_extractor.fetch_nav_history(fund["scheme_code"])


# ─────────────────────────────────────────────────────────────
# 8. MAIN
# ─────────────────────────────────────────────────────────────

def main() -> None:
    """Entry point — auto-selects live vs synthetic based on API availability."""
    import argparse
    parser = argparse.ArgumentParser(description="Bluestock MF ETL Pipeline")
    parser.add_argument("--synthetic", action="store_true",
                        help="Force synthetic data (offline mode)")
    parser.add_argument("--live", action="store_true",
                        help="Force live API fetch from mfapi.in")
    args = parser.parse_args()

    if args.synthetic:
        use_synthetic = True
    elif args.live:
        use_synthetic = False
    else:
        # Auto-detect: probe API
        use_synthetic = not _probe_api()

    logger.info("Mode: %s", "SYNTHETIC" if use_synthetic else "LIVE API")
    pipeline = ETLPipeline(use_synthetic=use_synthetic)
    stats = pipeline.run()

    print("\n" + "=" * 50)
    print("ETL SUMMARY")
    print("=" * 50)
    print(f"  Source        : {stats['source']}")
    print(f"  Funds loaded  : {stats['funds_loaded']}")
    print(f"  NAV rows      : {stats['total_nav_rows']:,}")
    print(f"  Errors        : {len(stats['errors'])}")
    print(f"  DB path       : {DB_PATH}")
    print(f"  Processed dir : {PROCESSED_DIR}")
    print("=" * 50)


def _probe_api(timeout: int = 5) -> bool:
    """Return True if mfapi.in is reachable."""
    try:
        r = requests.get(f"{MFAPI_BASE}/100033", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


if __name__ == "__main__":
    main()
