"""Master ETL Pipeline Orchestrator for Zwiggy Data Warehouse.

This module coordinates end-to-end Medallion pipeline execution across all processing layers:
  1. Source Seeding & Infrastructure Initialization
  2. Source -> Bronze Layer Ingestion (Raw JSONB Landing)
  3. Bronze -> Silver Layer Transformation (Schema Conforming & Cleansing)
  4. Data Quality Evaluation Engine (27 Rules Scorecard)
  5. Silver -> Gold Dimensional Modeling (SCD Type 2 Star Schema & Marts)
  6. Reconciliation Checks & Batch Audit Completion
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
    """Execute complete end-to-end Medallion Data Warehouse pipeline.

    Args:
        seed_source (bool): If True, populates initial source database tables with sample records.
        init_db (bool): If True, executes DDL scripts initializing ctl, bronze, silver, and gold schemas.

    Returns:
        Dict[str, Any]: Execution summary dictionary containing row counts, batch ID, and DQ scorecard.
    """
    logger.info("Starting Zwiggy Medallion Data Warehouse Pipeline Execution...")

    with connect() as conn:
        # Step 0: Infrastructure & Source Seed Initialization
        if seed_source:
            logger.info("Seeding operational source tables...")
            seed_source_database(conn)

        if init_db:
            logger.info("Initializing Data Warehouse schemas and control tables...")
            initialize_dwh_foundation(conn)

        # Register new execution batch in ctl.ctl_batch
        batch_id, cutoff_ts = start_new_batch(conn, run_type="FULL_LOAD", description="Full Medallion Pipeline Run")

        try:
            # Step 1: Source -> Bronze Raw Ingestion
            # Extracts raw payloads from operational tables and lands them in JSONB format.
            logger.info("Step 1/5: Executing Source -> Bronze Ingestion...")
            bronze_counts = ingest_all_source_tables_to_bronze(conn, batch_id, cutoff_ts)

            # Step 2: Bronze -> Silver Schema Conforming & Cleansing
            # Parses JSON payloads, applies strong typing, deduplicates records, and enforces constraints.
            logger.info("Step 2/5: Executing Bronze -> Silver Transformations...")
            silver_counts = transform_bronze_to_silver(conn, batch_id)

            # Step 3: Data Quality Rule Evaluation
            # Evaluates data quality rules across relational tables and computes quality scorecard.
            logger.info("Step 3/5: Running Data Quality Engine Evaluation...")
            dq_scorecard = evaluate_data_quality_rules(conn, batch_id)

            # Step 4: Silver -> Gold Dimensional Modeling
            # Builds dimensional star schema: SCD Type 2 dimensions, transaction facts, and marts.
            logger.info("Step 4/5: Building Gold Star-Schema Dimensions & Facts...")
            gold_counts = transform_silver_to_gold(conn, batch_id)

            # Step 5: Reconciliation & Batch Audit Completion
            # Executes cross-layer reconciliation checks to verify row count and revenue metric alignment.
            logger.info("Step 5/5: Running Cross-Layer Reconciliation Checks...")
            reconciliation_results = run_reconciliation_checks(conn, batch_id)

            # Mark batch successfully completed in ctl_batch
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
            # Catch exceptions, mark batch FAILED in control table, and re-raise exception.
            logger.exception("Pipeline failed with error: %s", e)
            fail_batch(conn, batch_id, str(e))
            raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_full_etl_pipeline()

