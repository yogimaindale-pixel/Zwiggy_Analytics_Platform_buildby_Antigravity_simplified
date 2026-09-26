"""Integration tests for end-to-end pipeline execution."""

import pytest
from zwiggy_dwh.db import connect, query_scalar
from zwiggy_dwh.pipeline import run_full_etl_pipeline
from zwiggy_dwh.config import get_settings


def test_full_pipeline_execution(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_pipeline.db")
    monkeypatch.setenv("DB_ENGINE", "sqlite")
    monkeypatch.setenv("DB_PATH", db_file)

    # Re-initialize settings with new env vars
    settings = get_settings()

    summary = run_full_etl_pipeline(seed_source=True, init_db=True)
    assert summary["status"] == "COMPLETED"
    assert summary["bronze_total_rows"] > 0
    assert summary["silver_total_rows"] > 0
    assert summary["gold_total_rows"] > 0
    assert summary["reconciliation_checks"] > 0

    # Idempotency check: run pipeline second time without resetting DB
    summary2 = run_full_etl_pipeline(seed_source=False, init_db=False)
    assert summary2["status"] == "COMPLETED"
