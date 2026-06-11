"""
scheduler.py
============
Bluestock Mutual Fund Analytics Capstone — Automated ETL Scheduler (B1)

Schedules
---------
  Daily  06:30 IST  → live_nav_fetch.py   (incremental NAV update)
  Weekly Sunday 02:00 IST → etl_pipeline.py (full refresh)
  Weekly Sunday 02:30 IST → compute_metrics.py (recompute all metrics)

Run
---
    python source_code/scripts/scheduler.py

    # Or as a background service:
    nohup python source_code/scripts/scheduler.py &

Author : Bluestock Capstone Team
Date   : 2025
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

import schedule
import time

BASE_DIR = Path(__file__).resolve().parents[2]
LOG_DIR  = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "scheduler.log"),
    ],
)
logger = logging.getLogger("scheduler")

sys.path.insert(0, str(BASE_DIR / "source_code" / "scripts"))


def run_incremental_nav() -> None:
    """Daily job: fetch latest NAV for all funds."""
    logger.info("▶ JOB START: incremental NAV fetch")
    try:
        from live_nav_fetch import LiveNAVFetcher
        import sqlite3
        DB = BASE_DIR / "datasets" / "db" / "bluestock_mf.db"
        with sqlite3.connect(DB) as conn:
            codes = [r[0] for r in conn.execute("SELECT scheme_code FROM fund_master").fetchall()]
        fetcher = LiveNAVFetcher(DB)
        summary = fetcher.incremental_update(codes)
        logger.info("▶ JOB DONE: incremental NAV — %s", summary)
    except Exception as exc:
        logger.error("▶ JOB FAILED: incremental NAV — %s", exc, exc_info=True)


def run_full_etl() -> None:
    """Weekly job: full ETL pipeline."""
    logger.info("▶ JOB START: full ETL pipeline")
    try:
        from etl_pipeline import ETLPipeline, _probe_api
        use_synthetic = not _probe_api()
        pipeline = ETLPipeline(use_synthetic=use_synthetic)
        stats = pipeline.run()
        logger.info("▶ JOB DONE: full ETL — %s", stats)
    except Exception as exc:
        logger.error("▶ JOB FAILED: full ETL — %s", exc, exc_info=True)


def run_compute_metrics() -> None:
    """Weekly job: recompute all performance metrics."""
    logger.info("▶ JOB START: compute metrics")
    try:
        from compute_metrics import MetricsEngine, create_views
        engine = MetricsEngine()
        df = engine.run()
        engine.save(df)
        create_views()
        logger.info("▶ JOB DONE: metrics — %d records", len(df))
    except Exception as exc:
        logger.error("▶ JOB FAILED: compute metrics — %s", exc, exc_info=True)


def main() -> None:
    logger.info("=" * 55)
    logger.info("BLUESTOCK MF SCHEDULER STARTED")
    logger.info("  Daily  06:30 → incremental NAV fetch")
    logger.info("  Weekly Sun 02:00 → full ETL pipeline")
    logger.info("  Weekly Sun 02:30 → recompute metrics")
    logger.info("=" * 55)

    # Daily incremental NAV at 06:30 IST
    schedule.every().day.at("06:30").do(run_incremental_nav)

    # Weekly full ETL on Sunday at 02:00
    schedule.every().sunday.at("02:00").do(run_full_etl)

    # Weekly metrics recompute on Sunday at 02:30
    schedule.every().sunday.at("02:30").do(run_compute_metrics)

    # Run once immediately on startup
    logger.info("Running initial incremental NAV fetch...")
    run_incremental_nav()

    logger.info("Scheduler running. Press Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
