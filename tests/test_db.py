"""Unit tests for database connection and execution helper module."""

import pytest
from zwiggy_dwh.db import connect, execute_sql, query_scalar
from zwiggy_dwh.config import DbTarget


def test_sqlite_connection():
    target = DbTarget("sqlite", ":memory:", "", 0, "", "", "")
    with connect(target) as conn:
        res = execute_sql(conn, "SELECT 1 as val;")
        assert len(res) == 1
        assert res[0]['val'] == 1


def test_query_scalar():
    target = DbTarget("sqlite", ":memory:", "", 0, "", "", "")
    with connect(target) as conn:
        val = query_scalar(conn, "SELECT 'hello' as greeting;")
        assert val == 'hello'
