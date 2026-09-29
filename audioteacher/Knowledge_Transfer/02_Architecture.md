# 🏗️ 02. Medallion Architecture & Data Warehouse Technical Specification

Welcome to **Lesson 02: Architecture & System Design** of the Zwiggy Analytics Platform Data Warehouse!

---

## 1. The Medallion Data Architecture

The Zwiggy Analytics Data Warehouse implements the **Medallion Data Architecture**, an industry-standard multi-layer pattern for data lakehouses and data warehouses.

```
+-----------------------------------------------------------------------------------+
|                               OLTP SOURCE DATABASE                                |
|  Tables: app_customer, app_orders, app_order_items, app_payments, app_delivery... |
+-----------------------------------------------------------------------------------+
                                          |
                                          | Batch / Watermark Extraction
                                          v
+-----------------------------------------------------------------------------------+
| BRONZE LAYER (br_*) - RAW LANDING LAYER                                          |
| Purpose: Land raw data as close to source as possible without transformation.    |
| Schemas: Raw JSON payload string, source key, dw_batch_id, dw_extracted_at.      |
| Ingestion Pattern: Append-only incremental delta landing.                        |
+-----------------------------------------------------------------------------------+
                                          |
                                          | Cleansing & Transformation Pipeline
                                          v
+-----------------------------------------------------------------------------------+
| SILVER LAYER (sl_*) - CLEANED & CONFORMED LAYER                                   |
| Purpose: Standardized relational entities, clean data types, PII masking.        |
| Features: Business surrogate keys, deduplicated records, null replacement.        |
| Quarantine: Corrupted / invalid rows routed to sl_quarantine with error reason.   |
+-----------------------------------------------------------------------------------+
                                          |
                                          | Dimensional Modeling & Aggregation
                                          v
+-----------------------------------------------------------------------------------+
| GOLD LAYER (gd_*) - STAR SCHEMA & ANALYTICAL MARTS                                |
| Purpose: Business Intelligence, executive reporting, and machine learning features|
| Features: 14 SCD Type 2 Dimensions (effective_from, effective_to, is_current),   |
|           6 Fact Tables (FactOrders, FactPayments, etc.), 2 Business Marts.        |
+-----------------------------------------------------------------------------------+
```

---

## 2. Infrastructure Control Tables (`ctl_*`)

The architecture relies on five system control tables to guarantee idempotent batch execution, change data capture (CDC), data quality governance, and operational auditing.

### 2.1 `ctl_batch_log` (Batch Execution Tracking)
Tracks every pipeline batch run from start to completion.
```sql
CREATE TABLE ctl_batch_log (
    dw_batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_status TEXT NOT NULL CHECK (batch_status IN ('STARTED', 'COMPLETED', 'FAILED')),
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    total_records_processed INTEGER DEFAULT 0,
    error_message TEXT
);
```

### 2.2 `ctl_watermark` (Incremental CDC High-Watermark Tracker)
Maintains the last successfully extracted timestamp for incremental delta loads per table.
```sql
CREATE TABLE ctl_watermark (
    table_name TEXT PRIMARY KEY,
    last_watermark_value TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_batch_id INTEGER REFERENCES ctl_batch_log(dw_batch_id)
);
```

### 2.3 `ctl_table_config` (Table Ingestion Configuration Matrix)
Defines the ingestion strategy and primary keys for all 18 tables.
```sql
CREATE TABLE ctl_table_config (
    table_name TEXT PRIMARY KEY,
    source_table_name TEXT NOT NULL,
    ingestion_strategy TEXT NOT NULL CHECK (ingestion_strategy IN ('FULL_RELOAD', 'INCREMENTAL_DELTA')),
    watermark_column TEXT,
    primary_key_column TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);
```

### 2.4 `ctl_dq_rules` (Data Quality Rules Registry)
Stores configurable validation rules evaluated during the Silver phase.
```sql
CREATE TABLE ctl_dq_rules (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name TEXT NOT NULL,
    target_table TEXT NOT NULL,
    rule_type TEXT NOT NULL CHECK (rule_type IN ('NOT_NULL', 'UNIQUE', 'FOREIGN_KEY', 'RANGE_BOUND')),
    column_name TEXT NOT NULL,
    rule_sql TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('WARNING', 'CRITICAL_QUARANTINE'))
);
```

### 2.5 `ctl_audit_log` (Operational Event Audit Log)
Logs fine-grained execution events, timings, and exceptions.
```sql
CREATE TABLE ctl_audit_log (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    dw_batch_id INTEGER REFERENCES ctl_batch_log(dw_batch_id),
    event_type TEXT NOT NULL,
    table_name TEXT,
    records_affected INTEGER DEFAULT 0,
    execution_time_ms INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 3. Dimensional Modeling: Star Schema Architecture

The Gold layer uses **Dimensional Modeling** designed by Ralph Kimball, consisting of Conformed Dimensions, Fact Tables, and Business Marts.

```
                        +----------------------+
                        |   gd_dim_customer    |
                        | (SCD Type 2 Dim)     |
                        +----------------------+
                                   | 1
                                   |
                                   | N
                        +----------------------+
                        |    gd_fact_orders    |
                        | (Central Fact Table) |
                        +----------------------+
                        /          |           \
                       /           |            \
                     1/           1|             \1
                     v             v              v
      +------------------+ +---------------+ +--------------------+
      |gd_dim_restaurant | | gd_dim_driver | |   gd_dim_date      |
      | (SCD2 Dim)       | | (SCD2 Dim)    | | (Role-Playing Dim)|
      +------------------+ +---------------+ +--------------------+
```

### 3.1 Slowly Changing Dimensions (SCD Type 2)
To preserve historical accuracy, key dimensions like `gd_dim_customer` and `gd_dim_restaurant` implement **SCD Type 2**. When an attribute changes (e.g., customer updates city or address):
1. The existing active record has its `effective_to` date set to the current timestamp and `is_current` set to `0`.
2. A new dimension record is inserted with a new surrogate key (`customer_sk`), `effective_from = current_timestamp`, `effective_to = '9999-12-31'`, and `is_current = 1`.

---

## 4. Watermarking & Incremental Loading Mechanics

The incremental extraction algorithm guarantees zero data loss and prevents duplicate processing using the following logic:

```python
# 1. Retrieve last high-watermark timestamp for source_table from ctl_watermark
last_watermark = get_watermark(cursor, source_table)  # e.g., '2025-08-04 12:00:00'

# 2. Extract delta records created/updated after last_watermark up to current batch execution time
query = f"""
    SELECT * FROM {source_table} 
    WHERE updated_at > '{last_watermark}' AND updated_at <= '{current_batch_timestamp}'
"""

# 3. Append delta rows into Bronze table br_{table} with dw_batch_id and raw_payload JSON
land_into_bronze(cursor, source_table, delta_rows, dw_batch_id)

# 4. Advance high-watermark in ctl_watermark to current_batch_timestamp upon batch completion
update_watermark(cursor, source_table, max_updated_at, dw_batch_id)
```
