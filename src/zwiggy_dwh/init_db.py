"""Database Foundations and DDL Initialization for Zwiggy Data Warehouse.

Idempotently creates all Control, Bronze, Silver, Silver Quarantine, and Gold
schema structures, seeds reference data, and populates ctl_table_config.
"""

import logging
from typing import Optional

from zwiggy_dwh.db import ConnectionWrapper, connect, execute_sql
from zwiggy_dwh.metadata import get_classification_matrix

logger = logging.getLogger(__name__)


def initialize_dwh_foundation(conn: ConnectionWrapper) -> None:
    """Initialize complete DWH foundation, control tables, reference data, and layer skeletons."""
    logger.info("Initializing Data Warehouse Control & Reference infrastructure...")
    cur = conn.cursor()

    # Drop existing DWH tables to ensure clean idempotent run
    control_tables = [
        "ctl_audit_run_log", "ctl_audit_source_extract", "ctl_reconciliation",
        "ctl_dq_rule", "ctl_watermark", "ctl_table_config", "ctl_batch"
    ]
    for tbl in control_tables:
        cur.execute(f"DROP TABLE IF EXISTS {tbl};")

    reference_tables = [
        "silver_ref_status_map", "silver_ref_payment_status_map",
        "silver_ref_cohort_rule", "silver_ref_dq_rule_definition"
    ]
    for tbl in reference_tables:
        cur.execute(f"DROP TABLE IF EXISTS {tbl};")

    # 1. Control Tables
    cur.execute("""
        CREATE TABLE ctl_batch (
            dw_batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_start_ts_utc TIMESTAMP NOT NULL,
            batch_end_ts_utc TIMESTAMP,
            run_cutoff_ts_utc TIMESTAMP NOT NULL,
            run_type VARCHAR(50) NOT NULL DEFAULT 'INCREMENTAL',
            status VARCHAR(50) NOT NULL DEFAULT 'IN_PROGRESS',
            triggered_by VARCHAR(255),
            code_version VARCHAR(50),
            batch_description TEXT,
            created_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE ctl_table_config (
            config_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_system VARCHAR(100) DEFAULT 'zwiggy_db',
            source_schema VARCHAR(100) DEFAULT 'app',
            source_table VARCHAR(255) NOT NULL UNIQUE,
            target_bronze_table VARCHAR(255) NOT NULL,
            target_silver_table VARCHAR(255),
            target_gold_table VARCHAR(255),
            ingestion_strategy VARCHAR(50) NOT NULL,
            business_key VARCHAR(255) NOT NULL,
            watermark_column VARCHAR(255),
            secondary_watermark_column VARCHAR(255),
            primary_key_column VARCHAR(255) NOT NULL,
            lookback_days INT DEFAULT 7,
            is_initial_load_complete BOOLEAN DEFAULT FALSE,
            is_active BOOLEAN DEFAULT TRUE,
            table_group VARCHAR(100),
            created_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE ctl_watermark (
            watermark_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_system VARCHAR(100) DEFAULT 'zwiggy_db',
            source_schema VARCHAR(100) DEFAULT 'app',
            source_table VARCHAR(255) NOT NULL UNIQUE,
            watermark_value VARCHAR(500),
            watermark_secondary_value VARCHAR(500),
            last_successful_batch_id BIGINT,
            last_successful_run_ts TIMESTAMP,
            last_failed_batch_id BIGINT,
            last_failed_run_ts TIMESTAMP,
            extract_row_count INT DEFAULT 0,
            load_row_count INT DEFAULT 0,
            reject_row_count INT DEFAULT 0,
            current_status VARCHAR(50) DEFAULT 'PENDING',
            updated_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE ctl_reconciliation (
            reconciliation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            dw_batch_id BIGINT NOT NULL,
            source_table VARCHAR(255) NOT NULL,
            target_table VARCHAR(255) NOT NULL,
            check_name VARCHAR(255) NOT NULL,
            source_row_count INT,
            target_row_count INT,
            expected_row_count INT,
            threshold_percent NUMERIC(5,2),
            result VARCHAR(50) NOT NULL,
            details TEXT,
            checked_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE ctl_dq_rule (
            dq_rule_id INT PRIMARY KEY,
            rule_category VARCHAR(100),
            rule_name VARCHAR(255) NOT NULL,
            rule_description TEXT,
            severity VARCHAR(50),
            target_table VARCHAR(255),
            sql_predicate TEXT,
            affected_column VARCHAR(255),
            is_active BOOLEAN DEFAULT TRUE,
            created_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE ctl_audit_run_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            dw_batch_id BIGINT NOT NULL,
            source_table VARCHAR(255),
            event_type VARCHAR(100) NOT NULL,
            message TEXT,
            severity VARCHAR(20) DEFAULT 'INFO',
            execution_duration_seconds INT,
            logged_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE ctl_audit_source_extract (
            extract_id INTEGER PRIMARY KEY AUTOINCREMENT,
            dw_batch_id BIGINT NOT NULL,
            source_table VARCHAR(255) NOT NULL,
            extract_predicate TEXT,
            extract_row_count INT NOT NULL,
            extract_start_ts TIMESTAMP NOT NULL,
            extract_end_ts TIMESTAMP NOT NULL,
            min_watermark_value VARCHAR(500),
            max_watermark_value VARCHAR(500),
            checksum_hash VARCHAR(64),
            extract_status VARCHAR(50) DEFAULT 'SUCCESS',
            error_message TEXT,
            created_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    logger.info("Control tables created. Populating ctl_table_config with 18 table strategies...")

    # Populate ctl_table_config
    configs = get_classification_matrix()
    for cfg in configs:
        cur.execute("""
            INSERT INTO ctl_table_config (
                source_table, target_bronze_table, target_silver_table, target_gold_table,
                ingestion_strategy, business_key, watermark_column, secondary_watermark_column,
                primary_key_column, lookback_days, table_group
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            cfg.source_table, cfg.target_bronze_table, cfg.target_silver_table, cfg.target_gold_table,
            cfg.ingestion_strategy, cfg.business_key, cfg.watermark_column, cfg.secondary_watermark_column,
            cfg.primary_key_column, cfg.lookback_days, cfg.table_group
        ))

    conn.commit()

    # 2. Reference Tables
    cur.execute("""
        CREATE TABLE silver_ref_status_map (
            status_map_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_status_value VARCHAR(100) NOT NULL,
            source_table VARCHAR(255) NOT NULL,
            conformed_status_value VARCHAR(100) NOT NULL,
            status_group VARCHAR(100),
            is_valid BOOLEAN DEFAULT TRUE,
            effective_from_date DATE DEFAULT CURRENT_DATE,
            effective_to_date DATE,
            created_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    status_mappings = [
        ("Pending", "app_orders", "PENDING", "In Progress"),
        ("PENDING", "app_orders", "PENDING", "In Progress"),
        ("Completed", "app_orders", "COMPLETED", "Terminal"),
        ("COMPLETED", "app_orders", "COMPLETED", "Terminal"),
        ("Cancelled", "app_orders", "CANCELLED", "Terminal"),
        ("CANCELLED", "app_orders", "CANCELLED", "Terminal"),
        ("Delivered", "app_orders", "COMPLETED", "Terminal"),
        ("PAID", "app_orders", "COMPLETED", "Terminal")
    ]
    cur.executemany("""
        INSERT INTO silver_ref_status_map (source_status_value, source_table, conformed_status_value, status_group)
        VALUES (?, ?, ?, ?);
    """, status_mappings)

    cur.execute("""
        CREATE TABLE silver_ref_cohort_rule (
            cohort_rule_id INT PRIMARY KEY,
            cohort_name VARCHAR(50) NOT NULL,
            boundary_column VARCHAR(100) NOT NULL,
            boundary_operator VARCHAR(10) NOT NULL,
            boundary_value VARCHAR(500) NOT NULL,
            cohort_description TEXT,
            created_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cur.execute("INSERT INTO silver_ref_cohort_rule VALUES (1, 'COHORT_A', 'order_id', '<=', '10928', 'Early cohort with human status vocabulary', CURRENT_TIMESTAMP);")
    cur.execute("INSERT INTO silver_ref_cohort_rule VALUES (2, 'COHORT_B', 'order_id', '>', '10928', 'Late cohort with machine vocabulary', CURRENT_TIMESTAMP);")

    cur.execute("""
        CREATE TABLE silver_ref_dq_rule_definition (
            dq_rule_id INT PRIMARY KEY,
            rule_name VARCHAR(255) NOT NULL,
            rule_description TEXT,
            rule_category VARCHAR(100),
            severity VARCHAR(50),
            target_layer VARCHAR(50),
            target_table VARCHAR(255),
            affected_column VARCHAR(255),
            is_blocking BOOLEAN,
            is_active BOOLEAN DEFAULT TRUE
        );
    """)

    dq_rules = [
        (1, "DQ_EXTRACT_MATCH", "Extract manifest count matches bronze count", "INGESTION", "BLOCK", "BRONZE", "br_orders", "order_id", True),
        (2, "DQ_COHORT_BOUNDARY", "Validate cohort classification boundary", "BUSINESS", "WARN", "SILVER", "slv_order", "dw_source_cohort", False),
        (3, "DQ_PENDING_BUT_PAID", "Order is pending but paid flag is true", "ANOMALY", "WARN", "SILVER", "slv_order", "dq_flag_pending_but_paid", False),
        (4, "DQ_CANCEL_MISMATCH", "Contradiction between cancellation flag and status", "ANOMALY", "WARN", "SILVER", "slv_order", "dq_flag_cancel_mismatch", False),
        (5, "DQ_MISSING_PAYMENT", "Order has no payment record", "GAP", "WARN", "SILVER", "slv_order", "payment_id", False),
        (6, "DQ_MISSING_DELIVERY", "Order has no delivery record", "GAP", "WARN", "SILVER", "slv_order", "delivery_id", False),
        (7, "DQ_SCD2_VALID_DATES", "Valid_to must be after valid_from", "DIMENSIONAL", "BLOCK", "GOLD", "dim_customer", "valid_to_utc", True)
    ]
    cur.executemany("INSERT INTO silver_ref_dq_rule_definition VALUES (?,?,?,?,?,?,?,?,?,1);", dq_rules)

    conn.commit()
    logger.info("Reference data seeded. Initializing Bronze layer tables...")

    # 3. Bronze Tables (br_*)
    for cfg in configs:
        b_tbl = cfg.target_bronze_table
        cur.execute(f"DROP TABLE IF EXISTS {b_tbl};")
        cur.execute(f"""
            CREATE TABLE {b_tbl} (
                dw_ingest_date DATE NOT NULL,
                dw_batch_id BIGINT NOT NULL,
                dw_ingest_ts_utc TIMESTAMP NOT NULL,
                dw_source_system VARCHAR(100) DEFAULT 'zwiggy_db',
                dw_source_schema VARCHAR(100) DEFAULT 'app',
                dw_source_table VARCHAR(255) NOT NULL,
                payload_json TEXT,
                source_primary_key VARCHAR(255),
                PRIMARY KEY (dw_batch_id, source_primary_key)
            );
        """)

    conn.commit()
    logger.info("Bronze tables created. Initializing Silver layer tables and Silver Quarantine tables...")

    # 4. Silver & Silver Quarantine Tables
    silver_tables = [
        "slv_order", "slv_order_item", "slv_payment_attempt", "slv_payment",
        "slv_delivery", "slv_review", "slv_customer", "slv_address",
        "slv_restaurant", "slv_menu_item", "slv_delivery_partner", "slv_cuisine",
        "slv_gender", "slv_cart", "slv_cart_item"
    ]
    for stbl in silver_tables:
        cur.execute(f"DROP TABLE IF EXISTS {stbl};")
        cur.execute(f"DROP TABLE IF EXISTS {stbl}_quarantine;")

        cur.execute(f"""
            CREATE TABLE {stbl} (
                dw_batch_id BIGINT NOT NULL,
                dw_ingest_date DATE NOT NULL,
                dw_source_cohort VARCHAR(50),
                dw_source_hash VARCHAR(64),
                dq_flag_pending_but_paid BOOLEAN DEFAULT FALSE,
                dq_flag_cancel_mismatch BOOLEAN DEFAULT FALSE,
                payload_json TEXT
            );
        """)

        cur.execute(f"""
            CREATE TABLE {stbl}_quarantine (
                quarantine_id INTEGER PRIMARY KEY AUTOINCREMENT,
                dw_batch_id BIGINT NOT NULL,
                dq_rule_id INT NOT NULL,
                dq_reason TEXT,
                dq_detected_ts_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                payload_json TEXT
            );
        """)

    conn.commit()
    logger.info("Silver tables created. Initializing Gold layer (14 SCD2 Dimensions, 6 Facts, 2 Marts)...")

    # 5. Gold Layer
    # 14 Gold Dimensions
    gold_dims = [
        "dim_customer", "dim_address", "dim_restaurant", "dim_menu_item",
        "dim_delivery_partner", "dim_cuisine", "dim_restaurant_owner",
        "dim_order_status", "dim_payment_method", "dim_order_flag",
        "dim_restaurant_cuisine", "dim_cuisine_mapping", "dim_delivery_carrier",
        "dim_review_sentiment"
    ]
    for dtbl in gold_dims:
        cur.execute(f"DROP TABLE IF EXISTS {dtbl};")
        cur.execute(f"""
            CREATE TABLE {dtbl} (
                sk INTEGER PRIMARY KEY AUTOINCREMENT,
                business_key VARCHAR(255) NOT NULL,
                dw_version_no INT DEFAULT 1,
                dw_row_hash VARCHAR(64),
                is_current BOOLEAN DEFAULT TRUE,
                valid_from_utc TIMESTAMP NOT NULL,
                valid_to_utc TIMESTAMP,
                dw_initial_load BOOLEAN DEFAULT FALSE,
                dw_is_deleted BOOLEAN DEFAULT FALSE,
                attributes_json TEXT
            );
        """)

    # 6 Gold Facts
    gold_facts = [
        "fact_order", "fact_order_item", "fact_payment_attempt",
        "fact_payment", "fact_delivery", "fact_review"
    ]
    for ftbl in gold_facts:
        cur.execute(f"DROP TABLE IF EXISTS {ftbl};")
        cur.execute(f"""
            CREATE TABLE {ftbl} (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                dw_batch_id BIGINT NOT NULL,
                event_ts_utc TIMESTAMP NOT NULL,
                dw_source_cohort VARCHAR(50),
                customer_sk BIGINT DEFAULT -1,
                restaurant_sk BIGINT DEFAULT -1,
                delivery_partner_sk BIGINT DEFAULT -1,
                order_id BIGINT,
                amount NUMERIC(18,2),
                dq_flag_dim_fallback BOOLEAN DEFAULT FALSE,
                details_json TEXT
            );
        """)

    # 2 Aggregate Marts
    cur.execute("DROP TABLE IF EXISTS mart_order_daily;")
    cur.execute("""
        CREATE TABLE mart_order_daily (
            order_date DATE PRIMARY KEY,
            total_orders INT,
            completed_orders INT,
            cancelled_orders INT,
            gross_revenue NUMERIC(18,2),
            avg_order_value NUMERIC(18,2)
        );
    """)

    cur.execute("DROP TABLE IF EXISTS mart_revenue_daily;")
    cur.execute("""
        CREATE TABLE mart_revenue_daily (
            order_date DATE PRIMARY KEY,
            gross_revenue NUMERIC(18,2),
            net_revenue NUMERIC(18,2),
            total_tax NUMERIC(18,2) DEFAULT 0.00,
            cohort_a_revenue NUMERIC(18,2),
            cohort_b_revenue NUMERIC(18,2)
        );
    """)

    conn.commit()
    logger.info("Complete DWH foundation initialized successfully!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with connect() as conn:
        initialize_dwh_foundation(conn)
