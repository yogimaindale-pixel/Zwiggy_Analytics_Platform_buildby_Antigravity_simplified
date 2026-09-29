# Zwiggy Analytics Platform - Junior Developer Onboarding & Knowledge Transfer (KT)

Welcome to the **Zwiggy Analytics Platform Knowledge Transfer Guide**. This document will guide you through understanding the codebase, running local simulations, and adding new features to the data warehouse.

---

## 1. Codebase Directory Structure

```
src/zwiggy_dwh/
│
├── __init__.py           # Package marker file
├── config.py             # Environment configuration loader (.env)
├── db.py                 # SQLite/DuckDB/Postgres database wrapper & connection retry decorator
├── metadata.py           # 18-table metadata matrix definition dataclasses
├── batch.py              # Batch lifecycle logging (ctl_batch) & incremental watermark advancement
├── seed_source.py        # Operational source generator (app_* tables, 61,777+ synthetic orders)
├── init_db.py            # Complete DDL script initializing Control, Bronze, Silver, Gold layers
├── bronze.py             # Incremental extraction & raw JSON landing engine
├── silver.py             # Business rule transformations, status mapping, & payment retry collapse
├── dq.py                 # Data Quality rule evaluation & quarantine table router
├── gold.py               # SCD Type-2 dimension versioning & Fact table surrogate key lookups
├── reconcile.py          # Cross-layer row count & reconciliation validation runner
├── health.py             # Operational health check diagnostic runner
├── simulate_incremental.py # 10-day incremental data generator and execution simulator
├── pipeline.py           # Master 5-step Medallion pipeline orchestrator
└── cli.py                # Command Line Interface (CLI) entrypoint script
```

---

## 2. Key Concepts Explained for Junior Developers

### A. High Watermark Incremental Extraction
Instead of reading all rows from the source database on every ETL run (which becomes slow and expensive over time), we keep track of the **latest timestamp processed so far**.
* In `ctl_watermark`, we store `watermark_value = '2025-08-03 12:00:00'`.
* On the next run, we only extract rows where `updated_at > '2025-08-03 12:00:00'`.

### B. Medallion Architecture Layers
* **Bronze**: Unaltered raw data stringified as JSON. If the source schema changes, Bronze doesn't break!
* **Silver**: Structured columns parsed out of JSON. Standardized values (`Pending` -> `PENDING`). Anomalies flagged or routed to `slv_order_quarantine`.
* **Gold**: Star-schema model optimized for BI tools (Power BI, Tableau, Looker). Contains Dimension tables (`dim_customer`) and Fact tables (`fact_order`).

### C. SCD Type 2 (Slowly Changing Dimensions)
When a customer updates their address or phone number, we don't overwrite their row in `dim_customer`. Instead:
1. We set the old version's `is_current = FALSE` and set `valid_to_utc = current_timestamp`.
2. We insert a new version with `dw_version_no = dw_version_no + 1`, `is_current = TRUE`, and `valid_from_utc = current_timestamp`.

---

## 3. Step-by-Step Hands-On Tutorial

### Step 1: Run Full Baseline Ingestion
Run the baseline load to populate 61,777 orders through Bronze, Silver, and Gold layers:
```bash
PYTHONPATH=src python3 src/zwiggy_dwh/cli.py run-all
```

### Step 2: Check Operational Health
Inspect platform diagnostic health metrics:
```bash
PYTHONPATH=src python3 src/zwiggy_dwh/cli.py health-check
```

### Step 3: Run 10-Day Incremental Simulation
Simulate 10 consecutive daily batch runs:
```bash
PYTHONPATH=src python3 src/zwiggy_dwh/cli.py simulate-10-days
```

---

## 4. Frequently Asked Questions (FAQ)

**Q: Do I need PostgreSQL or DuckDB installed to run this codebase?**
A: No! The platform defaults to standard SQLite (`zwiggy_warehouse.db`), which requires no external server setup.

**Q: How do I inspect table data directly?**
A: Use SQLite CLI or Python:
```python
import sqlite3
conn = sqlite3.connect("zwiggy_warehouse.db")
print(conn.execute("SELECT COUNT(*) FROM fact_order").fetchone())
```
