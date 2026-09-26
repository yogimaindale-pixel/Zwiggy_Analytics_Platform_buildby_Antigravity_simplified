"""Unit tests for configuration management module."""

import pytest
from zwiggy_dwh.config import Settings, DbTarget, get_settings


def test_settings_initialization():
    settings = get_settings()
    assert settings.db_engine in ('sqlite', 'duckdb', 'postgres')
    assert settings.batch_size > 0
    assert settings.default_lookback_days >= 0


def test_masked_repr():
    target = DbTarget(
        engine="postgres",
        db_path="",
        host="localhost",
        port=5432,
        dbname="zwiggy_db",
        user="postgres",
        password="secretpassword"
    )
    masked = target.masked_repr()
    assert "secretpassword" not in masked
    assert "***" in masked
