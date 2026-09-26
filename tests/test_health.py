"""Unit tests for operational health check module."""

import pytest
from zwiggy_dwh.db import connect
from zwiggy_dwh.health import run_operational_health_check
from zwiggy_dwh.init_db import initialize_dwh_foundation
from zwiggy_dwh.seed_source import seed_source_database
from zwiggy_dwh.config import DbTarget


def test_operational_health_check(tmp_path):
    db_file = str(tmp_path / "test_health.db")
    target = DbTarget("sqlite", db_file, "", 0, "", "", "")

    with connect(target) as conn:
        seed_source_database(conn)
        initialize_dwh_foundation(conn)

        report = run_operational_health_check(conn)
        assert "timestamp_utc" in report
        assert "checks" in report
        assert report["checks"]["source_connectivity"]["status"] == "HEALTHY"
        assert report["overall_platform_status"] in ("PASSED", "ACTION_REQUIRED")
