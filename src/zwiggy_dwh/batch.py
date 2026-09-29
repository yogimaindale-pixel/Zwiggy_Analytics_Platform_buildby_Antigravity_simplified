# ==============================================================================
# ZWIGGY ANALYTICS PLATFORM - BATCH ORCHESTRATION & WATERMARK MANAGEMENT
# ==============================================================================
# File: src/zwiggy_dwh/batch.py
# Purpose: Manages batch lifecycle logging (ctl_batch), incremental watermark tracking
#          (ctl_watermark), audit event logging (ctl_audit_run_log), and batch state
#          transitions (IN_PROGRESS, COMPLETED, FAILED).
# ==============================================================================

# Import UTC datetime utilities.
from datetime import datetime, timezone

# Import standard logging module.
import logging

# Import typing generics.
from typing import Optional, Tuple

# Import database connection wrapper and query runners.
from zwiggy_dwh.db import ConnectionWrapper, execute_sql, query_scalar

# Create module-level logger instance.
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# START NEW BATCH FUNCTION
# ------------------------------------------------------------------------------

def start_new_batch(
    conn: ConnectionWrapper,
    run_type: str = "INCREMENTAL",
    triggered_by: str = "PIPELINE_RUNNER",
    description: str = "Standard pipeline execution"
) -> Tuple[int, datetime]:
    """
    Registers and starts a new execution batch entry in ctl_batch table.
    
    Args:
        conn (ConnectionWrapper): Database connection object.
        run_type (str): Type of ETL run (e.g. FULL_LOAD, INCREMENTAL).
        triggered_by (str): Trigger source identity string.
        description (str): Human-readable batch description.
        
    Returns:
        Tuple[int, datetime]: Tuple containing new unique dw_batch_id and start timestamp object.
    """
    now_utc = datetime.now(timezone.utc)
    now_str = now_utc.strftime('%Y-%m-%d %H:%M:%S')

    cur = conn.cursor()
    # Insert new batch row with status IN_PROGRESS.
    cur.execute("""
        INSERT INTO ctl_batch (batch_start_ts_utc, run_cutoff_ts_utc, run_type, status, triggered_by, batch_description)
        VALUES (?, ?, ?, 'IN_PROGRESS', ?, ?);
    """, (now_str, now_str, run_type, triggered_by, description))
    conn.commit()

    # Retrieve generated auto-increment dw_batch_id.
    batch_id = query_scalar(conn, "SELECT MAX(dw_batch_id) FROM ctl_batch;")
    logger.info("Started new batch dw_batch_id=%d at %s", batch_id, now_str)
    return batch_id, now_utc


# ------------------------------------------------------------------------------
# WATERMARK MANAGEMENT FUNCTIONS
# ------------------------------------------------------------------------------

def get_watermark(conn: ConnectionWrapper, source_table: str) -> Optional[str]:
    """
    Retrieves the latest high watermark value for a given source table.
    
    Args:
        conn (ConnectionWrapper): Database connection object.
        source_table (str): Source table name string.
        
    Returns:
        Optional[str]: High watermark timestamp string, or None if first run.
    """
    row = execute_sql(conn, "SELECT watermark_value FROM ctl_watermark WHERE source_table = ?;", (source_table,))
    if row and row[0].get('watermark_value'):
        return str(row[0]['watermark_value'])
    return None


def update_watermark(
    conn: ConnectionWrapper,
    source_table: str,
    new_watermark: str,
    batch_id: int,
    extract_count: int,
    load_count: int
) -> None:
    """
    Advances high watermark value for a source table after successful landing.
    
    Args:
        conn (ConnectionWrapper): Database connection object.
        source_table (str): Source table name.
        new_watermark (str): New high watermark timestamp value.
        batch_id (int): ETL batch ID.
        extract_count (int): Total rows extracted.
        load_count (int): Total rows landed.
    """
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    cur = conn.cursor()

    existing = execute_sql(conn, "SELECT watermark_id FROM ctl_watermark WHERE source_table = ?;", (source_table,))
    if existing:
        # Update existing watermark row.
        cur.execute("""
            UPDATE ctl_watermark
            SET watermark_value = ?,
                last_successful_batch_id = ?,
                last_successful_run_ts = ?,
                extract_row_count = ?,
                load_row_count = ?,
                current_status = 'SUCCESS',
                updated_ts = ?
            WHERE source_table = ?;
        """, (new_watermark, batch_id, now_str, extract_count, load_count, now_str, source_table))
    else:
        # Insert initial watermark row.
        cur.execute("""
            INSERT INTO ctl_watermark (source_table, watermark_value, last_successful_batch_id, last_successful_run_ts, extract_row_count, load_row_count, current_status, updated_ts)
            VALUES (?, ?, ?, ?, ?, ?, 'SUCCESS', ?);
        """, (source_table, new_watermark, batch_id, now_str, extract_count, load_count, now_str))

    conn.commit()
    logger.info("Advanced watermark for %s to '%s' (batch %d)", source_table, new_watermark, batch_id)


# ------------------------------------------------------------------------------
# BATCH STATUS & AUDIT LOGGING FUNCTIONS
# ------------------------------------------------------------------------------

def complete_batch(conn: ConnectionWrapper, batch_id: int) -> None:
    """
    Updates ctl_batch table status to COMPLETED upon successful pipeline finish.
    """
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    cur = conn.cursor()
    cur.execute("UPDATE ctl_batch SET status = 'COMPLETED', batch_end_ts_utc = ? WHERE dw_batch_id = ?;", (now_str, batch_id))
    conn.commit()
    logger.info("Batch dw_batch_id=%d marked COMPLETED", batch_id)


def fail_batch(conn: ConnectionWrapper, batch_id: int, error_msg: str) -> None:
    """
    Updates ctl_batch table status to FAILED and records error audit log event.
    """
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    cur = conn.cursor()
    cur.execute("UPDATE ctl_batch SET status = 'FAILED', batch_end_ts_utc = ? WHERE dw_batch_id = ?;", (now_str, batch_id))
    conn.commit()
    log_audit_event(conn, batch_id, "BATCH_FAILED", error_msg, severity="ERROR")
    logger.error("Batch dw_batch_id=%d marked FAILED: %s", batch_id, error_msg)


def log_audit_event(
    conn: ConnectionWrapper,
    batch_id: int,
    event_type: str,
    message: str,
    source_table: Optional[str] = None,
    severity: str = "INFO"
) -> None:
    """
    Writes an audit record into ctl_audit_run_log table.
    """
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ctl_audit_run_log (dw_batch_id, source_table, event_type, message, severity, logged_ts)
        VALUES (?, ?, ?, ?, ?, ?);
    """, (batch_id, source_table, event_type, message, severity, now_str))
    conn.commit()
