# 📄 Line-by-Line Code Breakdown: `src/zwiggy_dwh/init_db.py`

**File Name**: `src/zwiggy_dwh/init_db.py`  
**Total Lines**: 425 Lines  
**Primary Purpose**: Data Warehouse foundation builder. Executes DDL statements creating control schemas (`ctl_*`), 18 Bronze raw landing tables (`br_*`), 18 Silver clean tables (`sl_*`), 18 Silver quarantine tables (`sl_*_quarantine`), 14 Gold SCD Type 2 dimensions (`gd_dim_*`), 6 Gold fact tables (`gd_fact_*`), and 2 Gold business analytical marts (`gd_mart_*`).

---

## 📜 Key Sections & Line Walkthrough

* **Lines 1–28**: Imports and logger setup. Imports `connect` and `execute_sql` from `zwiggy_dwh.db`.
* **Line 30**: `def initialize_dwh_foundation(db_path: Optional[Path] = None):` - Main entrypoint for DWH schema initialization.
* **Lines 31–45**: Establishes connection to target SQLite database.
* **Lines 46–110**: Creates Control Tables (`ctl_batch_log`, `ctl_watermark`, `ctl_table_config`, `ctl_dq_rules`, `ctl_audit_log`).
* **Lines 111–130**: Populates `ctl_table_config` with ingestion strategies for all 18 source tables (e.g. `app_orders` set to `INCREMENTAL_DELTA`, `app_customer` set to `FULL_RELOAD`).
* **Lines 131–220**: Creates Bronze Raw Landing Tables (`br_orders`, `br_customer`, `br_payments`, etc.). Each Bronze table contains `dw_batch_id`, `dw_extracted_at`, `source_key`, and `raw_payload TEXT` (storing raw JSON strings).
* **Lines 221–320**: Creates Silver Clean Tables and Silver Quarantine Tables. Silver tables feature clean data types (`TIMESTAMP`, `DECIMAL`, `INTEGER`), surrogate keys, and PII-masked columns. Quarantine tables store `dw_quarantine_id`, `dw_quarantine_reason`, `raw_payload`, and `created_at`.
* **Lines 321–400**: Creates Gold Star Schema Tables:
  - **SCD Type 2 Dimensions**: `gd_dim_customer`, `gd_dim_restaurant`, `gd_dim_driver`, `gd_dim_menu_item`, featuring `customer_sk`, `effective_from`, `effective_to`, `is_current`.
  - **Fact Tables**: `gd_fact_orders`, `gd_fact_payments`, `gd_fact_deliveries`, `gd_fact_reviews`, featuring dimension surrogate foreign keys (`customer_sk`, `restaurant_sk`, `driver_sk`, `date_sk`) and quantitative measures (`total_amount`, `delivery_fee`, `tip_amount`).
  - **Marts**: `gd_mart_cohort_retention`, `gd_mart_executive_gmv_daily`.
* **Lines 401–419**: Commits transaction and logs completion metrics.
