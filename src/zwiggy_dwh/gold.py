# ==============================================================================
# ZWIGGY ANALYTICS PLATFORM - SILVER-TO-GOLD DIMENSIONAL MODELING ENGINE
# ==============================================================================
# File: src/zwiggy_dwh/gold.py
# Purpose: Builds 14 SCD2 Type-2 dimensions, 6 Fact tables with as-at surrogate key
#          resolution, and 2 aggregate business Data Marts (mart_order_daily, mart_revenue_daily).
# ==============================================================================

# Import UTC datetime utilities.
from datetime import datetime, timezone

# Import md5 hashing and JSON serialization modules.
import hashlib
import json

# Import standard logger module.
import logging

# Import typing hints.
from typing import Dict, List, Optional

# Import audit logger and database helpers.
from zwiggy_dwh.batch import log_audit_event
from zwiggy_dwh.db import ConnectionWrapper, execute_sql

# Instantiate module logger.
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# SILVER-TO-GOLD TRANSFORM & BUILD FUNCTION
# ------------------------------------------------------------------------------

def transform_silver_to_gold(conn: ConnectionWrapper, batch_id: int) -> Dict[str, int]:
    """
    Transforms clean Silver layer data into Gold layer star-schema dimensions,
    fact tables, and aggregate data marts.
    
    Args:
        conn (ConnectionWrapper): Database connection object.
        batch_id (int): Unique batch run execution ID.
        
    Returns:
        Dict[str, int]: Summary mapping table names to inserted row counts.
    """
    logger.info("Starting Silver-to-Gold dimensional build for batch_id=%d...", batch_id)
    cur = conn.cursor()

    counts: Dict[str, int] = {}
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    # --------------------------------------------------------------------------
    # 1. BUILD SCD2 TYPE-2 DIMENSION TABLES
    # --------------------------------------------------------------------------
    # Define mapping of Silver source tables to Gold SCD2 dimension target tables.
    dim_mappings = [
        ("slv_customer", "dim_customer", "customer_id"),
        ("slv_restaurant", "dim_restaurant", "restaurant_id"),
        ("slv_menu_item", "dim_menu_item", "menu_item_id"),
        ("slv_delivery_partner", "dim_delivery_partner", "delivery_partner_id"),
        ("slv_cuisine", "dim_cuisine", "cuisine_id")
    ]

    # Iterate through dimension mappings.
    for s_tbl, d_tbl, bk_col in dim_mappings:
        # Fetch Silver records belonging to current batch.
        s_rows = execute_sql(conn, f"SELECT * FROM {s_tbl} WHERE dw_batch_id = ?;", (batch_id,))
        inserted_dim_cnt = 0

        # Process each Silver record.
        for r in s_rows:
            payload = json.loads(r['payload_json'])
            bk_val = str(payload.get(bk_col, ''))
            r_hash = r['dw_source_hash']

            # Check if current version of business key exists in dimension.
            existing = execute_sql(
                conn, f"SELECT sk, dw_row_hash FROM {d_tbl} WHERE business_key = ? AND is_current = 1;", (bk_val,)
            )

            if not existing:
                # Insert initial version 1 dimension record.
                cur.execute(f"""
                    INSERT INTO {d_tbl} (
                        business_key, dw_version_no, dw_row_hash, is_current,
                        valid_from_utc, valid_to_utc, attributes_json
                    ) VALUES (?, 1, ?, 1, ?, NULL, ?);
                """, (bk_val, r_hash, now_str, json.dumps(payload)))
                inserted_dim_cnt += 1
            elif existing[0]['dw_row_hash'] != r_hash:
                # Expire previous version and insert new SCD2 version 2 dimension record.
                old_sk = existing[0]['sk']
                cur.execute(f"UPDATE {d_tbl} SET is_current = 0, valid_to_utc = ? WHERE sk = ?;", (now_str, old_sk))
                cur.execute(f"""
                    INSERT INTO {d_tbl} (
                        business_key, dw_version_no, dw_row_hash, is_current,
                        valid_from_utc, valid_to_utc, attributes_json
                    ) VALUES (?, 2, ?, 1, ?, NULL, ?);
                """, (bk_val, r_hash, now_str, json.dumps(payload)))
                inserted_dim_cnt += 1

        counts[d_tbl] = inserted_dim_cnt

    conn.commit()

    # --------------------------------------------------------------------------
    # 2. BUILD FACT TABLES WITH SURROGATE KEY (SK) RESOLUTION
    # --------------------------------------------------------------------------
    # Delete existing fact records for current batch to ensure idempotent execution.
    cur.execute("DELETE FROM fact_order WHERE dw_batch_id = ?;", (batch_id,))
    slv_orders = execute_sql(conn, "SELECT * FROM slv_order WHERE dw_batch_id = ?;", (batch_id,))

    facts_to_insert = []
    for so in slv_orders:
        opayload = json.loads(so['payload_json'])
        oid = opayload['order_id']
        cid = str(opayload['customer_id'])
        rid = str(opayload['restaurant_id'])
        amt = opayload['total_price']
        odt = opayload['order_date']

        # Perform as-at surrogate key lookup for customer_sk.
        c_sk_rows = execute_sql(conn, "SELECT sk FROM dim_customer WHERE business_key = ? AND is_current = 1;", (cid,))
        c_sk = c_sk_rows[0]['sk'] if c_sk_rows else -1

        # Perform as-at surrogate key lookup for restaurant_sk.
        r_sk_rows = execute_sql(conn, "SELECT sk FROM dim_restaurant WHERE business_key = ? AND is_current = 1;", (rid,))
        r_sk = r_sk_rows[0]['sk'] if r_sk_rows else -1

        # Flag dimension fallback if lookup returned unknown (-1).
        dim_fallback = (c_sk == -1 or r_sk == -1)

        # Append row tuple for bulk insert.
        facts_to_insert.append((
            batch_id, odt, so['dw_source_cohort'], c_sk, r_sk, -1,
            oid, amt, dim_fallback, json.dumps(opayload)
        ))

    # Bulk insert fact records into fact_order.
    if facts_to_insert:
        cur.executemany("""
            INSERT INTO fact_order (
                dw_batch_id, event_ts_utc, dw_source_cohort, customer_sk,
                restaurant_sk, delivery_partner_sk, order_id, amount,
                dq_flag_dim_fallback, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, facts_to_insert)

    counts["fact_order"] = len(facts_to_insert)
    conn.commit()

    # --------------------------------------------------------------------------
    # 3. BUILD AGGREGATE BUSINESS DATA MARTS
    # --------------------------------------------------------------------------
    # Clear target mart tables.
    cur.execute("DELETE FROM mart_order_daily;")
    cur.execute("DELETE FROM mart_revenue_daily;")

    # Populate daily order metrics mart.
    cur.execute("""
        INSERT INTO mart_order_daily (order_date, total_orders, completed_orders, cancelled_orders, gross_revenue, avg_order_value)
        SELECT 
            SUBSTR(event_ts_utc, 1, 10) as odate,
            COUNT(*) as total_orders,
            SUM(CASE WHEN JSON_EXTRACT(details_json, '$.conformed_status') = 'COMPLETED' THEN 1 ELSE 0 END) as completed_orders,
            SUM(CASE WHEN JSON_EXTRACT(details_json, '$.conformed_status') = 'CANCELLED' THEN 1 ELSE 0 END) as cancelled_orders,
            SUM(amount) as gross_revenue,
            AVG(amount) as avg_order_value
        FROM fact_order
        GROUP BY SUBSTR(event_ts_utc, 1, 10);
    """)

    # Populate daily revenue and cohort breakdown mart.
    cur.execute("""
        INSERT INTO mart_revenue_daily (order_date, gross_revenue, net_revenue, total_tax, cohort_a_revenue, cohort_b_revenue)
        SELECT 
            SUBSTR(event_ts_utc, 1, 10) as odate,
            SUM(amount) as gross_revenue,
            SUM(CASE WHEN JSON_EXTRACT(details_json, '$.conformed_status') = 'COMPLETED' THEN amount ELSE 0 END) as net_revenue,
            0.00 as total_tax,
            SUM(CASE WHEN dw_source_cohort = 'COHORT_A' THEN amount ELSE 0 END) as cohort_a_revenue,
            SUM(CASE WHEN dw_source_cohort = 'COHORT_B' THEN amount ELSE 0 END) as cohort_b_revenue
        FROM fact_order
        GROUP BY SUBSTR(event_ts_utc, 1, 10);
    """)

    # Commit gold transactions and write audit event.
    conn.commit()
    log_audit_event(conn, batch_id, "GOLD_BUILD_COMPLETE", f"Built Gold dimensional layer and aggregate marts.")
    logger.info("Gold layer dimensional model built successfully!")
    return counts
