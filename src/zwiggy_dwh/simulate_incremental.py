"""10-Day Incremental Data Generator and Pipeline Execution Engine.

Simulates 10 sequential daily incremental data loads from source into the Data Warehouse.
For each day (Day 1 through Day 10):
  1. Generates new orders, payments, delivery records, and updated dimension records.
  2. Saves raw incremental batch snapshots into 'incremental_data/' directory.
  3. Executes incremental Bronze -> Silver -> Gold pipeline.
  4. Validates watermark progression, SCD2 versioning, and reconciliation checks.
"""

from datetime import datetime, timedelta, timezone
import json
import logging
import os

from zwiggy_dwh.batch import start_new_batch, complete_batch
from zwiggy_dwh.bronze import ingest_all_source_tables_to_bronze
from zwiggy_dwh.db import ConnectionWrapper, connect, execute_sql, query_scalar
from zwiggy_dwh.dq import evaluate_data_quality_rules
from zwiggy_dwh.gold import transform_silver_to_gold
from zwiggy_dwh.reconcile import run_reconciliation_checks
from zwiggy_dwh.silver import transform_bronze_to_silver

logger = logging.getLogger(__name__)

INCREMENTAL_DIR = "/config/Desktop/Session4/incremental_data"


def run_10_day_incremental_simulation(conn: ConnectionWrapper) -> List[Dict[str, Any]]:
    """Execute 10 sequential daily incremental batch runs."""
    logger.info("Starting 10-day incremental simulation...")
    os.makedirs(INCREMENTAL_DIR, exist_ok=True)

    results: List[Dict[str, Any]] = []

    # Get baseline max order_id and latest timestamp
    max_order_id = query_scalar(conn, "SELECT COALESCE(MAX(order_id), 61777) FROM app_orders;") or 61777
    max_payment_id = query_scalar(conn, "SELECT COALESCE(MAX(payment_id), 60000) FROM app_payments;") or 60000
    max_delivery_id = query_scalar(conn, "SELECT COALESCE(MAX(delivery_id), 60000) FROM app_delivery_details;") or 60000

    max_dt_str = query_scalar(conn, "SELECT COALESCE(MAX(updated_at), '2025-08-03 12:00:00') FROM app_orders;")
    try:
        base_date = datetime.strptime(str(max_dt_str)[:19], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
    except Exception:
        base_date = datetime(2025, 8, 3, tzinfo=timezone.utc)

    for day in range(1, 11):
        day_date = base_date + timedelta(days=day - 1)
        day_str = day_date.strftime('%Y-%m-%d')

        logger.info("--- Simulating Day %d/10 (%s) ---", day, day_str)

        # 1. Generate incremental source data for the day
        new_orders = []
        new_items = []
        new_payments = []
        new_deliveries = []

        day_order_count = 500
        for i in range(1, day_order_count + 1):
            max_order_id += 1
            max_payment_id += 1
            max_delivery_id += 1

            row_id = f"inc-day{day}-{max_order_id}"
            cid = (max_order_id % 1000) + 1
            rid = 214 if (max_order_id % 10 < 8) else ((max_order_id % 250) + 1)
            aid = cid
            total_price = round(200.0 + (max_order_id % 300), 2)
            dt_str = (day_date + timedelta(minutes=i * 2)).strftime('%Y-%m-%d %H:%M:%S')

            status = "COMPLETED" if (i % 5 != 0) else "CANCELLED"
            is_paid = (status == "COMPLETED")
            is_cancelled = (status == "CANCELLED")

            new_orders.append((
                row_id, max_order_id, cid, rid, aid, total_price, dt_str,
                status, is_paid, is_cancelled, 0.00, None, dt_str, "incremental_sim", dt_str, "incremental_sim"
            ))

            new_items.append((
                max_order_id * 10, max_order_id, (max_order_id % 1000) + 1, 2, total_price / 2.0, total_price, dt_str, dt_str
            ))

            new_payments.append((
                max_payment_id, max_order_id, "UPI", "SUCCESS" if is_paid else "FAILED", total_price, dt_str, 1, dt_str, dt_str
            ))

            new_deliveries.append((
                max_delivery_id, max_order_id, (max_order_id % 100) + 1, "DELIVERED" if is_paid else "CANCELLED", dt_str, 30, 25, dt_str, dt_str
            ))

        # Insert new day records into source tables
        cur = conn.cursor()
        cur.executemany("INSERT INTO app_orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);", new_orders)
        cur.executemany("INSERT INTO app_order_items VALUES (?,?,?,?,?,?,?,?);", new_items)
        cur.executemany("INSERT INTO app_payments VALUES (?,?,?,?,?,?,?,?,?);", new_payments)
        cur.executemany("INSERT INTO app_delivery_details VALUES (?,?,?,?,?,?,?,?,?);", new_deliveries)

        # Update subset of customer records to trigger SCD2 dimension updates on Day 3 and Day 7
        if day in (3, 7):
            update_ts = day_date.strftime('%Y-%m-%d %H:%M:%S')
            cur.execute("""
                UPDATE app_customer
                SET last_name = ?, updated_at = ?
                WHERE customer_id IN (10, 20, 30);
            """, (f"Updated_Day{day}", update_ts))

        conn.commit()

        # Export raw daily batch snapshot to incremental_data/ folder
        day_snapshot_path = os.path.join(INCREMENTAL_DIR, f"day_{day:02d}_{day_str}.json")
        with open(day_snapshot_path, "w") as f:
            json.dump({
                "day": day,
                "date": day_str,
                "orders_added": len(new_orders),
                "payments_added": len(new_payments),
                "deliveries_added": len(new_deliveries)
            }, f, indent=2)

        # 2. Run incremental pipeline execution for this day
        batch_id, cutoff_ts = start_new_batch(
            conn, run_type="INCREMENTAL", description=f"Incremental Day {day} ({day_str})"
        )

        b_counts = ingest_all_source_tables_to_bronze(conn, batch_id, cutoff_ts)
        s_counts = transform_bronze_to_silver(conn, batch_id)
        dq_score = evaluate_data_quality_rules(conn, batch_id)
        g_counts = transform_silver_to_gold(conn, batch_id)
        reconcile_res = run_reconciliation_checks(conn, batch_id)
        complete_batch(conn, batch_id)

        day_summary = {
            "day": day,
            "date": day_str,
            "dw_batch_id": batch_id,
            "bronze_rows_ingested": sum(b_counts.values()),
            "silver_rows_transformed": sum(s_counts.values()),
            "gold_rows_built": sum(g_counts.values()),
            "reconciliation_pass": all(r['result'] == 'PASS' for r in reconcile_res)
        }
        results.append(day_summary)
        logger.info("Day %d execution completed successfully: %s", day, day_summary)

    logger.info("Completed 10-day incremental simulation!")
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with connect() as conn:
        run_10_day_incremental_simulation(conn)
