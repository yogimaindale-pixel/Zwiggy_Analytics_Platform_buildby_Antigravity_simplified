# ==============================================================================
# ZWIGGY ANALYTICS PLATFORM - COMMAND LINE INTERFACE (CLI)
# ==============================================================================
# File: src/zwiggy_dwh/cli.py
# Purpose: Command-line entrypoint exposing modular subcommands for database initialization,
#          source seeding, ingestion, transformation, quality scorecard calculation,
#          operational health diagnostics, incremental simulation, and end-to-end execution.
# ==============================================================================

# Import standard argument parsing module.
import argparse

# Import UTC datetime utilities.
from datetime import datetime, timezone

# Import JSON formatting utility.
import json

# Import standard logging module.
import logging

# Import sys module.
import sys

# Import batch management audit helpers.
from zwiggy_dwh.batch import start_new_batch, complete_batch

# Import Bronze ingestion module.
from zwiggy_dwh.bronze import ingest_all_source_tables_to_bronze

# Import configuration settings getter.
from zwiggy_dwh.config import get_settings

# Import database connection manager and SQL runner.
from zwiggy_dwh.db import connect, execute_sql

# Import Data Quality rule evaluation engine.
from zwiggy_dwh.dq import evaluate_data_quality_rules

# Import Silver-to-Gold dimensional builder.
from zwiggy_dwh.gold import transform_silver_to_gold

# Import DWH database schema initializer.
from zwiggy_dwh.init_db import initialize_dwh_foundation

# Import master pipeline orchestrator.
from zwiggy_dwh.pipeline import run_full_etl_pipeline

# Import cross-layer reconciliation runner.
from zwiggy_dwh.reconcile import run_reconciliation_checks

# Import operational source seeding utility.
from zwiggy_dwh.seed_source import seed_source_database

# Import Bronze-to-Silver transformation module.
from zwiggy_dwh.silver import transform_bronze_to_silver


# ------------------------------------------------------------------------------
# MAIN CLI PARSER ENTRYPOINT
# ------------------------------------------------------------------------------

def main() -> None:
    """Main CLI entrypoint parsing arguments and dispatching sub-commands."""
    parser = argparse.ArgumentParser(description="Zwiggy Analytics Platform Data Warehouse CLI")
    subparsers = parser.add_subparsers(dest="command", help="Sub-command to execute")

    # Command 1: seed-source
    subparsers.add_parser("seed-source", help="Seed source database with 18 tables and 336k rows")

    # Command 2: init-db
    subparsers.add_parser("init-db", help="Initialize DWH control schemas and layer skeletons")

    # Command 3: ingest
    subparsers.add_parser("ingest", help="Run Source-to-Bronze ingestion")

    # Command 4: transform
    subparsers.add_parser("transform", help="Run Silver and Gold layer transformations")

    # Command 5: reconcile
    subparsers.add_parser("reconcile", help="Execute cross-layer reconciliation checks")

    # Command 6: scorecard
    subparsers.add_parser("scorecard", help="Display Data Quality scorecard metrics")

    # Command 7: health-check
    subparsers.add_parser("health-check", help="Run operational health check diagnostic")

    # Command 8: simulate-10-days
    subparsers.add_parser("simulate-10-days", help="Run 10 days of incremental data generation and pipeline execution")

    # Command 9: run-all
    subparsers.add_parser("run-all", help="Execute complete pipeline end-to-end")

    # Parse command line flags.
    args = parser.parse_args()

    # Configure root logging format.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # If no subcommand provided or run-all requested, execute full pipeline.
    if not args.command or args.command == "run-all":
        print("Executing Full Medallion Pipeline...")
        run_full_etl_pipeline(seed_source=True, init_db=True)
        print("Pipeline execution completed successfully.")
        return

    # Dispatch subcommand handlers using database context wrapper.
    with connect() as conn:
        if args.command == "seed-source":
            print("Seeding source database...")
            seed_source_database(conn)
            print("Source database seeded successfully.")

        elif args.command == "init-db":
            print("Initializing DWH control and reference structures...")
            initialize_dwh_foundation(conn)
            print("DWH foundation initialized successfully.")

        elif args.command == "ingest":
            batch_id, cutoff = start_new_batch(conn, run_type="INGESTION_ONLY")
            counts = ingest_all_source_tables_to_bronze(conn, batch_id, cutoff)
            complete_batch(conn, batch_id)
            print(f"Bronze Ingestion Complete. Total rows: {sum(counts.values())}")

        elif args.command == "transform":
            latest_batch = execute_sql(conn, "SELECT MAX(dw_batch_id) as bid FROM ctl_batch;")
            bid = latest_batch[0]['bid'] if latest_batch and latest_batch[0]['bid'] else 1
            print(f"Transforming batch {bid}...")
            s_counts = transform_bronze_to_silver(conn, bid)
            evaluate_data_quality_rules(conn, bid)
            g_counts = transform_silver_to_gold(conn, bid)
            print(f"Transformation Complete. Silver rows: {sum(s_counts.values())}, Gold rows: {sum(g_counts.values())}")

        elif args.command == "reconcile":
            latest_batch = execute_sql(conn, "SELECT MAX(dw_batch_id) as bid FROM ctl_batch;")
            bid = latest_batch[0]['bid'] if latest_batch and latest_batch[0]['bid'] else 1
            results = run_reconciliation_checks(conn, bid)
            print("\nReconciliation Results:")
            for r in results:
                print(f"[{r['result']}] {r['check_name']} ({r['source_table']} -> {r['target_table']}): {r['details']}")

        elif args.command == "scorecard":
            latest_batch = execute_sql(conn, "SELECT MAX(dw_batch_id) as bid FROM ctl_batch;")
            bid = latest_batch[0]['bid'] if latest_batch and latest_batch[0]['bid'] else 1
            scorecard = evaluate_data_quality_rules(conn, bid)
            print("\nData Quality Scorecard:")
            print(json.dumps(scorecard, indent=2))

        elif args.command == "health-check":
            from zwiggy_dwh.health import run_operational_health_check
            report = run_operational_health_check(conn)
            print("\nOperational Health Report:")
            print(json.dumps(report, indent=2))

        elif args.command == "simulate-10-days":
            from zwiggy_dwh.simulate_incremental import run_10_day_incremental_simulation
            print("Running 10-day incremental data simulation & ingestion...")
            sim_results = run_10_day_incremental_simulation(conn)
            print("\n10-Day Incremental Simulation Summary:")
            print(json.dumps(sim_results, indent=2))


if __name__ == "__main__":
    main()
