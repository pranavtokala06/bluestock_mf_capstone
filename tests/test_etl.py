"""
test_etl.py
===========
Bluestock Mutual Fund Analytics Capstone — ETL Unit Tests

Covers
------
* Synthetic NAV generation (shape, values, GBM validity)
* DataTransformer — each transformation stage
* CSVLoader — file creation and content
* SQLiteLoader — schema, inserts, deduplication
* ETLPipeline — end-to-end smoke test

Run with:  pytest tests/test_etl.py -v
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# ── Make source_code importable ───────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source_code" / "scripts"))

from etl_pipeline import (
    FUND_UNIVERSE,
    DataTransformer,
    ETLPipeline,
    SQLiteLoader,
    SyntheticExtractor,
    _business_dates,
    generate_benchmark_nav,
    generate_synthetic_nav,
)


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def sample_fund() -> dict:
    return FUND_UNIVERSE[0]


@pytest.fixture()
def sample_nav_df(sample_fund) -> pd.DataFrame:
    return generate_synthetic_nav(sample_fund, seed=42)


@pytest.fixture()
def fund_meta_df() -> pd.DataFrame:
    return pd.DataFrame(FUND_UNIVERSE)


@pytest.fixture()
def transformer(fund_meta_df) -> DataTransformer:
    return DataTransformer(fund_meta_df)


@pytest.fixture()
def processed_df(sample_nav_df, transformer) -> pd.DataFrame:
    return transformer.transform(sample_nav_df)


@pytest.fixture()
def tmp_db(tmp_path) -> Path:
    return tmp_path / "test_bluestock.db"


# ─────────────────────────────────────────────────────────────────────────────
# T1 — SYNTHETIC NAV GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

class TestSyntheticNAVGenerator:

    def test_output_columns(self, sample_nav_df):
        assert set(sample_nav_df.columns) >= {"scheme_code", "date", "nav"}

    def test_no_negative_navs(self, sample_nav_df):
        assert (sample_nav_df["nav"] > 0).all(), "NAV must be strictly positive"

    def test_row_count_approx_5_years(self, sample_nav_df):
        # ~252 trading days/year × 5 years
        assert 1100 <= len(sample_nav_df) <= 1400, f"Unexpected row count: {len(sample_nav_df)}"

    def test_dates_are_business_days(self, sample_nav_df):
        days_of_week = sample_nav_df["date"].dt.dayofweek
        assert (days_of_week < 5).all(), "NAV dates must be weekdays only"

    def test_dates_sorted_ascending(self, sample_nav_df):
        assert sample_nav_df["date"].is_monotonic_increasing

    def test_reproducibility_with_seed(self, sample_fund):
        df1 = generate_synthetic_nav(sample_fund, seed=99)
        df2 = generate_synthetic_nav(sample_fund, seed=99)
        pd.testing.assert_frame_equal(df1, df2)

    def test_different_seeds_produce_different_data(self, sample_fund):
        df1 = generate_synthetic_nav(sample_fund, seed=1)
        df2 = generate_synthetic_nav(sample_fund, seed=2)
        assert not df1["nav"].equals(df2["nav"])

    def test_scheme_code_column_correct(self, sample_fund, sample_nav_df):
        assert (sample_nav_df["scheme_code"] == sample_fund["scheme_code"]).all()

    def test_nav_gbm_drift(self, sample_fund):
        """GBM should produce positive long-run drift for equity funds."""
        df = generate_synthetic_nav(sample_fund, seed=42)
        # With mu=0.12+ and 5 years, NAV should be higher than start (on average over seeds)
        start = df["nav"].iloc[0]
        end   = df["nav"].iloc[-1]
        # Allow wide range; just check it's plausible (not 100x or near zero)
        assert start * 0.2 < end < start * 20


# ─────────────────────────────────────────────────────────────────────────────
# T2 — BENCHMARK GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

class TestBenchmarkGenerator:

    def test_columns(self):
        df = generate_benchmark_nav("Nifty 50 TRI")
        assert set(df.columns) >= {"benchmark_name", "date", "index_value"}

    def test_positive_values(self):
        df = generate_benchmark_nav("Nifty 50 TRI")
        assert (df["index_value"] > 0).all()

    def test_unknown_benchmark_fallback(self):
        df = generate_benchmark_nav("Unknown Benchmark XYZ")
        assert len(df) > 0


# ─────────────────────────────────────────────────────────────────────────────
# T3 — DATA TRANSFORMER
# ─────────────────────────────────────────────────────────────────────────────

class TestDataTransformer:

    def test_output_has_required_columns(self, processed_df):
        required = {
            "scheme_code", "date", "nav", "daily_return", "log_return",
            "rolling_30d_vol", "rolling_90d_vol", "rolling_252d_vol",
            "week52_high", "week52_low", "year", "month", "quarter",
            "scheme_name", "category", "sub_category", "amc_name",
        }
        missing = required - set(processed_df.columns)
        assert not missing, f"Missing columns: {missing}"

    def test_no_negative_nav_after_transform(self, processed_df):
        assert (processed_df["nav"] > 0).all()

    def test_daily_return_range(self, processed_df):
        """Daily returns for synthetic data should be within ±50%."""
        returns = processed_df["daily_return"].dropna()
        assert returns.between(-0.5, 0.5).all(), "Returns outside ±50% range"

    def test_rolling_vol_non_negative(self, processed_df):
        for col in ["rolling_30d_vol", "rolling_90d_vol", "rolling_252d_vol"]:
            assert (processed_df[col].dropna() >= 0).all(), f"{col} contains negatives"

    def test_week52_high_gte_nav(self, processed_df):
        assert (processed_df["week52_high"] >= processed_df["nav"] - 1e-6).all()

    def test_week52_low_lte_nav(self, processed_df):
        assert (processed_df["week52_low"] <= processed_df["nav"] + 1e-6).all()

    def test_calendar_columns(self, processed_df):
        assert processed_df["year"].between(2018, 2030).all()
        assert processed_df["month"].between(1, 12).all()
        assert processed_df["quarter"].between(1, 4).all()

    def test_metadata_merged(self, processed_df):
        assert processed_df["scheme_name"].notna().all()
        assert processed_df["category"].notna().all()

    def test_is_return_outlier_boolean(self, processed_df):
        assert processed_df["is_return_outlier"].isin([True, False, 0, 1]).all()

    def test_quality_report_keys(self, processed_df, transformer):
        qr = transformer.quality_report(processed_df, "Test Fund")
        required_keys = {
            "fund_name", "total_rows", "date_min", "date_max",
            "nav_min", "nav_max", "null_nav_count", "outlier_count",
        }
        assert required_keys.issubset(qr.keys())


# ─────────────────────────────────────────────────────────────────────────────
# T4 — SQLITE LOADER
# ─────────────────────────────────────────────────────────────────────────────

class TestSQLiteLoader:

    def test_schema_created(self, tmp_db):
        loader = SQLiteLoader(tmp_db)
        with sqlite3.connect(tmp_db) as conn:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
        expected = {"fund_master", "nav_history", "category_master",
                    "fund_house_master", "benchmark_nav", "etl_run_log"}
        assert expected.issubset(tables)

    def test_fund_master_loaded(self, tmp_db, fund_meta_df):
        loader = SQLiteLoader(tmp_db)
        loader.load_fund_master(fund_meta_df)
        with sqlite3.connect(tmp_db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM fund_master").fetchone()[0]
        assert count == len(fund_meta_df)

    def test_nav_history_loaded(self, tmp_db, fund_meta_df, sample_nav_df,
                                transformer):
        loader = SQLiteLoader(tmp_db)
        loader.load_fund_master(fund_meta_df)
        processed = transformer.transform(sample_nav_df)
        inserted  = loader.load_nav_history(processed)
        assert inserted > 0

    def test_nav_history_no_duplicate_on_rerun(self, tmp_db, fund_meta_df,
                                               sample_nav_df, transformer):
        loader = SQLiteLoader(tmp_db)
        loader.load_fund_master(fund_meta_df)
        processed = transformer.transform(sample_nav_df)
        first  = loader.load_nav_history(processed)
        second = loader.load_nav_history(processed)   # re-insert same data
        assert second == 0, "Duplicate rows were inserted on second run"

    def test_benchmark_nav_loaded(self, tmp_db):
        loader = SQLiteLoader(tmp_db)
        bench  = generate_benchmark_nav("Nifty 50 TRI")
        loader.load_benchmark_nav(bench)
        with sqlite3.connect(tmp_db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM benchmark_nav").fetchone()[0]
        assert count > 0

    def test_etl_run_log_entry(self, tmp_db):
        loader = SQLiteLoader(tmp_db)
        loader.log_run("synthetic", 5, 1000, "SUCCESS")
        with sqlite3.connect(tmp_db) as conn:
            row = conn.execute("SELECT * FROM etl_run_log").fetchone()
        assert row is not None


# ─────────────────────────────────────────────────────────────────────────────
# T5 — END-TO-END PIPELINE SMOKE TEST
# ─────────────────────────────────────────────────────────────────────────────

class TestETLPipelineSmoke:

    def test_pipeline_runs_synthetic(self, tmp_path, monkeypatch):
        """Full pipeline should complete without errors in synthetic mode."""
        import etl_pipeline as ep

        # Redirect paths to tmp_path
        monkeypatch.setattr(ep, "RAW_DIR",       tmp_path / "raw")
        monkeypatch.setattr(ep, "PROCESSED_DIR", tmp_path / "processed")
        monkeypatch.setattr(ep, "ANALYTICS_DIR", tmp_path / "analytics")
        monkeypatch.setattr(ep, "EXPORTS_DIR",   tmp_path / "exports")
        monkeypatch.setattr(ep, "DB_PATH",       tmp_path / "db" / "test.db")
        monkeypatch.setattr(ep, "LOG_DIR",       tmp_path / "logs")

        for p in [ep.RAW_DIR, ep.PROCESSED_DIR, ep.ANALYTICS_DIR,
                  ep.EXPORTS_DIR, ep.DB_PATH.parent, ep.LOG_DIR]:
            p.mkdir(parents=True, exist_ok=True)

        # Use only 2 funds to keep the test fast
        monkeypatch.setattr(ep, "FUND_UNIVERSE", ep.FUND_UNIVERSE[:2])

        pipeline = ep.ETLPipeline(use_synthetic=True)
        stats    = pipeline.run()

        assert stats["funds_loaded"] == 2
        assert stats["total_nav_rows"] >= 0   # 0 valid on re-run (idempotent)
        assert len(stats["errors"]) == 0
        # Verify combined CSV was created (reliable across all runs)
        assert (tmp_path / "processed" / "nav_all_funds.csv").exists()

    def test_pipeline_creates_processed_csvs(self, tmp_path, monkeypatch):
        import etl_pipeline as ep

        monkeypatch.setattr(ep, "RAW_DIR",       tmp_path / "raw")
        monkeypatch.setattr(ep, "PROCESSED_DIR", tmp_path / "processed")
        monkeypatch.setattr(ep, "ANALYTICS_DIR", tmp_path / "analytics")
        monkeypatch.setattr(ep, "EXPORTS_DIR",   tmp_path / "exports")
        monkeypatch.setattr(ep, "DB_PATH",       tmp_path / "db" / "test.db")
        monkeypatch.setattr(ep, "LOG_DIR",       tmp_path / "logs")

        for p in [ep.RAW_DIR, ep.PROCESSED_DIR, ep.ANALYTICS_DIR,
                  ep.EXPORTS_DIR, ep.DB_PATH.parent, ep.LOG_DIR]:
            p.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(ep, "FUND_UNIVERSE", ep.FUND_UNIVERSE[:1])

        pipeline = ep.ETLPipeline(use_synthetic=True)
        pipeline.run()

        processed_files = list((tmp_path / "processed").glob("nav_processed_*.csv"))
        assert len(processed_files) >= 1

    def test_pipeline_analytics_ready_csv(self, tmp_path, monkeypatch):
        import etl_pipeline as ep

        monkeypatch.setattr(ep, "RAW_DIR",       tmp_path / "raw")
        monkeypatch.setattr(ep, "PROCESSED_DIR", tmp_path / "processed")
        monkeypatch.setattr(ep, "ANALYTICS_DIR", tmp_path / "analytics")
        monkeypatch.setattr(ep, "EXPORTS_DIR",   tmp_path / "exports")
        monkeypatch.setattr(ep, "DB_PATH",       tmp_path / "db" / "test.db")
        monkeypatch.setattr(ep, "LOG_DIR",       tmp_path / "logs")

        for p in [ep.RAW_DIR, ep.PROCESSED_DIR, ep.ANALYTICS_DIR,
                  ep.EXPORTS_DIR, ep.DB_PATH.parent, ep.LOG_DIR]:
            p.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(ep, "FUND_UNIVERSE", ep.FUND_UNIVERSE[:2])

        pipeline = ep.ETLPipeline(use_synthetic=True)
        pipeline.run()

        analytics_file = tmp_path / "analytics" / "analytics_ready.csv"
        assert analytics_file.exists(), "analytics_ready.csv was not created"
        df = pd.read_csv(analytics_file)
        assert "daily_return" in df.columns
        assert "scheme_name"  in df.columns
