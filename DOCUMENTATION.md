# Zwiggy Analytics Platform - Technical Specification & Requirements Guide

This document outlines the detailed technical specifications, architecture decisions, database schemas, business logic, and code runflows for the **Zwiggy Analytics Platform**.

---

## 1. Requirements Overview

The Zwiggy Analytics Platform processes operational food delivery data across 18 source tables into a central Medallion Data Warehouse:
* **Bronze Layer**: Append-only raw landing layer holding unparsed JSON payloads with technical ingestion metadata (`dw_batch_id`, `dw_ingest_date`, `source_primary_key`).
* **Silver Layer**: Cleaned, typed, status-conformed layer resolving legacy vs modern vocabulary differences (Cohort A vs Cohort B) and isolating data quality anomalies into quarantine tables (`slv_*_quarantine`).
* **Gold Layer**: Dimensional star-schema layer containing 14 Slowly Changing Dimensions Type 2 (SCD2), 6 Fact tables with as-at surrogate key lookups, and 2 pre-aggregated daily revenue marts.

---

## 2. Source Classification & Ingestion Matrix (18 Tables)

| Source Table Name | Ingestion Strategy | Watermark Column | Business Key | Target Bronze | Target Silver | Target Gold |
|---|---|---|---|---|---|---|
| `app_orders` | INCREMENTAL_WATERMARK | `updated_at` | `order_id` | `br_orders` | `slv_order` | `fact_order` |
| `app_order_items` | INCREMENTAL_WATERMARK | `updated_at` | `order_item_id` | `br_order_items` | `slv_order_item` | `fact_order_item` |
| `app_payments` | INCREMENTAL_WATERMARK | `updated_at` | `payment_id` | `br_payments` | `slv_payment` | `fact_payment` |
| `app_delivery_details` | INCREMENTAL_WATERMARK | `updated_at` | `delivery_id` | `br_delivery_details` | `slv_delivery` | `fact_delivery` |
| `app_reviews` | INCREMENTAL_WATERMARK | `created_at` | `review_id` | `br_reviews` | `slv_review` | `fact_review` |
| `app_cart` | FULL_SNAPSHOT | N/A | `cart_id` | `br_cart` | `slv_cart` | N/A |
| `app_cart_items` | FULL_SNAPSHOT | N/A | `cart_item_id` | `br_cart_items` | `slv_cart_item` | N/A |
| `app_customer` | INCREMENTAL_WATERMARK | `updated_at` | `customer_id` | `br_customer` | `slv_customer` | `dim_customer` |
| `app_user_address` | INCREMENTAL_WATERMARK | `updated_at` | `address_id` | `br_user_address` | `slv_address` | `dim_address` |
| `app_restaurant` | INCREMENTAL_WATERMARK | `updated_at` | `restaurant_id` | `br_restaurant` | `slv_restaurant` | `dim_restaurant` |
| `app_menu_item` | INCREMENTAL_WATERMARK | `updated_at` | `menu_item_id` | `br_menu_item` | `slv_menu_item` | `dim_menu_item` |
| `app_delivery_partner` | INCREMENTAL_WATERMARK | `updated_at` | `delivery_partner_id` | `br_delivery_partner` | `slv_delivery_partner` | `dim_delivery_partner` |
| `app_cuisines` | FULL_SNAPSHOT | N/A | `cuisine_id` | `br_cuisines` | `slv_cuisine` | `dim_cuisine` |
| `app_gender` | FULL_SNAPSHOT | N/A | `id` | `br_gender` | `slv_gender` | N/A |
| `app_order_cancellation` | FULL_SNAPSHOT | N/A | `cancellation_id` | `br_order_cancellation` | N/A | N/A |
| `app_restaurant_cuisine` | FULL_SNAPSHOT | N/A | `restaurant_cuisine_id` | `br_restaurant_cuisine` | N/A | `dim_restaurant_cuisine` |
| `app_restaurant_owner` | INCREMENTAL_WATERMARK | `updated_at` | `owner_id` | `br_restaurant_owner` | N/A | `dim_restaurant_owner` |
| `app_refunds` | FULL_SNAPSHOT | N/A | `refund_id` | `br_refunds` | N/A | N/A |

---

## 3. Business Rules Specification

* **BR-R1 (High Watermark Extraction)**: Extract records where `watermark_column > last_watermark_value AND watermark_column <= cutoff_ts`.
* **BR-R2 (Cohort Boundary Tagging)**: Orders with `order_id <= 10928` are tagged `COHORT_A` (human-entered statuses). Orders with `order_id > 10928` are tagged `COHORT_B` (machine-entered statuses).
* **BR-R5 (Payment Retry Collapse)**: Collapse multiple payment attempts per `order_id` into a single canonical payment summary record.
* **BR-R8 (Status Vocabulary Normalization)**: Map human vocabulary (`Pending`, `Completed`, `Cancelled`, `Delivered`, `PAID`) to conformed values (`PENDING`, `COMPLETED`, `CANCELLED`).
* **BR-R11 (SCD Type 2 Dimension Versioning)**: Track history of dimension attribute changes by expiring old versions (`is_current = 0`, `valid_to_utc = event_ts`) and creating new versions (`dw_version_no + 1`, `is_current = 1`).

---

## 4. Reconciliation Contracts (RC-1 to RC-3)

* **RC-1 (Extract vs Bronze)**: `ctl_audit_source_extract.extract_row_count == COUNT(br_*)`
* **RC-2 (Bronze vs Silver + Quarantine)**: `COUNT(br_orders) == COUNT(slv_order) + COUNT(slv_order_quarantine)`
* **RC-3 (Silver vs Gold Facts)**: `COUNT(slv_order) == COUNT(fact_order)`

---

## 5. End-to-End Pipeline Execution Flow

```
[CLI / Python Entrypoint]
       │
       ▼
1. seed_source.py ──────► Seed 18 source tables (61,777 raw orders)
       │
       ▼
2. init_db.py     ──────► DDL setup for Control, Bronze, Silver, Gold schemas
       │
       ▼
3. bronze.py      ──────► Incremental extraction into br_* tables (JSON landing)
       │
       ▼
4. silver.py      ──────► Status mapping, Cohort tagging, Payment retry collapse
       │
       ▼
5. dq.py          ──────► DQ rule evaluation & quarantine isolation
       │
       ▼
6. gold.py        ──────► SCD2 dimension history building & Fact SK resolution
       │
       ▼
7. reconcile.py   ──────► Verify row counts and data contracts across layers
```
