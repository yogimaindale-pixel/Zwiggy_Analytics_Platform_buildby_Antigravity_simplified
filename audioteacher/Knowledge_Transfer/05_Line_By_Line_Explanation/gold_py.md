# 📄 Line-by-Line Code Breakdown: `src/zwiggy_dwh/gold.py`

**File Name**: `src/zwiggy_dwh/gold.py`  
**Total Lines**: 191 Lines  
**Primary Purpose**: Silver-to-Gold Star Schema dimensional modeling engine. Builds 14 SCD Type 2 dimensions (`gd_dim_*`), 6 fact tables (`gd_fact_*`), and 2 analytical marts (`gd_mart_*`).

---

## 📜 Key Line Walkthrough

* **Line 34**: `def transform_silver_to_gold(batch_id: int, db_path: Optional[Path] = None) -> dict:` - Main Gold layer builder orchestrator.
* **Lines 45–90**: Builds **Slowly Changing Dimensions (SCD Type 2)** for `gd_dim_customer`, `gd_dim_restaurant`, `gd_dim_driver`:
  - Compares incoming Silver records against active dimension records where `is_current = 1`.
  - If a change is detected in customer city or address:
    1. Sets `effective_to = current_timestamp` and `is_current = 0` on existing record.
    2. Inserts new record with new surrogate key (`customer_sk`), `effective_from = current_timestamp`, `effective_to = '9999-12-31'`, and `is_current = 1`.
* **Lines 95–140**: Builds Central Fact Tables (`gd_fact_orders`, `gd_fact_payments`, `gd_fact_deliveries`):
  - Resolves dimension surrogate keys (`customer_sk`, `restaurant_sk`, `driver_sk`, `date_sk`) by joining Silver tables against active Gold dimensions (`is_current = 1`).
  - Populates quantitative metrics (`subtotal`, `tax_amount`, `delivery_fee`, `tip_amount`, `total_amount`).
* **Lines 145–180**: Builds Analytical Aggregation Marts:
  - `gd_mart_cohort_retention`: Groups customers by signup cohort month and tracks order frequency over 30/60/90 days.
  - `gd_mart_executive_gmv_daily`: Computes daily Gross Merchandise Value (GMV), total order volume, and average order value (AOV).
* **Line 191**: Returns summary dictionary containing total Gold dimension, fact, and mart rows created.
