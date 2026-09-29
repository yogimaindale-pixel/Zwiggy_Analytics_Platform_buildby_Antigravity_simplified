# ==============================================================================
# ZWIGGY ANALYTICS PLATFORM - BRONZE-TO-SILVER TRANSFORMATION ENGINE
# ==============================================================================
# File: src/zwiggy_dwh/silver.py
# Purpose: Cleanses, normalizes, type-casts, and conforms raw Bronze data into Silver.
#          Applies Business Rules BR-R1 through BR-R11 (cohort tagging, status
#          conformance, cancellation contradiction flags, and payment retry collapse).
# ==============================================================================

# Import UTC datetime utilities.
from datetime import datetime, timezone

# Import md5 hashing and JSON serialization modules.
import hashlib
import json

# Import standard logging module.
import logging

# Import typing hints.
from typing import Dict, List, Optional

# Import audit logging helper and database queries.
from zwiggy_dwh.batch import log_audit_event
from zwiggy_dwh.db import ConnectionWrapper, execute_sql

# Create standard logger instance for this module.
logger = logging.getLogger(__name__)

# Business Rule BR-R2: Cohort boundary order_id split.
COHORT_BOUNDARY_ORDER_ID = 10928


# ------------------------------------------------------------------------------
# BRONZE-TO-SILVER TRANSFORMATION ENGINE FUNCTION
# ------------------------------------------------------------------------------

def transform_bronze_to_silver(conn: ConnectionWrapper, batch_id: int) -> Dict[str, int]:
    """
    Executes Silver layer transformations for raw Bronze landed data.
    
    Args:
        conn (ConnectionWrapper): Database connection object.
        batch_id (int): Unique batch run execution ID.
        
    Returns:
        Dict[str, int]: Summary mapping Silver table names to transformed row counts.
    """
    logger.info("Starting Bronze-to-Silver transformation for batch_id=%d...", batch_id)
    cur = conn.cursor()

    counts: Dict[str, int] = {}

    # --------------------------------------------------------------------------
    # 1. TRANSFORM ORDERS DATA -> slv_order
    # --------------------------------------------------------------------------
    # Clear existing Silver order records for current batch to ensure idempotency.
    cur.execute("DELETE FROM slv_order WHERE dw_batch_id = ?;", (batch_id,))
    rows = execute_sql(conn, "SELECT * FROM br_orders WHERE dw_batch_id = ?;", (batch_id,))

    slv_orders_to_insert = []
    for r in rows:
        payload = json.loads(r['payload_json'])
        order_id = int(payload['order_id'])
        order_status = payload.get('order_status', '')
        payment_status = bool(payload.get('payment_status', False))
        is_cancelled = bool(payload.get('is_cancelled', False))

        # Business Rule BR-R2: Cohort Tagging based on order_id split.
        cohort = "COHORT_A" if order_id <= COHORT_BOUNDARY_ORDER_ID else "COHORT_B"

        # Business Rule BR-R8: Status Conformance mapping.
        norm_status = str(order_status).upper()
        if norm_status in ("COMPLETED", "DELIVERED", "PAID"):
            conformed_status = "COMPLETED"
        elif norm_status in ("PENDING",):
            conformed_status = "PENDING"
        elif norm_status in ("CANCELLED",):
            conformed_status = "CANCELLED"
        else:
            conformed_status = "PENDING"

        # Business Rule BR-R3: Flag pending orders with payment completed.
        flag_pending_paid = (conformed_status == "PENDING" and payment_status is True)
        
        # Business Rule BR-R7: Flag cancellation flag contradictions.
        flag_cancel_mismatch = (is_cancelled and conformed_status == "COMPLETED")

        # Compute MD5 row hash for change data capture tracking.
        row_hash = hashlib.md5(f"{order_id}:{conformed_status}:{payment_status}:{is_cancelled}".encode('utf-8')).hexdigest()

        # Build conformed cleaned payload dictionary.
        cleaned_payload = {
            "order_id": order_id,
            "customer_id": payload.get("customer_id"),
            "restaurant_id": payload.get("restaurant_id"),
            "address_id": payload.get("address_id"),
            "total_price": float(payload.get("total_price", 0.0)),
            "order_date": payload.get("order_date"),
            "conformed_status": conformed_status,
            "raw_status": order_status,
            "payment_status": payment_status,
            "is_cancelled": is_cancelled,
            "tax_amount": 0.00,
            "revenue_is_gross_inclusive": True
        }

        # Append tuple for Silver order insert.
        slv_orders_to_insert.append((
            batch_id, r['dw_ingest_date'], cohort, row_hash,
            flag_pending_paid, flag_cancel_mismatch, json.dumps(cleaned_payload)
        ))

    # Bulk insert conformed records into slv_order.
    if slv_orders_to_insert:
        cur.executemany("""
            INSERT INTO slv_order (
                dw_batch_id, dw_ingest_date, dw_source_cohort, dw_source_hash,
                dq_flag_pending_but_paid, dq_flag_cancel_mismatch, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """, slv_orders_to_insert)

    counts["slv_order"] = len(slv_orders_to_insert)

    # --------------------------------------------------------------------------
    # 2. TRANSFORM PAYMENTS -> slv_payment_attempt & slv_payment (BR-R5 RETRY COLLAPSE)
    # --------------------------------------------------------------------------
    # Clear existing payment records for current batch.
    cur.execute("DELETE FROM slv_payment_attempt WHERE dw_batch_id = ?;", (batch_id,))
    cur.execute("DELETE FROM slv_payment WHERE dw_batch_id = ?;", (batch_id,))

    p_rows = execute_sql(conn, "SELECT * FROM br_payments WHERE dw_batch_id = ?;", (batch_id,))
    attempts_to_insert = []
    payments_by_order: Dict[int, Dict] = {}

    for pr in p_rows:
        ppayload = json.loads(pr['payload_json'])
        oid = int(ppayload['order_id'])
        amt = float(ppayload.get('amount', 0.0))
        pstatus = str(ppayload.get('payment_status', 'FAILED')).upper()
        pdate = ppayload.get('payment_date')

        cohort = "COHORT_A" if oid <= COHORT_BOUNDARY_ORDER_ID else "COHORT_B"
        r_hash = hashlib.md5(f"{ppayload['payment_id']}:{pstatus}:{amt}".encode('utf-8')).hexdigest()

        # Add raw attempt.
        attempts_to_insert.append((
            batch_id, pr['dw_ingest_date'], cohort, r_hash, False, False, json.dumps(ppayload)
        ))

        # Business Rule BR-R5: Collapse payment retries by taking latest SUCCESS or first attempt.
        if oid not in payments_by_order or pstatus == "SUCCESS":
            payments_by_order[oid] = {
                "order_id": oid,
                "payment_id": ppayload['payment_id'],
                "payment_method": ppayload.get('payment_method', 'UNKNOWN'),
                "payment_status": pstatus,
                "amount": amt,
                "payment_date": pdate
            }

    # Insert payment attempts.
    if attempts_to_insert:
        cur.executemany("""
            INSERT INTO slv_payment_attempt (
                dw_batch_id, dw_ingest_date, dw_source_cohort, dw_source_hash,
                dq_flag_pending_but_paid, dq_flag_cancel_mismatch, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """, attempts_to_insert)

    # Prepare collapsed single payments.
    payments_to_insert = []
    for oid, pdict in payments_by_order.items():
        cohort = "COHORT_A" if oid <= COHORT_BOUNDARY_ORDER_ID else "COHORT_B"
        r_hash = hashlib.md5(f"{pdict['payment_id']}:{pdict['amount']}".encode('utf-8')).hexdigest()
        payments_to_insert.append((
            batch_id, pr['dw_ingest_date'] if 'pr' in locals() else datetime.now().strftime('%Y-%m-%d'),
            cohort, r_hash, False, False, json.dumps(pdict)
        ))

    # Insert collapsed single payments.
    if payments_to_insert:
        cur.executemany("""
            INSERT INTO slv_payment (
                dw_batch_id, dw_ingest_date, dw_source_cohort, dw_source_hash,
                dq_flag_pending_but_paid, dq_flag_cancel_mismatch, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """, payments_to_insert)

    counts["slv_payment_attempt"] = len(attempts_to_insert)
    counts["slv_payment"] = len(payments_to_insert)

    # --------------------------------------------------------------------------
    # 3. TRANSFORM MASTER ENTITIES & REFERENCE LOOKUPS
    # --------------------------------------------------------------------------
    master_mappings = [
        ("br_customer", "slv_customer", "customer_id"),
        ("br_restaurant", "slv_restaurant", "restaurant_id"),
        ("br_menu_item", "slv_menu_item", "menu_item_id"),
        ("br_delivery_partner", "slv_delivery_partner", "delivery_partner_id"),
        ("br_cuisines", "slv_cuisine", "cuisine_id"),
        ("br_delivery_details", "slv_delivery", "delivery_id")
    ]

    for b_tbl, s_tbl, pk_field in master_mappings:
        cur.execute(f"DELETE FROM {s_tbl} WHERE dw_batch_id = ?;", (batch_id,))
        m_rows = execute_sql(conn, f"SELECT * FROM {b_tbl} WHERE dw_batch_id = ?;", (batch_id,))

        s_insert = []
        for mr in m_rows:
            mpayload = json.loads(mr['payload_json'])
            r_hash = hashlib.md5(json.dumps(mpayload, sort_keys=True).encode('utf-8')).hexdigest()
            s_insert.append((
                batch_id, mr['dw_ingest_date'], "ALL", r_hash, False, False, json.dumps(mpayload)
            ))

        if s_insert:
            cur.executemany(f"""
                INSERT INTO {s_tbl} (
                    dw_batch_id, dw_ingest_date, dw_source_cohort, dw_source_hash,
                    dq_flag_pending_but_paid, dq_flag_cancel_mismatch, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, s_insert)

        counts[s_tbl] = len(s_insert)

    # Commit silver transaction and log audit event.
    conn.commit()
    log_audit_event(conn, batch_id, "SILVER_TRANSFORMATION_COMPLETE", f"Transformed Silver layer ({sum(counts.values())} records).")
    logger.info("Silver layer transformation completed successfully!")
    return counts
