"""Unit tests for Zwiggy Analytics Platform CLI interface."""

import pytest
from unittest.mock import patch
from zwiggy_dwh.cli import main


class TestCLI:

    @patch("sys.argv", ["zwiggy-cli", "seed-source"])
    @patch("zwiggy_dwh.cli.seed_source_database")
    @patch("zwiggy_dwh.cli.connect")
    def test_cli_seed_source(self, mock_connect, mock_seed):
        main()
        mock_seed.assert_called_once()

    @patch("sys.argv", ["zwiggy-cli", "init-db"])
    @patch("zwiggy_dwh.cli.initialize_dwh_foundation")
    @patch("zwiggy_dwh.cli.connect")
    def test_cli_init_db(self, mock_connect, mock_init):
        main()
        mock_init.assert_called_once()

    @patch("sys.argv", ["zwiggy-cli", "health-check"])
    @patch("zwiggy_dwh.health.run_operational_health_check", return_value={"status": "HEALTHY"})
    @patch("zwiggy_dwh.cli.connect")
    def test_cli_health_check(self, mock_connect, mock_health):
        main()
        mock_health.assert_called_once()

    @patch("sys.argv", ["zwiggy-cli", "run-all"])
    @patch("zwiggy_dwh.cli.run_full_etl_pipeline")
    def test_cli_run_all(self, mock_run_all):
        main()
        mock_run_all.assert_called_once_with(seed_source=True, init_db=True)
