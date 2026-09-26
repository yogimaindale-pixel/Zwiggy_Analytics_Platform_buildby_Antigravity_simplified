"""Unit tests for 10-day incremental data simulation module."""

import pytest
from zwiggy_dwh.db import connect
from zwiggy_dwh.init_db import initialize_dwh_foundation
from zwiggy_dwh.seed_source import seed_source_database
from zwiggy_dwh.simulate_incremental import run_10_day_incremental_simulation
from zwiggy_dwh.config import DbTarget


def test_10_day_incremental_simulation(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_inc.db")
    target = DbTarget("sqlite", db_file, "", 0, "", "", "")

    with connect(target) as conn:
        seed_source_database(conn)
        initialize_dwh_foundation(conn)

        results = run_10_day_incremental_simulation(conn)
        assert len(results) == 10
        assert all(r["reconciliation_pass"] is True for r in results)
        assert results[0]["day"] == 1
        assert results[9]["day"] == 10
