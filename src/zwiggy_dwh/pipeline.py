# ==============================================================================
# ZWIGGY ANALYTICS PLATFORM - MASTER ETL PIPELINE ORCHESTRATOR
# ==============================================================================
# File: src/zwiggy_dwh/pipeline.py
# Purpose: Master ETL pipeline coordinator orchestrating end-to-end Medallion data
#          warehouse processing across all stages:
#            1. Infrastructure & Source Seed Initialization
#            2. Source -> Bronze Layer Ingestion (Raw JSON Landing)
#            3. Bronze -> Silver Layer Transformation (Conforming & Cleansing)
#            4. Data Quality Evaluation Engine (Quality Scorecard Calculation)
#            5. Silver -> Gold Dimensional Modeling (SCD2 Dimensions & Marts)
#            6. Reconciliation Checks & Batch Audit Completion
# ==============================================================================

# Import UTC datetime utilities.
from datetime import datetime, timezone

# Import standard logging module.
import logging

# Import typing generics.
from typing import Dict, Any

# Import batch management audit control functions.
from zwiggy_dwh.batch import start_new_batch, complete_batch, fail_batch, log_audit_event

# Import Bronze ingestion engine entrypoint.
from zwiggy_dwh.bronze import ingest_all_source_tables_to_bronze

# Import database connection manager.
from zwiggy_dwh.db import connect

# Import Data Quality rule evaluation engine.
from zwiggy_dwh.dq import evaluate_data_quality_rules

# Import Silver-to-Gold dimensional builder.
from zwiggy_dwh.gold import transform_silver_to_gold

# Import database foundation DDL initializer.
from zwiggy_dwh.init_db import initialize_dwh_foundation

# Import cross-layer reconciliation engine.
from zwiggy_dwh.reconcile import run_reconciliation_checks

# Import operational source seeding utility.
from zwiggy_dwh.seed_source import seed_source_database

# Import Bronze-to-Silver transformation engine.
from zwiggy_dwh.silver import transform_bronze_to_silver

# Create module-level logger.
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# FULL ETL PIPELINE RUNNER FUNCTION
# ------------------------------------------------------------------------------

def run_full_etl_pipeline(seed_source: bool = True, init_db: bool = True) -> Dict[str, Any]:
    """
    Executes complete end-to-end Medallion Data Warehouse pipeline.
    
    Args:
        seed_source (bool): If True, seeds initial operational source database tables.
        init_db (bool): If True, executes DDL scripts initializing ctl, bronze, silver, and gold schemas.
        
    Returns:
        Dict[str, Any]: Detailed execution summary dictionary containing row counts, batch ID, and quality metrics.
    """
    logger.info("Starting Zwiggy Medallion Data Warehouse Pipeline Execution...")

    # Connect to database using context manager.
    with connect() as conn:
        # Step 0A: Seed operational source tables if requested.
        if seed_source:
            logger.info("Seeding operational source tables...")
            seed_source_database(conn)

        # Step 0B: Initialize Data Warehouse schemas and control tables if requested.
        if init_db:
            logger.info("Initializing Data Warehouse schemas and control tables...")
            initialize_dwh_foundation(conn)

        # Register new execution batch in ctl.ctl_batch table.
        batch_id, cutoff_ts = start_new_batch(conn, run_type="FULL_LOAD", description="Full Medallion Pipeline Run")

        try:
            # Step 1: Source -> Bronze Raw Landing Ingestion.
            logger.info("Step 1/5: Executing Source -> Bronze Ingestion...")
            bronze_counts = ingest_all_source_tables_to_bronze(conn, batch_id, cutoff_ts)

            # Step 2: Bronze -> Silver Schema Conforming & Cleansing.
            logger.info("Step 2/5: Executing Bronze -> Silver Transformations...")
            silver_counts = transform_bronze_to_silver(conn, batch_id)

            # Step 3: Data Quality Rule Evaluation & Quality Scorecard.
            logger.info("Step 3/5: Running Data Quality Engine Evaluation...")
            dq_scorecard = evaluate_data_quality_rules(conn, batch_id)

            # Step 4: Silver -> Gold Dimensional Modeling (SCD2 Dimensions, Facts, and Marts).
            logger.info("Step 4/5: Building Gold Star-Schema Dimensions & Facts...")
            gold_counts = transform_silver_to_gold(conn, batch_id)

            # Step 5: Cross-Layer Reconciliation Checks.
            logger.info("Step 5/5: Running Cross-Layer Reconciliation Checks...")
            reconciliation_results = run_reconciliation_checks(conn, batch_id)

            # Mark batch execution as COMPLETED in ctl_batch table.
            complete_batch(conn, batch_id)

            # Formulate final pipeline execution summary.
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
            # On error, record failure status in control table and re-raise exception.
            logger.exception("Pipeline failed with error: %s", e)
            fail_batch(conn, batch_id, str(e))
            raise


# Direct execution entrypoint.
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_full_etl_pipeline()
