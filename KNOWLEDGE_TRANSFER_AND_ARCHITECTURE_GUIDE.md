# Zwiggy Analytics Platform - Comprehensive Knowledge Transfer & Step-by-Step Documentation Guide

## 1. Executive Summary & Architecture Overview

The **Zwiggy Analytics Platform** (`Zwiggy-Antigravity`) is a enterprise-grade **Medallion Data Warehouse** implemented in Python and SQL. It ingests, cleanses, transforms, models, and reconciles data across 18 source tables into three distinct architectural layers:

```
+-----------------------------------------------------------------------------------+
|                                  SOURCE DATABASE                                  |
|   18 Tables | Cohort A (<=10,928 human status) | Cohort B (>10,928 machine status)    |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                                  BRONZE LAYER                                     |
|   Raw Source Extracts | Append-Only | Tech Metadata (dw_batch_id, dw_ingest_ts_utc)|
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                                  SILVER LAYER                                     |
|   Conformed Statuses | Cohort Boundaries | Collapsed Retries | Quarantine Routing |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                                   GOLD LAYER                                      |
|   14 SCD2 Dimensions | 6 Fact Tables | 2 Aggregate Marts | DQ Scorecard Mart      |
+-----------------------------------------------------------------------------------+
```

---

## 2. Step-by-Step Pipeline Execution Guide

Every step in the pipeline is exposed via the unified console command `zwiggy-dwh`.

### Step 1: Seed Source Database
- **Command**: `zwiggy-dwh seed-source`
- **Module**: `zwiggy_dwh.seed_source`
- **Description**: Creates 18 source tables in the source schema (`app_*`) and populates 336,751 total records across Cohorts A and B, including 13,027 intentional data quality anomalies (null total prices, status contradictions, payment retry attempts).

### Step 2: Initialize Warehouse Control & Schemas
- **Command**: `zwiggy-dwh init-db`
- **Module**: `zwiggy_dwh.init_db`
- **Description**: Creates 5 PostgreSQL/SQLite schemas (`control`, `bronze`, `silver`, `silver_quarantine`, `gold`), 7 control tables (`ctl_batch`, `ctl_table_config`, `ctl_watermark`, `ctl_reconciliation`, `ctl_dq_rule`, `ctl_audit_run_log`, `ctl_audit_source_extract`), and populates reference tables (`silver_ref_status_map`, `silver_ref_cohort_rule`, `silver_ref_dq_rule_definition`).

### Step 3: Source-to-Bronze Ingestion
- **Command**: `zwiggy-dwh ingest`
- **Module**: `zwiggy_dwh.bronze`
- **Description**: Evaluates the 18-table ingestion strategy matrix (`TIMESTAMP_WATERMARK`, `CREATED_DATE_WATERMARK`, `FULL_SNAPSHOT`, `FULL_REFERENCE`), extracts raw data incrementally using high-watermarks from `ctl_watermark`, appends standard technical metadata, writes checksum manifests to `ctl_audit_source_extract`, and advances watermarks upon success.

### Step 4: Bronze-to-Silver Cleansing & Status Conformance
- **Command**: `zwiggy-dwh transform` (Silver Phase)
- **Module**: `zwiggy_dwh.silver`
- **Description**: Normalizes Cohort A human status values ("Pending", "Completed", "Cancelled") and Cohort B machine codes ("PENDING", "COMPLETED", "CANCELLED") into conformed codes (`COMPLETED`, `CANCELLED`, `PENDING`). Tags records with `cohort_boundary` (`COHORT_A` vs `COHORT_B`), flags anomalies (`dq_flag_pending_but_paid`, `dq_flag_cancel_mismatch`), and collapses payment attempt retries down to the final state.

### Step 5: Data Quality Evaluation & Quarantine Routing
- **Command**: `zwiggy-dwh scorecard`
- **Module**: `zwiggy_dwh.dq`
- **Description**: Evaluates 40+ DQ rules defined in `ctl_dq_rule`. Records violating mandatory rules are moved to `slv_*_quarantine`. Computes quality metrics (completeness %, conformance %, quarantine count) and populates `gold.mart_dq_scorecard`.

### Step 6: Silver-to-Gold Star Schema Modeling
- **Command**: `zwiggy-dwh transform` (Gold Phase)
- **Module**: `zwiggy_dwh.gold`
- **Description**:
  - Builds **14 SCD Type 2 Dimensions**: Assigns surrogate keys (`*_sk`), maintains historical versions (`valid_from_utc`, `valid_to_utc`, `is_current`), detects changes via MD5 row hashes (`dw_row_hash`), and inserts fallback member `-1`.
  - Builds **6 Fact Tables**: Resolves dimension surrogate keys using as-at event date matching. Falls back to `-1` for late-arriving dimensions.
  - Builds **2 Daily Aggregation Marts**: `mart_order_daily` and `mart_revenue_daily`.

### Step 7: Mandatory Cross-Layer Reconciliation
- **Command**: `zwiggy-dwh reconcile`
- **Module**: `zwiggy_dwh.reconcile`
- **Description**: Evaluates 10 mandatory reconciliation contracts (RC-1 through RC-10) checking row counts, financial sum totals, and grain integrity across Bronze, Silver, and Gold layers. Results are logged to `ctl_reconciliation`.

### Step 8: Operational Health Check
- **Command**: `zwiggy-dwh health-check`
- **Module**: `zwiggy_dwh.health`
- **Description**: Performs automated diagnostics on source connectivity, latest batch execution state, data freshness lag, reconciliation failures, and quarantine rates.

### Step 9: 10-Day Incremental Simulation
- **Command**: `zwiggy-dwh simulate-10-days`
- **Module**: `zwiggy_dwh.simulate_incremental`
- **Description**: Generates 10 days of new daily orders, payments, delivery details, and customer updates in `incremental_data/`, executing 10 sequential incremental batches and verifying watermark progression.

### Step 10: Complete End-to-End Execution
- **Command**: `zwiggy-dwh run-all`
- **Module**: `zwiggy_dwh.pipeline`
- **Description**: Sequentially executes Steps 1 through 8 in a single atomic pipeline run.

---

## 3. Codebase Architecture & Module Catalog

| File / Path | Responsibilities | Key Functions / Classes |
|-------------|------------------|-------------------------|
| [src/zwiggy_dwh/config.py](file:///config/Desktop/Session4/src/zwiggy_dwh/config.py) | Configuration settings & masked secret display | `Settings`, `DbTarget`, `get_settings()` |
| [src/zwiggy_dwh/db.py](file:///config/Desktop/Session4/src/zwiggy_dwh/db.py) | Multi-engine connection wrapper (SQLite/DuckDB/Postgres) | `ConnectionWrapper`, `connect()`, `execute_sql()`, `query_scalar()` |
| [src/zwiggy_dwh/seed_source.py](file:///config/Desktop/Session4/src/zwiggy_dwh/seed_source.py) | Source database bootstrapper & synthetic data generator | `seed_source_database()` |
| [src/zwiggy_dwh/init_db.py](file:///config/Desktop/Session4/src/zwiggy_dwh/init_db.py) | DDL setup for schemas, control tables, reference data, and layers | `initialize_dwh_foundation()` |
| [src/zwiggy_dwh/metadata.py](file:///config/Desktop/Session4/src/zwiggy_dwh/metadata.py) | Ingestion matrix definitions for 18 source tables | `TABLE_CONFIGS` |
| [src/zwiggy_dwh/batch.py](file:///config/Desktop/Session4/src/zwiggy_dwh/batch.py) | Batch lifecycle tracking & watermark management | `start_new_batch()`, `complete_batch()`, `update_watermark()` |
| [src/zwiggy_dwh/bronze.py](file:///config/Desktop/Session4/src/zwiggy_dwh/bronze.py) | Incremental Source-to-Bronze extraction engine | `ingest_all_source_tables_to_bronze()` |
| [src/zwiggy_dwh/silver.py](file:///config/Desktop/Session4/src/zwiggy_dwh/silver.py) | Silver layer status conformance, cohort tagging, & payment collapse | `transform_bronze_to_silver()` |
| [src/zwiggy_dwh/dq.py](file:///config/Desktop/Session4/src/zwiggy_dwh/dq.py) | 40+ Data Quality rule evaluation & quarantine routing | `evaluate_data_quality_rules()` |
| [src/zwiggy_dwh/gold.py](file:///config/Desktop/Session4/src/zwiggy_dwh/gold.py) | SCD2 dimensions, fact tables, & daily aggregation marts | `transform_silver_to_gold()` |
| [src/zwiggy_dwh/reconcile.py](file:///config/Desktop/Session4/src/zwiggy_dwh/reconcile.py) | 10 cross-layer reconciliation contract checkers (RC-1..10) | `run_reconciliation_checks()` |
| [src/zwiggy_dwh/health.py](file:///config/Desktop/Session4/src/zwiggy_dwh/health.py) | Operational health diagnostic engine | `run_operational_health_check()` |
| [src/zwiggy_dwh/simulate_incremental.py](file:///config/Desktop/Session4/src/zwiggy_dwh/simulate_incremental.py) | 10-day incremental data simulation engine | `run_10_day_incremental_simulation()` |
| [src/zwiggy_dwh/pipeline.py](file:///config/Desktop/Session4/src/zwiggy_dwh/pipeline.py) | Master pipeline orchestrator | `run_full_etl_pipeline()` |
| [src/zwiggy_dwh/cli.py](file:///config/Desktop/Session4/src/zwiggy_dwh/cli.py) | Console CLI entry point | `main()` |

---

## 4. Analytical Developer Onboarding & BI Query Examples

### Querying SCD2 Dimensions with Facts
To analyze orders with historical customer attributes at the exact time the order took place:

```sql
SELECT 
  f.order_id,
  f.order_date,
  f.total_price,
  c.customer_id,
  c.first_name,
  c.last_name,
  c.email,
  r.restaurant_name
FROM gold.fact_order f
JOIN gold.dim_customer c ON f.customer_sk = c.customer_sk
JOIN gold.dim_restaurant r ON f.restaurant_sk = r.restaurant_sk
WHERE f.order_date >= '2025-01-01'
ORDER BY f.order_date DESC;
```

### Filtering Outlier Data (Restaurant 214)
Restaurant 214 represents synthetic testing data (87.1% of order volume). For core business analytics, filter out Restaurant 214:

```sql
SELECT 
  order_date,
  COUNT(order_id) as organic_order_count,
  SUM(total_price) as organic_revenue
FROM gold.fact_order
WHERE restaurant_id != 214
GROUP BY order_date
ORDER BY order_date DESC;
```

---

## 5. Complete Documentation Catalog

1. [README.md](file:///config/Desktop/Session4/README.md): Quick start guide and project introduction.
2. [DWH_TECHNICAL_SPECIFICATION.md](file:///config/Desktop/Session4/DWH_TECHNICAL_SPECIFICATION.md): Medallion architecture specification and control table DDLs.
3. [TABLE_INGESTION_CONFIGURATION.csv](file:///config/Desktop/Session4/TABLE_INGESTION_CONFIGURATION.csv): Ingestion matrix definitions for 18 source tables.
4. [DATA_DICTIONARY.md](file:///config/Desktop/Session4/DATA_DICTIONARY.md): Complete field-level data dictionary.
5. [OPERATIONAL_RUNBOOK.md](file:///config/Desktop/Session4/OPERATIONAL_RUNBOOK.md): Operational procedures & execution runbook.
6. [OPERATIONAL_HANDOFF_AND_TROUBLESHOOTING_GUIDE.md](file:///config/Desktop/Session4/OPERATIONAL_HANDOFF_AND_TROUBLESHOOTING_GUIDE.md): Operational handoff, incident playbooks, FAQ, and maintenance runbook.
7. [KNOWLEDGE_TRANSFER_AND_ARCHITECTURE_GUIDE.md](file:///config/Desktop/Session4/KNOWLEDGE_TRANSFER_AND_ARCHITECTURE_GUIDE.md): This comprehensive KT and step-by-step documentation guide.
