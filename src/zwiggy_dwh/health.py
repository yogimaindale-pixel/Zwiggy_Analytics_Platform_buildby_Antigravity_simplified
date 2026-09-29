# ==============================================================================
# ZWIGGY ANALYTICS PLATFORM - OPERATIONAL HEALTH & DIAGNOSTICS ENGINE
# ==============================================================================
# File: src/zwiggy_dwh/health.py
# Purpose: Provides diagnostic health checks for source connectivity, control batch
#          lifecycle state, data freshness, reconciliation compliance, and quarantine rates.
# ==============================================================================

# Import UTC datetime utilities.
from datetime import datetime, timezone

# Import JSON serialization utilities.
import json

# Import standard logging module.
import logging

# Import typing generics.
from typing import Dict, Any, List

# Import database connection wrapper and query functions.
from zwiggy_dwh.db import ConnectionWrapper, execute_sql, query_scalar

# Create module-level logger.
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# OPERATIONAL HEALTH CHECK RUNNER FUNCTION
# ------------------------------------------------------------------------------

def run_operational_health_check(conn: ConnectionWrapper) -> Dict[str, Any]:
    """
    Executes a comprehensive health check across database layers.
    
    Args:
        conn (ConnectionWrapper): Database connection object.
        
    Returns:
        Dict[str, Any]: Structured operational health report dictionary.
    """
    logger.info("Executing operational health check...")

    health_report: Dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
        "checks": {}
    }

    # 1. SOURCE DATABASE CONNECTIVITY & ROW COUNT CHECK
    try:
        source_order_cnt = query_scalar(conn, "SELECT COUNT(*) FROM app_orders;") or 0
        health_report["checks"]["source_connectivity"] = {
            "status": "HEALTHY",
            "source_order_count": source_order_cnt
        }
    except Exception as e:
        health_report["checks"]["source_connectivity"] = {
            "status": "UNHEALTHY",
            "error": str(e)
        }

    # 2. CONTROL BATCH STATE & LIFECYCLE CHECK
    latest_batch = execute_sql(conn, """
        SELECT dw_batch_id, batch_start_ts_utc, batch_end_ts_utc, status, run_type
        FROM ctl_batch
        ORDER BY dw_batch_id DESC
        LIMIT 1;
    """)
    if latest_batch:
        b_info = latest_batch[0]
        b_status = b_info['status']
        health_report["checks"]["latest_batch_status"] = {
            "status": "HEALTHY" if b_status == "COMPLETED" else "WARNING",
            "dw_batch_id": b_info['dw_batch_id'],
            "batch_status": b_status,
            "start_time": b_info['batch_start_ts_utc'],
            "end_time": b_info['batch_end_ts_utc']
        }
    else:
        health_report["checks"]["latest_batch_status"] = {
            "status": "UNHEALTHY",
            "message": "No batch executions found in ctl_batch."
        }

    # 3. DATA FRESHNESS SLA METRIC CHECK
    max_order_dt = query_scalar(conn, "SELECT MAX(event_ts_utc) FROM fact_order;")
    health_report["checks"]["data_freshness"] = {
        "status": "HEALTHY" if max_order_dt else "WARNING",
        "latest_fact_order_timestamp": max_order_dt or "N/A"
    }

    # 4. RECONCILIATION CONTRACT COMPLIANCE CHECK
    rec_fails = execute_sql(conn, """
        SELECT check_name, source_table, target_table, details
        FROM ctl_reconciliation
        WHERE result = 'FAIL';
    """)
    health_report["checks"]["reconciliation_contracts"] = {
        "status": "HEALTHY" if len(rec_fails) == 0 else "UNHEALTHY",
        "failed_check_count": len(rec_fails),
        "failures": rec_fails
    }

    # 5. DATA QUALITY QUARANTINE RATE CHECK
    gold_orders = query_scalar(conn, "SELECT COUNT(*) FROM fact_order;") or 0
    quarantine_orders = query_scalar(conn, "SELECT COUNT(*) FROM slv_order_quarantine;") or 0
    q_rate_pct = round((quarantine_orders / gold_orders * 100.0), 2) if gold_orders > 0 else 0.0

    health_report["checks"]["quarantine_health"] = {
        "status": "HEALTHY" if q_rate_pct < 5.0 else "WARNING",
        "quarantine_order_count": quarantine_orders,
        "gold_order_count": gold_orders,
        "quarantine_rate_pct": q_rate_pct
    }

    # 6. OVERALL PLATFORM HEALTH SUMMARY EVALUATION
    all_healthy = all(
        c.get("status") in ("HEALTHY", "WARNING") for c in health_report["checks"].values()
    )
    health_report["overall_platform_status"] = "PASSED" if all_healthy else "ACTION_REQUIRED"

    logger.info("Operational Health Check completed. Status: %s", health_report["overall_platform_status"])
    return health_report
