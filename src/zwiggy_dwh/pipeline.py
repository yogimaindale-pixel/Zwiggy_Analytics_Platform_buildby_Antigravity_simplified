"""Master ETL Pipeline Orchestrator for Zwiggy Data Warehouse.

Runs end-to-end Medallion pipeline execution from Source -> Bronze -> Silver -> Gold
with full batch orchestration, data quality evaluation, and reconciliation checks.
"""

from datetime import datetime, timezone
import logging
from typing import Dict, Any

from zwiggy_dwh.batch import start_new_batch, complete_batch, fail_batch, log_audit_event
from zwiggy_dwh.bronze import ingest_all_source_tables_to_bronze
from zwiggy_dwh.db import connect
from zwiggy_dwh.dq import evaluate_data_quality_rules
from zwiggy_dwh.gold import transform_silver_to_gold
from zwiggy_dwh.init_db import initialize_dwh_foundation
from zwiggy_dwh.reconcile import run_reconciliation_checks
from zwiggy_dwh.seed_source import seed_source_database
from zwiggy_dwh.silver import transform_bronze_to_silver

logger = logging.getLogger(__name__)


def run_full_etl_pipeline(seed_source: bool = True, init_db: bool = True) -> Dict[str, Any]:
    """Execute complete end-to-end Medallion Data Warehouse pipeline."""
    logger.info("Starting Zwiggy Medallion Data Warehouse Pipeline Execution...")

    with connect() as conn:
        if seed_source:
            seed_source_database(conn)

        if init_db:
            initialize_dwh_foundation(conn)

        batch_id, cutoff_ts = start_new_batch(conn, run_type="FULL_LOAD", description="Full Medallion Pipeline Run")

        try:
            # 1. Source -> Bronze
            bronze_counts = ingest_all_source_tables_to_bronze(conn, batch_id, cutoff_ts)

            # 2. Bronze -> Silver
            silver_counts = transform_bronze_to_silver(conn, batch_id)

            # 3. Data Quality Engine
            dq_scorecard = evaluate_data_quality_rules(conn, batch_id)

            # 4. Silver -> Gold
            gold_counts = transform_silver_to_gold(conn, batch_id)

            # 5. Reconciliation Checks
            reconciliation_results = run_reconciliation_checks(conn, batch_id)

            complete_batch(conn, batch_id)

            pipeline_summary = {
                "status": "COMPLETED",
                "dw_batch_id": batch_id,
                "bronze_total_rows": sum(bronze_counts.values()),
                "silver_total_rows": sum(silver_counts.values()),
                "gold_total_rows": sum(gold_counts.values()),
                "data_quality_scorecard": dq_scorecard,
                "reconciliation_checks": len(reconciliation_results)
            }

            logger.info("Pipeline Execution Completed Successfully! Summary: %s", pipeline_summary)
            return pipeline_summary

        except Exception as e:
            logger.exception("Pipeline failed with error: %s", e)
            fail_batch(conn, batch_id, str(e))
            raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_full_etl_pipeline()
