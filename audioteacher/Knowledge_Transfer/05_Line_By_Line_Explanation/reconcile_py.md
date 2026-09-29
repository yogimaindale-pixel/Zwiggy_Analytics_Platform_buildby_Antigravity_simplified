# 📄 Line-by-Line Code Breakdown: `src/zwiggy_dwh/reconcile.py`

**File Name**: `src/zwiggy_dwh/reconcile.py`  
**Total Lines**: 114 Lines  
**Primary Purpose**: Cross-layer data reconciliation audit engine. Compares record counts and numeric metrics (e.g. total order amounts) between Source, Bronze, Silver, and Gold layers to verify 100% data fidelity.

---

## 📜 Key Line Walkthrough

* **Line 27**: `def run_reconciliation_checks(batch_id: int, db_path: Optional[Path] = None) -> list[dict]:` - Main reconciliation check executor.
* **Lines 35–65**: Executes row count comparisons:
  - Compares Source `app_orders` row count vs Bronze `br_orders` count vs Silver `sl_orders` count vs Gold `gd_fact_orders` count.
  - Computes row discrepancy variance: `variance = source_count - gold_count`.
* **Lines 70–95**: Executes financial metric reconciliation:
  - Compares `SUM(total_amount)` in Source `app_orders` against `SUM(total_amount)` in Gold `gd_fact_orders`.
  - Verifies financial discrepancy is zero (`variance == 0.00`).
* **Lines 100–110**: Logs reconciliation audit results into `ctl_audit_log` with status `PASSED` or `WARNING`.
* **Line 114**: Returns list of reconciliation audit check dictionaries.
