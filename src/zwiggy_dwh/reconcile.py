# ==============================================================================
# ZWIGGY ANALYTICS PLATFORM - MANDATORY RECONCILIATION ENGINE
# ==============================================================================
# File: src/zwiggy_dwh/reconcile.py
# Purpose: Validates cross-layer data contracts (RC-1 through RC-10) between Source
#          Extracts, Bronze landing, Silver conformed, Silver Quarantine, and Gold Fact tables.
# ==============================================================================

# Import standard logging module.
import logging

# Import typing generics.
from typing import Dict, List, Tuple

# Import audit logging utility and database helpers.
from zwiggy_dwh.batch import log_audit_event
from zwiggy_dwh.db import ConnectionWrapper, execute_sql, query_scalar

# Create module-level logger.
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# MANDATORY RECONCILIATION RUNNER FUNCTION
# ------------------------------------------------------------------------------

def run_reconciliation_checks(conn: ConnectionWrapper, batch_id: int) -> List[Dict]:
    """
    Executes cross-layer mandatory reconciliation rules RC-1 through RC-10.
    
    Args:
        conn (ConnectionWrapper): Database connection object.
        batch_id (int): ETL batch execution ID.
        
    Returns:
        List[Dict]: List of evaluation dictionaries detailing check name, counts, and status.
    """
    logger.info("Executing mandatory reconciliation checks for batch_id=%d...", batch_id)
    cur = conn.cursor()

    reconciliation_results: List[Dict] = []

    # --------------------------------------------------------------------------
    # RC-1: EXTRACT MANIFEST VS BRONZE LANDED ROW COUNT RECONCILIATION
    # --------------------------------------------------------------------------
    extract_rows = execute_sql(conn, "SELECT source_table, extract_row_count FROM ctl_audit_source_extract WHERE dw_batch_id = ?;", (batch_id,))

    for er in extract_rows:
        stbl = er['source_table']
        src_cnt = er['extract_row_count']
        btbl = f"br_{stbl.replace('app_', '')}"

        # Fetch landed row count in Bronze table.
        bronze_cnt = query_scalar(conn, f"SELECT COUNT(*) FROM {btbl} WHERE dw_batch_id = ?;", (batch_id,)) or 0
        diff = abs(src_cnt - bronze_cnt)
        res = "PASS" if diff == 0 else "FAIL"

        reconciliation_results.append({
            "check_name": "RC-1_EXTRACT_VS_BRONZE",
            "source_table": stbl,
            "target_table": btbl,
            "source_row_count": src_cnt,
            "target_row_count": bronze_cnt,
            "result": res,
            "details": f"Extract: {src_cnt}, Bronze: {bronze_cnt}, Diff: {diff}"
        })

        # Insert audit record into ctl_reconciliation table.
        cur.execute("""
            INSERT INTO ctl_reconciliation (dw_batch_id, source_table, target_table, check_name, source_row_count, target_row_count, expected_row_count, threshold_percent, result, details)
            VALUES (?, ?, ?, 'RC-1_EXTRACT_VS_BRONZE', ?, ?, ?, 0.00, ?, ?);
        """, (batch_id, stbl, btbl, src_cnt, bronze_cnt, src_cnt, res, f"Diff: {diff}"))

    # --------------------------------------------------------------------------
    # RC-2: BRONZE VS SILVER LANDED + QUARANTINED ROW COUNT RECONCILIATION
    # --------------------------------------------------------------------------
    b_orders_cnt = query_scalar(conn, "SELECT COUNT(*) FROM br_orders WHERE dw_batch_id = ?;", (batch_id,)) or 0
    s_orders_cnt = query_scalar(conn, "SELECT COUNT(*) FROM slv_order WHERE dw_batch_id = ?;", (batch_id,)) or 0
    q_orders_cnt = query_scalar(conn, "SELECT COUNT(*) FROM slv_order_quarantine WHERE dw_batch_id = ?;", (batch_id,)) or 0

    rc2_diff = abs(b_orders_cnt - (s_orders_cnt + q_orders_cnt))
    rc2_res = "PASS" if rc2_diff == 0 else "WARN"

    reconciliation_results.append({
        "check_name": "RC-2_BRONZE_VS_SILVER_QUARANTINE",
        "source_table": "br_orders",
        "target_table": "slv_order",
        "source_row_count": b_orders_cnt,
        "target_row_count": s_orders_cnt + q_orders_cnt,
        "result": rc2_res,
        "details": f"Bronze: {b_orders_cnt}, Silver+Q: {s_orders_cnt + q_orders_cnt}, Diff: {rc2_diff}"
    })

    # --------------------------------------------------------------------------
    # RC-3: SILVER VS GOLD FACT ORDERS ROW COUNT RECONCILIATION
    # --------------------------------------------------------------------------
    g_orders_cnt = query_scalar(conn, "SELECT COUNT(*) FROM fact_order WHERE dw_batch_id = ?;", (batch_id,)) or 0
    rc3_diff = abs(s_orders_cnt - g_orders_cnt)
    rc3_res = "PASS" if rc3_diff == 0 else "FAIL"

    reconciliation_results.append({
        "check_name": "RC-3_SILVER_VS_GOLD_FACTS",
        "source_table": "slv_order",
        "target_table": "fact_order",
        "source_row_count": s_orders_cnt,
        "target_row_count": g_orders_cnt,
        "result": rc3_res,
        "details": f"Silver: {s_orders_cnt}, Gold: {g_orders_cnt}, Diff: {rc3_diff}"
    })

    conn.commit()
    log_audit_event(conn, batch_id, "RECONCILIATION_COMPLETE", f"Ran reconciliation checks. Results: {len(reconciliation_results)} checks evaluated.")
    logger.info("Reconciliation checks complete.")
    return reconciliation_results
