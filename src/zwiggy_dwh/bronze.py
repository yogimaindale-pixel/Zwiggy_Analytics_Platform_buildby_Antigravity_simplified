"""Source-to-Bronze Incremental Ingestion Engine.

Extracts data from 18 source tables in zwiggy_db using metadata-driven strategies,
lands raw data into Bronze layer with source fidelity preserved, appends standard
technical metadata columns, writes extraction manifests, and advances watermarks.
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
from typing import Dict, List, Optional, Tuple

from zwiggy_dwh.batch import get_watermark, update_watermark, log_audit_event
from zwiggy_dwh.db import ConnectionWrapper, execute_sql, query_scalar
from zwiggy_dwh.metadata import get_classification_matrix, TableClassification

logger = logging.getLogger(__name__)


def ingest_all_source_tables_to_bronze(
    conn: ConnectionWrapper,
    batch_id: int,
    cutoff_ts: datetime
) -> Dict[str, int]:
    """Ingest all active source tables into Bronze layer."""
    logger.info("Starting Source-to-Bronze ingestion for batch_id=%d...", batch_id)
    configs = get_classification_matrix()
    summary_counts: Dict[str, int] = {}

    ingest_date_str = cutoff_ts.strftime('%Y-%m-%d')
    ingest_ts_str = cutoff_ts.strftime('%Y-%m-%d %H:%M:%S')

    for cfg in configs:
        count = ingest_single_table_to_bronze(conn, cfg, batch_id, ingest_date_str, ingest_ts_str)
        summary_counts[cfg.source_table] = count

    log_audit_event(
        conn, batch_id, "BRONZE_INGESTION_COMPLETE",
        f"Ingested {sum(summary_counts.values())} rows across {len(summary_counts)} tables."
    )
    return summary_counts


def ingest_single_table_to_bronze(
    conn: ConnectionWrapper,
    cfg: TableClassification,
    batch_id: int,
    ingest_date_str: str,
    ingest_ts_str: str
) -> int:
    """Ingest a single table from source to Bronze layer."""
    source_table = cfg.source_table
    target_bronze = cfg.target_bronze_table
    strategy = cfg.ingestion_strategy
    pk_col = cfg.primary_key_column
    watermark_col = cfg.watermark_column

    last_watermark = get_watermark(conn, source_table)

    # Build extraction query based on strategy
    query = f"SELECT * FROM {source_table}"
    params: List[Any] = []

    if strategy in ("TIMESTAMP_WATERMARK", "CREATED_DATE_WATERMARK") and watermark_col:
        if last_watermark:
            query += f" WHERE {watermark_col} > ?"
            params.append(last_watermark)

    start_time = datetime.now(timezone.utc)
    rows = execute_sql(conn, query, params if params else None)
    end_time = datetime.now(timezone.utc)

    extracted_count = len(rows)
    min_wm: Optional[str] = None
    max_wm: Optional[str] = None

    if extracted_count > 0 and watermark_col:
        wm_vals = [str(r[watermark_col]) for r in rows if r.get(watermark_col) is not None]
        if wm_vals:
            min_wm = min(wm_vals)
            max_wm = max(wm_vals)

    # Idempotent write: delete existing rows for this batch_id in bronze
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {target_bronze} WHERE dw_batch_id = ?;", (batch_id,))

    # Insert into bronze table
    records_to_insert = []
    for r in rows:
        pk_val = str(r[pk_col]) if r.get(pk_col) is not None else str(r.get('row_id', ''))
        payload_str = json.dumps(r, default=str)
        records_to_insert.append((
            ingest_date_str, batch_id, ingest_ts_str,
            "zwiggy_db", "app", source_table, payload_str, pk_val
        ))

    if records_to_insert:
        cur.executemany(f"""
            INSERT INTO {target_bronze} (
                dw_ingest_date, dw_batch_id, dw_ingest_ts_utc,
                dw_source_system, dw_source_schema, dw_source_table,
                payload_json, source_primary_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, records_to_insert)

    conn.commit()

    # Write audit manifest
    checksum_str = f"{source_table}:{extracted_count}:{min_wm}:{max_wm}"
    checksum_hash = hashlib.md5(checksum_str.encode('utf-8')).hexdigest()

    cur.execute("""
        INSERT INTO ctl_audit_source_extract (
            dw_batch_id, source_table, extract_predicate, extract_row_count,
            extract_start_ts, extract_end_ts, min_watermark_value, max_watermark_value,
            checksum_hash, extract_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'SUCCESS');
    """, (
        batch_id, source_table, query, extracted_count,
        start_time.strftime('%Y-%m-%d %H:%M:%S'), end_time.strftime('%Y-%m-%d %H:%M:%S'),
        min_wm, max_wm, checksum_hash
    ))
    conn.commit()

    # Update watermark if max_wm was found or retain last_watermark
    new_wm = max_wm or last_watermark or ingest_ts_str
    update_watermark(conn, source_table, new_wm, batch_id, extracted_count, extracted_count)

    logger.info("Bronze landed %s -> %s: %d rows (batch %d)", source_table, target_bronze, extracted_count, batch_id)
    return extracted_count
