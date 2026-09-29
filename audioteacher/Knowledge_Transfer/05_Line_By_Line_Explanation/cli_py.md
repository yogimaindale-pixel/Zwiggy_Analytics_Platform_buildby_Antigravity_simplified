# 📄 Line-by-Line Code Breakdown: `src/zwiggy_dwh/cli.py`

**File Name**: `src/zwiggy_dwh/cli.py`  
**Total Lines**: 165 Lines  
**Primary Purpose**: Command Line Interface (CLI) entrypoint. Parses subcommands (`seed-source`, `init-db`, `ingest`, `transform`, `reconcile`, `scorecard`, `health-check`, `simulate-10-days`, `run-all`) and dispatches pipeline tasks.

---

## 📜 Key Line Walkthrough

* **Line 63**: `def main():` - CLI execution entrypoint function.
* **Lines 65–95**: Builds `argparse.ArgumentParser` instance with command description and subparser choices.
* **Lines 96–150**: Evaluates parsed subcommands:
  - `seed-source`: Calls `seed_source_database()`.
  - `init-db`: Calls `initialize_dwh_foundation()`.
  - `ingest`: Calls `ingest_all_source_tables_to_bronze()`.
  - `transform`: Calls `transform_bronze_to_silver()` and `transform_silver_to_gold()`.
  - `reconcile`: Calls `run_reconciliation_checks()`.
  - `health-check`: Calls `run_operational_health_check()`.
  - `simulate-10-days`: Calls `run_10_day_incremental_simulation()`.
  - `run-all`: Calls `run_full_etl_pipeline()`.
* **Lines 155–161**: Handles `sys.exit(0)` on clean completion or `sys.exit(1)` on error.
* **Line 165**: `if __name__ == "__main__": main()` - Entrypoint execution block.
