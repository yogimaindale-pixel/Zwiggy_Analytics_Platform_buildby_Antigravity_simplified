"""Unit tests for DWH foundation initialization."""

import pytest
from zwiggy_dwh.db import connect, query_scalar
from zwiggy_dwh.init_db import initialize_dwh_foundation
from zwiggy_dwh.config import DbTarget


def test_dwh_foundation_initialization(tmp_path):
    db_file = str(tmp_path / "test_dwh.db")
    target = DbTarget("sqlite", db_file, "", 0, "", "", "")

    with connect(target) as conn:
        initialize_dwh_foundation(conn)

        # Verify ctl_table_config has 18 rows
        cfg_count = query_scalar(conn, "SELECT COUNT(*) FROM ctl_table_config;")
        assert cfg_count == 18

        # Verify reference data exists
        status_map_cnt = query_scalar(conn, "SELECT COUNT(*) FROM silver_ref_status_map;")
        assert status_map_cnt == 8

        cohort_cnt = query_scalar(conn, "SELECT COUNT(*) FROM silver_ref_cohort_rule;")
        assert cohort_cnt == 2
