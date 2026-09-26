# Zwiggy Analytics Platform - Data Warehouse Technical Specification

## 1. Executive Summary & Medallion Architecture
The Zwiggy Analytics Platform implements a metadata-driven Medallion Architecture (Bronze → Silver → Gold) designed for scalable batch processing, full source fidelity preservation, robust data quality enforcement, and BI-ready dimensional analytics.

```
Source System (zwiggy_db)
       │
       ▼ (Source-to-Bronze Ingestion: Watermark Tracking, Idempotent Append)
Bronze Layer (br_*)
       │ Raw JSON & Technical Metadata Preservation
       ▼ (Bronze-to-Silver Cleansing: Status Conformance, Cohort Boundary Tagging, DQ Rules)
Silver Layer (slv_*) ──► Silver Quarantine (slv_*_quarantine)
       │ Cleansed, Conformed, Deduplicated Entities
       ▼ (Silver-to-Gold Transformation: SCD2 Dimensions, As-At Resolution, Facts)
Gold Layer (dim_*, fact_*, mart_*)
```

---

## 2. Layer Contracts & Standards

### Bronze Layer (`bronze`)
- **Fidelity**: Exact representation of source records.
- **Mutability**: Immutable, append-only.
- **Technical Columns**: `dw_ingest_date`, `dw_batch_id`, `dw_ingest_ts_utc`, `dw_source_system`, `dw_source_schema`, `dw_source_table`, `payload_json`, `source_primary_key`.

### Silver Layer (`silver`)
- **Cleansing**: Typed attributes, normalized strings, conformed vocabularies.
- **Cohort Tagging**: `COHORT_A` (order_id ≤ 10,928) vs `COHORT_B` (order_id > 10,928).
- **Business Rules**: BR-R1 through BR-R11 applied.
- **Anomalies**: Identified and flagged via `dq_flag_*` boolean columns.
- **Quarantine Subschema**: Failed/disputed records stored in `slv_*_quarantine`.

### Gold Layer (`gold`)
- **Dimensional Model**: 14 SCD2 dimensions with surrogate keys (`*_sk`), `valid_from_utc`, `valid_to_utc`, `is_current`, `dw_row_hash`.
- **Facts**: 6 fact tables with as-at resolution (`fact_event_ts_utc` within validity interval) and fallback surrogate key `-1` when dimension member is missing.
- **Marts**: Pre-aggregated daily marts (`mart_order_daily`, `mart_revenue_daily`).

---

## 3. Control Layer & Orchestration Schema (`control`)
- `ctl_batch`: Tracks execution runs, cutoff timestamps, and run types (`FULL_LOAD`, `INCREMENTAL`, `REPLAY`).
- `ctl_table_config`: 18-table metadata matrix driving ingestion strategies.
- `ctl_watermark`: Tracks high-watermark checkpoints for incremental loading.
- `ctl_reconciliation`: Stores cross-layer validation check outputs (RC-1 to RC-10).
- `ctl_dq_rule`: Stores data quality rule execution metadata.
- `ctl_audit_run_log`: Audit trail for all pipeline execution events.
- `ctl_audit_source_extract`: Manifest of source extractions including checksums and min/max watermarks.
