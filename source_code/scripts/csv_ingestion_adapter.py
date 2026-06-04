"""
csv_ingestion_adapter.py
========================
Bluestock Mutual Fund Analytics Capstone — CSV Dataset Ingestion Adapter

PURPOSE
-------
You have 10 CSV files with real data. This adapter:
  1. Auto-detects each CSV by its filename prefix (01_, 02_, etc.)
  2. Maps YOUR column names → the internal pipeline column names
  3. Runs the same Transform + Load stages as the live API pipeline
  4. Produces identical outputs (DB, processed CSVs, analytics_ready.csv)

So you drop your 10 CSVs into  datasets/raw/user_csvs/
and run:   python source_code/scripts/csv_ingestion_adapter.py
That's it. No manual editing. No per-file changes.

COLUMN MAPPING (your CSV → internal)
-------------------------------------
fund_master:
  amfi_code            → scheme_code
  fund_house           → amc_name
  scheme_name          → scheme_name
  category             → category
  sub_category         → sub_category
  plan                 → plan
  launch_date          → inception_date
  benchmark            → benchmark
  expense_ratio_pct    → expense_ratio
  exit_load_pct        → exit_load
  min_sip_amount       → min_sip_amount
  min_lumpsum_amount   → min_lumpsum_amount
  fund_manager         → fund_manager
  risk_category        → risk_level
  sebi_category_code   → sebi_category_code

nav_history:
  amfi_code  → scheme_code
  date       → date
  nav        → nav

Other CSVs (03–10) are auto-detected by filename keywords.

SUPPORTED FILENAME PATTERNS
----------------------------
  *fund_master*          → fund metadata
  *nav_history*          → NAV time-series
  *benchmark*            → benchmark index data
  *performance*          → pre-computed metrics
  *category*             → category reference
  *fund_house* | *amc*   → AMC reference
  *risk*                 → risk reference
  *returns*              → returns data
  *sip* | *portfolio*    → portfolio / SIP data
  *scheme*               → scheme data (treated as fund_master)

Author : Bluestock Capstone Team
Date   : 2025
"""

from __future__ import annotations

import logging
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parents[2]
USER_CSV_DIR  = BASE_DIR / "datasets" / "raw" / "user_csvs"
RAW_DIR       = BASE_DIR / "datasets" / "raw"
PROCESSED_DIR = BASE_DIR / "datasets" / "processed"
ANALYTICS_DIR = BASE_DIR / "datasets" / "analytics"
EXPORTS_DIR   = BASE_DIR / "datasets" / "exports"
DB_DIR        = BASE_DIR / "datasets" / "db"
LOG_DIR       = BASE_DIR / "logs"

for _d in (USER_CSV_DIR, PROCESSED_DIR, ANALYTICS_DIR, EXPORTS_DIR, DB_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

DB_PATH = DB_DIR / "bluestock_mf.db"

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "csv_ingestion.log"),
    ],
)
logger = logging.getLogger("csv_ingestion")


# ─────────────────────────────────────────────────────────────────────────────
# 1. COLUMN MAPS  (your columns → internal columns)
# ─────────────────────────────────────────────────────────────────────────────

# fund_master column map
FUND_MASTER_COL_MAP: dict[str, str] = {
    "amfi_code":           "scheme_code",
    "scheme_code":         "scheme_code",     # already correct
    "fund_house":          "amc_name",
    "amc_name":            "amc_name",
    "scheme_name":         "scheme_name",
    "category":            "category",
    "sub_category":        "sub_category",
    "subcategory":         "sub_category",
    "plan":                "plan",
    "launch_date":         "inception_date",
    "inception_date":      "inception_date",
    "benchmark":           "benchmark",
    "benchmark_index":     "benchmark",
    "expense_ratio_pct":   "expense_ratio",
    "expense_ratio":       "expense_ratio",
    "exit_load_pct":       "exit_load",
    "exit_load":           "exit_load",
    "min_sip_amount":      "min_sip_amount",
    "min_lumpsum_amount":  "min_lumpsum_amount",
    "fund_manager":        "fund_manager",
    "risk_category":       "risk_level",
    "risk_level":          "risk_level",
    "sebi_category_code":  "sebi_category_code",
}

# nav_history column map
NAV_COL_MAP: dict[str, str] = {
    "amfi_code":    "scheme_code",
    "scheme_code":  "scheme_code",
    "fund_code":    "scheme_code",
    "code":         "scheme_code",
    "date":         "date",
    "nav_date":     "date",
    "price_date":   "date",
    "nav":          "nav",
    "nav_value":    "nav",
    "price":        "nav",
    "close":        "nav",
}

# benchmark column map
BENCHMARK_COL_MAP: dict[str, str] = {
    "benchmark_name": "benchmark_name",
    "index_name":     "benchmark_name",
    "name":           "benchmark_name",
    "date":           "date",
    "index_value":    "index_value",
    "value":          "index_value",
    "close":          "index_value",
    "price":          "index_value",
}


# ─────────────────────────────────────────────────────────────────────────────
# 2. FILE TYPE DETECTOR
# ─────────────────────────────────────────────────────────────────────────────

FILE_TYPE_PATTERNS: list[tuple[str, str]] = [
    # (regex pattern on lowercased filename, file_type)
    (r"fund_master|scheme_master|fund_info|scheme_info|scheme$", "fund_master"),
    (r"nav_history|nav_data|daily_nav|nav$",                     "nav_history"),
    (r"benchmark|index_data|market_index",                       "benchmark"),
    (r"performance|metrics|returns_summary",                     "performance"),
    (r"category_master|category$",                               "category"),
    (r"fund_house|amc_master|amc$",                              "fund_house"),
    (r"risk_master|risk$",                                       "risk"),
    (r"monthly_returns|daily_returns|returns$",                  "returns"),
    (r"sip|portfolio|holding",                                   "portfolio"),
]


def detect_file_type(filepath: Path) -> str:
    """
    Auto-detect CSV type from filename.

    Returns one of: fund_master | nav_history | benchmark |
                    performance | category | fund_house | risk |
                    returns | portfolio | unknown
    """
    name = filepath.stem.lower()
    # Strip numeric prefix like "01_", "02_"
    name = re.sub(r"^\d+_", "", name)

    for pattern, ftype in FILE_TYPE_PATTERNS:
        if re.search(pattern, name):
            logger.info("  %-30s → detected as: %s", filepath.name, ftype)
            return ftype

    logger.warning("  %-30s → UNKNOWN type (will be skipped)", filepath.name)
    return "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# 3. COLUMN NORMALISER
# ─────────────────────────────────────────────────────────────────────────────

def normalise_columns(df: pd.DataFrame, col_map: dict[str, str]) -> pd.DataFrame:
    """
    Rename columns using col_map (case-insensitive, strip whitespace).
    Columns not in the map are kept as-is.
    """
    # Lowercase + strip all column names first
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    rename = {k: v for k, v in col_map.items() if k in df.columns}
    df = df.rename(columns=rename)
    logger.debug("  Column mapping applied: %s", rename)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 4. INDIVIDUAL FILE LOADERS
# ─────────────────────────────────────────────────────────────────────────────

class FundMasterLoader:
    """Loads and validates fund_master CSV into a clean DataFrame."""

    REQUIRED_COLS = {"scheme_code", "scheme_name", "category", "amc_name"}

    def load(self, filepath: Path) -> pd.DataFrame:
        logger.info("Loading fund_master: %s", filepath.name)
        df = pd.read_csv(filepath)
        df = normalise_columns(df, FUND_MASTER_COL_MAP)

        # Validate required columns
        missing = self.REQUIRED_COLS - set(df.columns)
        if missing:
            raise ValueError(f"fund_master missing required columns: {missing}")

        # Type coercions
        df["scheme_code"] = pd.to_numeric(df["scheme_code"], errors="coerce").astype("Int64")
        df = df.dropna(subset=["scheme_code"])

        # Add defaults for optional columns if missing
        defaults = {
            "sub_category":        "General",
            "risk_level":          "Moderate",
            "benchmark":           "Nifty 50 TRI",
            "plan":                "Regular",
            "inception_date":      None,
            "expense_ratio":       None,
            "exit_load":           None,
            "min_sip_amount":      500,
            "min_lumpsum_amount":  1000,
            "fund_manager":        None,
            "sebi_category_code":  None,
        }
        for col, default in defaults.items():
            if col not in df.columns:
                df[col] = default

        # Rename risk_level variations
        risk_map = {
            "moderately high": "Moderately High",
            "moderate":        "Moderate",
            "high":            "High",
            "very high":       "Very High",
            "low":             "Low",
            "moderately low":  "Moderately Low",
        }
        df["risk_level"] = (
            df["risk_level"].str.strip().str.lower()
            .map(risk_map)
            .fillna(df["risk_level"])
        )

        logger.info("  ✅ Loaded %d funds", len(df))
        return df


class NAVHistoryLoader:
    """Loads, validates, and enriches NAV history CSV."""

    REQUIRED_COLS = {"scheme_code", "date", "nav"}

    def load(self, filepath: Path) -> pd.DataFrame:
        logger.info("Loading nav_history: %s", filepath.name)
        df = pd.read_csv(filepath)
        df = normalise_columns(df, NAV_COL_MAP)

        missing = self.REQUIRED_COLS - set(df.columns)
        if missing:
            raise ValueError(f"nav_history missing required columns: {missing}")

        # Types
        df["scheme_code"] = pd.to_numeric(df["scheme_code"], errors="coerce").astype("Int64")
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["nav"]  = pd.to_numeric(df["nav"], errors="coerce")

        before = len(df)
        df = df.dropna(subset=["scheme_code", "date", "nav"])
        df = df[df["nav"] > 0]
        after = len(df)
        if before != after:
            logger.warning("  Dropped %d invalid rows", before - after)

        df = df.sort_values(["scheme_code", "date"]).reset_index(drop=True)
        logger.info("  ✅ Loaded %d NAV rows for %d funds",
                    len(df), df["scheme_code"].nunique())
        return df


class BenchmarkLoader:
    """Loads benchmark index CSV."""

    def load(self, filepath: Path) -> pd.DataFrame:
        logger.info("Loading benchmark: %s", filepath.name)
        df = pd.read_csv(filepath)
        df = normalise_columns(df, BENCHMARK_COL_MAP)

        if "benchmark_name" not in df.columns:
            # If no benchmark_name col, use filename as the benchmark name
            bench_name = filepath.stem.replace("_", " ").title()
            df["benchmark_name"] = bench_name
            logger.info("  Inferred benchmark name: %s", bench_name)

        df["date"]        = pd.to_datetime(df["date"], errors="coerce")
        df["index_value"] = pd.to_numeric(df["index_value"], errors="coerce")
        df = df.dropna(subset=["date", "index_value"])
        df = df[df["index_value"] > 0]

        logger.info("  ✅ Loaded %d benchmark rows", len(df))
        return df


# ─────────────────────────────────────────────────────────────────────────────
# 5. TRANSFORMER  (same logic as etl_pipeline.py, works on your real data)
# ─────────────────────────────────────────────────────────────────────────────

class RealDataTransformer:
    """
    Applies the full transformation pipeline to real NAV data.
    Identical transformations to DataTransformer in etl_pipeline.py.
    """

    def __init__(self, fund_meta: pd.DataFrame) -> None:
        self.fund_meta = fund_meta

    def transform(self, nav_df: pd.DataFrame) -> pd.DataFrame:
        """Transform one fund's NAV data. Returns enriched DataFrame."""
        df = nav_df.copy()
        df = df.drop_duplicates(subset=["scheme_code", "date"]).sort_values("date")

        # Reindex to business days, forward fill up to 3 days
        df = df.set_index("date")
        full_idx = pd.bdate_range(df.index.min(), df.index.max(), freq="B")
        df = df.reindex(full_idx)
        df["scheme_code"] = df["scheme_code"].ffill()
        df["nav"] = df["nav"].ffill(limit=3)
        df = df.dropna(subset=["nav"]).reset_index().rename(columns={"index": "date"})

        # Returns
        df["daily_return"] = df["nav"].pct_change()
        df["log_return"]   = np.log(df["nav"] / df["nav"].shift(1))

        # Outlier flag
        df["is_return_outlier"] = df["daily_return"].abs() > 0.30

        # Rolling volatility (annualised)
        df["rolling_30d_vol"]  = df["daily_return"].rolling(30,  min_periods=20).std() * np.sqrt(252)
        df["rolling_90d_vol"]  = df["daily_return"].rolling(90,  min_periods=60).std() * np.sqrt(252)
        df["rolling_252d_vol"] = df["daily_return"].rolling(252, min_periods=200).std() * np.sqrt(252)

        # 52-week high / low
        df["week52_high"] = df["nav"].rolling(252, min_periods=1).max()
        df["week52_low"]  = df["nav"].rolling(252, min_periods=1).min()

        # Calendar columns
        df["year"]       = df["date"].dt.year
        df["month"]      = df["date"].dt.month
        df["quarter"]    = df["date"].dt.quarter
        df["month_name"] = df["date"].dt.strftime("%b")

        # Merge fund metadata
        meta_cols = [
            "scheme_code", "scheme_name", "category", "sub_category",
            "amc_name", "benchmark", "risk_level",
        ]
        available = [c for c in meta_cols if c in self.fund_meta.columns]
        df = df.merge(
            self.fund_meta[available],
            on="scheme_code",
            how="left",
        )
        return df

    def transform_all(self, nav_df: pd.DataFrame) -> pd.DataFrame:
        """Transform all funds in one DataFrame. Returns combined result."""
        all_funds = []
        codes = nav_df["scheme_code"].unique()
        logger.info("Transforming %d funds...", len(codes))
        for i, code in enumerate(codes, 1):
            fund_nav = nav_df[nav_df["scheme_code"] == code].copy()
            try:
                transformed = self.transform(fund_nav)
                all_funds.append(transformed)
                if i % 10 == 0:
                    logger.info("  Transformed %d / %d funds", i, len(codes))
            except Exception as exc:
                logger.error("  Failed to transform scheme %s: %s", code, exc)
        return pd.concat(all_funds, ignore_index=True) if all_funds else pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# 6. DATABASE LOADER
# ─────────────────────────────────────────────────────────────────────────────

class DatabaseLoader:
    """Loads fund master and NAV history into SQLite (re-uses the schema from schema.sql)."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        schema_path = BASE_DIR / "source_code" / "sql" / "schema.sql"
        if schema_path.exists():
            with sqlite3.connect(self.db_path) as conn:
                conn.executescript(schema_path.read_text())
            logger.info("Schema initialised from schema.sql")
        else:
            logger.warning("schema.sql not found — DB tables may not exist")

    def load_fund_master(self, df: pd.DataFrame) -> int:
        """Upsert funds into fund_master, category_master, fund_house_master."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            for _, row in df.iterrows():
                cat  = str(row.get("category", "General"))
                sub  = str(row.get("sub_category", "General"))
                amc  = str(row.get("amc_name", "Unknown"))

                conn.execute(
                    "INSERT OR IGNORE INTO category_master (category, sub_category) VALUES (?,?)",
                    (cat, sub)
                )
                cat_id = conn.execute(
                    "SELECT category_id FROM category_master WHERE category=? AND sub_category=?",
                    (cat, sub)
                ).fetchone()[0]

                conn.execute(
                    "INSERT OR IGNORE INTO fund_house_master (amc_name) VALUES (?)", (amc,)
                )
                amc_id = conn.execute(
                    "SELECT amc_id FROM fund_house_master WHERE amc_name=?", (amc,)
                ).fetchone()[0]

                conn.execute("""
                    INSERT OR REPLACE INTO fund_master
                        (scheme_code, scheme_name, category_id, amc_id,
                         sub_category, benchmark, risk_level,
                         inception_date, expense_ratio, exit_load,
                         fund_manager, plan, min_sip_amount, min_lumpsum_amount,
                         sebi_category_code)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    int(row["scheme_code"]),
                    str(row.get("scheme_name", "")),
                    cat_id, amc_id,
                    sub,
                    str(row.get("benchmark", "")),
                    str(row.get("risk_level", "Moderate")),
                    str(row.get("inception_date", "")) or None,
                    float(row["expense_ratio"]) if pd.notna(row.get("expense_ratio")) else None,
                    str(row.get("exit_load", "")) or None,
                    str(row.get("fund_manager", "")) or None,
                    str(row.get("plan", "")) or None,
                    float(row["min_sip_amount"]) if pd.notna(row.get("min_sip_amount")) else None,
                    float(row["min_lumpsum_amount"]) if pd.notna(row.get("min_lumpsum_amount")) else None,
                    str(row.get("sebi_category_code", "")) or None,
                ))
        logger.info("fund_master: %d funds upserted", len(df))
        return len(df)

    def load_nav_history(self, df: pd.DataFrame) -> int:
        """Bulk insert processed NAV rows. Returns inserted count."""
        cols = [
            "scheme_code", "date", "nav", "daily_return", "log_return",
            "rolling_30d_vol", "rolling_90d_vol", "rolling_252d_vol",
            "week52_high", "week52_low", "is_return_outlier",
        ]
        df_sub = df[[c for c in cols if c in df.columns]].copy()
        df_sub["date"] = df_sub["date"].astype(str)
        if "is_return_outlier" in df_sub.columns:
            df_sub["is_return_outlier"] = df_sub["is_return_outlier"].astype(int)

        rows = [tuple(r) for r in df_sub.itertuples(index=False)]
        with sqlite3.connect(self.db_path) as conn:
            before = conn.execute("SELECT COUNT(*) FROM nav_history").fetchone()[0]
            conn.executemany(f"""
                INSERT OR IGNORE INTO nav_history
                    ({', '.join(df_sub.columns)})
                VALUES ({', '.join(['?'] * len(df_sub.columns))})
            """, rows)
            after  = conn.execute("SELECT COUNT(*) FROM nav_history").fetchone()[0]
        inserted = after - before
        logger.info("nav_history: %d new rows inserted", inserted)
        return inserted

    def load_benchmark(self, df: pd.DataFrame) -> int:
        """Insert benchmark NAV rows."""
        df_copy = df.copy()
        df_copy["date"] = df_copy["date"].astype(str)
        rows = [(str(r.benchmark_name), str(r.date), float(r.index_value))
                for r in df_copy.itertuples()]
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO benchmark_nav (benchmark_name, date, index_value) VALUES (?,?,?)",
                rows
            )
        logger.info("benchmark_nav: %d rows loaded", len(rows))
        return len(rows)


# ─────────────────────────────────────────────────────────────────────────────
# 7. MAIN ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────

class CSVIngestionPipeline:
    """
    Scans a folder for CSVs, auto-detects types, and runs the full
    Transform + Load pipeline on all of them.

    Usage
    -----
    Drop all 10 CSVs into:  datasets/raw/user_csvs/
    Then run:               python source_code/scripts/csv_ingestion_adapter.py
    """

    def __init__(self, csv_dir: Path = USER_CSV_DIR, db_path: Path = DB_PATH) -> None:
        self.csv_dir  = csv_dir
        self.db_path  = db_path
        self.db       = DatabaseLoader(db_path)

    def run(self) -> dict[str, Any]:
        logger.info("=" * 60)
        logger.info("CSV INGESTION PIPELINE START")
        logger.info("Scanning: %s", self.csv_dir)
        logger.info("=" * 60)

        # Discover all CSVs
        csv_files = sorted(self.csv_dir.glob("*.csv"))
        if not csv_files:
            logger.error("No CSV files found in %s", self.csv_dir)
            logger.error("Place your CSVs in: %s", self.csv_dir)
            return {"error": "no_files_found"}

        logger.info("Found %d CSV files:", len(csv_files))
        for f in csv_files:
            logger.info("  %s", f.name)

        # Categorise files
        typed: dict[str, list[Path]] = {}
        for f in csv_files:
            ftype = detect_file_type(f)
            typed.setdefault(ftype, []).append(f)

        stats: dict[str, Any] = {
            "files_found":    len(csv_files),
            "files_by_type":  {k: [f.name for f in v] for k, v in typed.items()},
            "funds_loaded":   0,
            "nav_rows":       0,
            "errors":         [],
        }

        # ── Step 1 : Fund master ─────────────────────────────────────────────
        fund_meta = pd.DataFrame()
        if "fund_master" in typed:
            fm_loader = FundMasterLoader()
            frames = []
            for f in typed["fund_master"]:
                try:
                    frames.append(fm_loader.load(f))
                except Exception as e:
                    stats["errors"].append(f"fund_master {f.name}: {e}")
                    logger.error("Failed: %s — %s", f.name, e)
            if frames:
                fund_meta = pd.concat(frames, ignore_index=True).drop_duplicates("scheme_code")
                self.db.load_fund_master(fund_meta)
                fund_meta.to_csv(PROCESSED_DIR / "fund_master_processed.csv", index=False)
                stats["funds_loaded"] = len(fund_meta)
                logger.info("Fund master: %d funds loaded", len(fund_meta))
        else:
            logger.warning("No fund_master CSV found — metadata will be minimal")

        # ── Step 2 : NAV History ─────────────────────────────────────────────
        if "nav_history" in typed:
            nav_loader  = NAVHistoryLoader()
            transformer = RealDataTransformer(fund_meta)
            nav_frames  = []

            for f in typed["nav_history"]:
                try:
                    raw_nav = nav_loader.load(f)
                    raw_nav.to_csv(RAW_DIR / f"nav_raw_{f.stem}.csv", index=False)
                    nav_frames.append(raw_nav)
                except Exception as e:
                    stats["errors"].append(f"nav_history {f.name}: {e}")
                    logger.error("Failed: %s — %s", f.name, e)

            if nav_frames:
                all_raw = pd.concat(nav_frames, ignore_index=True)
                logger.info("Total raw NAV rows: %d", len(all_raw))

                # Transform
                logger.info("Running transforms...")
                processed = transformer.transform_all(all_raw)

                # Save
                processed.to_csv(PROCESSED_DIR / "nav_all_funds.csv", index=False)
                processed.to_csv(EXPORTS_DIR   / "nav_all_funds_export.csv", index=False)

                # Analytics-ready subset
                analytics_cols = [
                    "scheme_code", "scheme_name", "date", "nav",
                    "category", "sub_category", "amc_name", "benchmark", "risk_level",
                    "daily_return", "log_return",
                    "rolling_30d_vol", "rolling_90d_vol", "rolling_252d_vol",
                    "week52_high", "week52_low",
                    "year", "month", "quarter", "month_name",
                ]
                analytics_df = processed[[c for c in analytics_cols if c in processed.columns]]
                analytics_df.to_csv(ANALYTICS_DIR / "analytics_ready.csv", index=False)

                # Load to DB
                nav_rows = self.db.load_nav_history(processed)
                stats["nav_rows"] = nav_rows
                logger.info("NAV history loaded: %d rows", nav_rows)

        # ── Step 3 : Benchmark ───────────────────────────────────────────────
        if "benchmark" in typed:
            bench_loader = BenchmarkLoader()
            for f in typed["benchmark"]:
                try:
                    bench_df = bench_loader.load(f)
                    self.db.load_benchmark(bench_df)
                    bench_df.to_csv(RAW_DIR / f"benchmark_{f.stem}.csv", index=False)
                except Exception as e:
                    stats["errors"].append(f"benchmark {f.name}: {e}")

        # ── Step 4 : Unknown files — report them ─────────────────────────────
        if "unknown" in typed:
            logger.warning("Unrecognised files (skipped):")
            for f in typed["unknown"]:
                logger.warning("  %s  →  rename it to match a known pattern", f.name)
                stats["errors"].append(f"unrecognised: {f.name}")

        # ── Summary ──────────────────────────────────────────────────────────
        logger.info("=" * 60)
        logger.info("CSV INGESTION COMPLETE")
        logger.info("  Funds loaded : %d", stats["funds_loaded"])
        logger.info("  NAV rows     : %d", stats["nav_rows"])
        logger.info("  Errors       : %d", len(stats["errors"]))
        logger.info("  DB           : %s", self.db_path)
        logger.info("=" * 60)
        return stats


# ─────────────────────────────────────────────────────────────────────────────
# 8. MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Bluestock CSV Ingestion Adapter — drop your CSVs and run"
    )
    parser.add_argument(
        "--csv-dir", type=Path, default=USER_CSV_DIR,
        help=f"Folder containing your CSVs (default: {USER_CSV_DIR})"
    )
    parser.add_argument(
        "--db", type=Path, default=DB_PATH,
        help=f"SQLite DB path (default: {DB_PATH})"
    )
    args = parser.parse_args()

    pipeline = CSVIngestionPipeline(csv_dir=args.csv_dir, db_path=args.db)
    stats    = pipeline.run()

    print("\n" + "=" * 50)
    print("INGESTION SUMMARY")
    print("=" * 50)
    print(f"  Files found  : {stats.get('files_found', 0)}")
    print(f"  Funds loaded : {stats.get('funds_loaded', 0)}")
    print(f"  NAV rows     : {stats.get('nav_rows', 0):,}")
    print(f"  Errors       : {len(stats.get('errors', []))}")
    if stats.get("errors"):
        print("\n  Errors:")
        for e in stats["errors"]:
            print(f"    ✗ {e}")
    print("\n  Files by type:")
    for ftype, files in stats.get("files_by_type", {}).items():
        for f in files:
            print(f"    {ftype:15s} ← {f}")
    print("=" * 50)


if __name__ == "__main__":
    main()
