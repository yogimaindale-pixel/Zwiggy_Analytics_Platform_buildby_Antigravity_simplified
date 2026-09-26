"""CLI Interface for Zwiggy Analytics Platform Data Warehouse.

Provides subcommands for database initialization, source seeding, ingestion,
transformation, quality evaluation, reconciliation, and full pipeline execution.
"""

import argparse
from datetime import datetime, timezone
import json
import logging
import sys

from zwiggy_dwh.batch import start_new_batch, complete_batch
from zwiggy_dwh.bronze import ingest_all_source_tables_to_bronze
from zwiggy_dwh.config import get_settings
from zwiggy_dwh.db import connect, execute_sql
from zwiggy_dwh.dq import evaluate_data_quality_rules
from zwiggy_dwh.gold import transform_silver_to_gold
from zwiggy_dwh.init_db import initialize_dwh_foundation
from zwiggy_dwh.pipeline import run_full_etl_pipeline
from zwiggy_dwh.reconcile import run_reconciliation_checks
from zwiggy_dwh.seed_source import seed_source_database
from zwiggy_dwh.silver import transform_bronze_to_silver


def main() -> None:
    parser = argparse.ArgumentParser(description="Zwiggy Analytics Platform Data Warehouse CLI")
    subparsers = parser.add_subparsers(dest="command", help="Sub-command to execute")

    # seed-source
    subparsers.add_parser("seed-source", help="Seed source database with 18 tables and 336k rows")

    # init-db
    subparsers.add_parser("init-db", help="Initialize DWH control schemas and layer skeletons")

    # ingest
    subparsers.add_parser("ingest", help="Run Source-to-Bronze ingestion")

    # transform
    subparsers.add_parser("transform", help="Run Silver and Gold layer transformations")

    # reconcile
    subparsers.add_parser("reconcile", help="Execute cross-layer reconciliation checks")

    # scorecard
    subparsers.add_parser("scorecard", help="Display Data Quality scorecard metrics")

    # health-check
    subparsers.add_parser("health-check", help="Run operational health check diagnostic")

    # simulate-10-days
    subparsers.add_parser("simulate-10-days", help="Run 10 days of incremental data generation and pipeline execution")

    # run-all
    subparsers.add_parser("run-all", help="Execute complete pipeline end-to-end")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    if not args.command or args.command == "run-all":
        print("Executing Full Medallion Pipeline...")
        run_full_etl_pipeline(seed_source=True, init_db=True)
        print("Pipeline execution completed successfully.")
        return

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
            # Find latest batch
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
