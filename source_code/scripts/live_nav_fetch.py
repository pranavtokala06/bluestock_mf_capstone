"""
live_nav_fetch.py
=================
Bluestock Mutual Fund Analytics Capstone — Live NAV Fetcher

Standalone script to fetch and update ONLY the latest NAV for all tracked
funds from mfapi.in.  Designed to be called by the scheduler (B1) or run
manually for intra-day refreshes without re-running the full ETL.

Features
--------
* Retry logic with exponential back-off
* Incremental updates — only inserts dates not already in the DB
* Writes a daily delta CSV to datasets/raw/live_nav_<date>.csv
* Thread-safe SQLite upsert

Author : Bluestock Capstone Team
Date   : 2025
"""

from __future__ import annotations

import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests

# ── Paths (relative to repo root) ────────────────────────────────────────────
BASE_DIR  = Path(__file__).resolve().parents[2]
RAW_DIR   = BASE_DIR / "datasets" / "raw"
DB_DIR    = BASE_DIR / "datasets" / "db"
LOG_DIR   = BASE_DIR / "logs"
for _d in (RAW_DIR, DB_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

DB_PATH = DB_DIR / "bluestock_mf.db"

# ── Config ───────────────────────────────────────────────────────────────────
MFAPI_BASE     = "https://api.mfapi.in/mf"
MAX_RETRIES    = 3
BACKOFF_FACTOR = 1.5        # seconds
MAX_WORKERS    = 4          # concurrent threads

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / f"live_nav_{datetime.now():%Y%m%d}.log"),
    ],
)
logger = logging.getLogger("live_nav_fetch")


# ─────────────────────────────────────────────────────────────────────────────
# FETCHER
# ─────────────────────────────────────────────────────────────────────────────

class LiveNAVFetcher:
    """Fetches latest NAV from mfapi.in with retry and incremental DB update."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "BluestockCapstone/1.0"})

    # ── Public ───────────────────────────────────────────────────────────────

    def fetch_latest_nav(self, scheme_code: int) -> dict[str, Any] | None:
        """
        Fetch the most recent NAV for a single scheme.

        Returns
        -------
        dict with keys: scheme_code, date, nav
        or None on failure.
        """
        url = f"{MFAPI_BASE}/{scheme_code}/latest"
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(url, timeout=10)
                resp.raise_for_status()
                payload = resp.json()
                data    = payload.get("data", [{}])[0]
                nav_date = datetime.strptime(data["date"], "%d-%m-%Y").date()
                return {
                    "scheme_code": scheme_code,
                    "date":        nav_date,
                    "nav":         float(data["nav"]),
                }
            except Exception as exc:
                wait = BACKOFF_FACTOR ** attempt
                logger.warning("Attempt %d/%d failed for %s: %s — retrying in %.1fs",
                               attempt, MAX_RETRIES, scheme_code, exc, wait)
                time.sleep(wait)
        logger.error("All retries exhausted for scheme %s", scheme_code)
        return None

    def fetch_all_latest(self, scheme_codes: list[int]) -> pd.DataFrame:
        """
        Fetch latest NAV for a list of scheme codes in parallel.

        Returns a DataFrame with columns: scheme_code, date, nav
        """
        results: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(self.fetch_latest_nav, sc): sc for sc in scheme_codes}
            for future in as_completed(futures):
                sc  = futures[future]
                res = future.result()
                if res:
                    results.append(res)
                else:
                    logger.warning("No result for scheme %s", sc)

        df = pd.DataFrame(results) if results else pd.DataFrame(
            columns=["scheme_code", "date", "nav"]
        )
        return df

    def incremental_update(self, scheme_codes: list[int]) -> dict[str, Any]:
        """
        Fetch latest NAVs and insert only new rows into the DB.

        Returns summary: {fetched, inserted, skipped, errors}
        """
        import sqlite3

        logger.info("Starting incremental NAV update for %d funds", len(scheme_codes))
        df = self.fetch_all_latest(scheme_codes)

        if df.empty:
            logger.warning("No NAV data fetched — aborting update")
            return {"fetched": 0, "inserted": 0, "skipped": 0, "errors": len(scheme_codes)}

        # Save daily delta CSV
        today = date.today().isoformat()
        delta_path = RAW_DIR / f"live_nav_{today}.csv"
        df.to_csv(delta_path, index=False)
        logger.info("Delta CSV saved: %s (%d rows)", delta_path.name, len(df))

        # Upsert to SQLite
        inserted = skipped = 0
        with sqlite3.connect(self.db_path) as conn:
            for _, row in df.iterrows():
                existing = conn.execute(
                    "SELECT 1 FROM nav_history WHERE scheme_code=? AND date=?",
                    (int(row["scheme_code"]), str(row["date"])),
                ).fetchone()
                if existing:
                    skipped += 1
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO nav_history (scheme_code, date, nav) VALUES (?,?,?)",
                    (int(row["scheme_code"]), str(row["date"]), float(row["nav"])),
                )
                inserted += 1

        summary = {
            "fetched":  len(df),
            "inserted": inserted,
            "skipped":  skipped,
            "errors":   len(scheme_codes) - len(df),
        }
        logger.info("Incremental update complete: %s", summary)
        return summary


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """Fetch latest NAV for all funds in the DB and update incrementally."""
    import sqlite3

    if not DB_PATH.exists():
        logger.error("Database not found at %s — run etl_pipeline.py first", DB_PATH)
        sys.exit(1)

    # Read all scheme codes from DB
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT scheme_code FROM fund_master").fetchall()
    scheme_codes = [r[0] for r in rows]
    logger.info("Found %d funds in DB", len(scheme_codes))

    fetcher = LiveNAVFetcher()
    summary = fetcher.incremental_update(scheme_codes)

    print("\n── Live NAV Fetch Summary ──")
    for k, v in summary.items():
        print(f"  {k:10s}: {v}")


if __name__ == "__main__":
    main()
