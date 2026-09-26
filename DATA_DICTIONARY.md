# Zwiggy Data Warehouse Data Dictionary

## 1. Bronze Layer (`br_*`)
All 18 Bronze tables share standard technical columns plus a JSON payload representing the exact raw source record:
- `dw_ingest_date` (DATE): Business ingestion date.
- `dw_batch_id` (BIGINT): Pipeline execution batch identifier.
- `dw_ingest_ts_utc` (TIMESTAMP): Extraction timestamp in UTC.
- `dw_source_system` (VARCHAR): Always 'zwiggy_db'.
- `dw_source_schema` (VARCHAR): Always 'app'.
- `dw_source_table` (VARCHAR): Source table name (e.g. 'app_orders').
- `payload_json` (TEXT): Raw source row serialized as JSON.
- `source_primary_key` (VARCHAR): Source primary key value.

---

## 2. Silver Layer (`slv_*`)
Cleansed entities with conformed status values, cohort tags, and data quality flags:
- `slv_order`:
  * `order_id` (BIGINT): Business key.
  * `customer_id` (BIGINT), `restaurant_id` (BIGINT), `address_id` (BIGINT).
  * `conformed_status` (VARCHAR): 'PENDING', 'COMPLETED', 'CANCELLED'.
  * `dw_source_cohort` (VARCHAR): 'COHORT_A' (order_id ≤ 10,928) or 'COHORT_B' (order_id > 10,928).
  * `dq_flag_pending_but_paid` (BOOLEAN): True if order is pending but marked paid.
  * `dq_flag_cancel_mismatch` (BOOLEAN): True if cancellation flag contradicts status.
- `slv_payment_attempt`: All payment attempts including retries.
- `slv_payment`: Deduplicated, collapsed payment records (one final payment per order).
- `slv_customer`, `slv_restaurant`, `slv_menu_item`, `slv_delivery_partner`.

---

## 3. Gold Layer (`dim_*`, `fact_*`, `mart_*`)

### Dimensions (SCD2)
- `dim_customer`, `dim_restaurant`, `dim_menu_item`, `dim_delivery_partner`, `dim_cuisine`:
  * `sk` (BIGINT): Auto-incremented surrogate key.
  * `business_key` (VARCHAR): Natural entity key.
  * `dw_version_no` (INT): Version sequence (1, 2, ...).
  * `dw_row_hash` (VARCHAR): MD5 hash of entity attributes for change detection.
  * `is_current` (BOOLEAN): 1 if active current version, 0 if expired.
  * `valid_from_utc` (TIMESTAMP): Validity start.
  * `valid_to_utc` (TIMESTAMP): Validity end (NULL if current).

### Facts
- `fact_order`:
  * `event_id` (BIGINT): Fact surrogate key.
  * `dw_batch_id` (BIGINT): Ingestion batch.
  * `event_ts_utc` (TIMESTAMP): Order timestamp.
  * `customer_sk` (BIGINT), `restaurant_sk` (BIGINT), `delivery_partner_sk` (BIGINT): Dimension surrogate key references (-1 if fallback).
  * `amount` (NUMERIC): Order total.
  * `dq_flag_dim_fallback` (BOOLEAN): True if dimension surrogate key fallback occurred.

### Aggregate Marts
- `mart_order_daily`: Daily order volume, completion rates, cancelled orders, gross revenue, AOV.
- `mart_revenue_daily`: Daily gross revenue, net revenue, tax, Cohort A revenue, Cohort B revenue.
