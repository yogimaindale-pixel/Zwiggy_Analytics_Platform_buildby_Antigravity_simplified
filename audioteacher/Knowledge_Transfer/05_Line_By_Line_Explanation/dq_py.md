# 📄 Line-by-Line Code Breakdown: `src/zwiggy_dwh/dq.py`

**File Name**: `src/zwiggy_dwh/dq.py`  
**Total Lines**: 111 Lines  
**Primary Purpose**: Data Quality rule evaluation engine. Evaluates 7 mandatory quality checks against Silver tables, computes completeness and conformance percentages, and generates batch scorecards.

---

## 📜 Key Line Walkthrough

* **Line 34**: `def evaluate_data_quality_rules(batch_id: int, db_path: Optional[Path] = None) -> dict:` - Main DQ evaluation engine.
* **Lines 45–75**: Iterates through registered quality rules in `ctl_dq_rules`:
  1. **Not-Null Checks**: Validates required primary keys and mandatory timestamp columns are not null (`order_id`, `customer_id`, `created_at`).
  2. **Uniqueness Checks**: Confirms zero duplicate business keys exist in Silver tables.
  3. **Referential Integrity Checks**: Verifies all `order_id` references in `sl_order_items` exist in `sl_orders`.
  4. **Range Bound Checks**: Validates `total_amount >= 0` and `rating BETWEEN 1 AND 5`.
* **Lines 80–100**: Calculates Data Quality Metrics:
  - `data_completeness_pct`: % of non-null required attributes.
  - `conformance_score_pct`: % of rules passed cleanly.
  - Logs scorecard summary into `ctl_audit_log`.
* **Line 111**: Returns scorecard dictionary (`rules_evaluated`, `total_anomalies_detected`, `completeness_pct`, `conformance_pct`).
