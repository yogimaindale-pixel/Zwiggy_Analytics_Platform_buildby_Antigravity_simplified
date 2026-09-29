# 📄 Line-by-Line Code Breakdown: `src/zwiggy_dwh/pipeline.py`

**File Name**: `src/zwiggy_dwh/pipeline.py`  
**Total Lines**: 135 Lines  
**Primary Purpose**: Master pipeline orchestrator. Coordinates the sequential execution of all 5 Medallion pipeline stages in a single unified execution loop with batch lifecycle management and transaction safety.

---

## 📜 Key Line Walkthrough

* **Line 59**: `def run_full_etl_pipeline(db_path: Optional[Path] = None) -> dict:` - Main entrypoint for end-to-end pipeline execution.
* **Line 65**: Starts new batch entry in `ctl_batch_log` using `start_new_batch()`, obtaining `dw_batch_id`.
* **Lines 70–80**: **Step 1/5 (Source -> Bronze)**: Executes `ingest_all_source_tables_to_bronze(batch_id)`.
* **Lines 81–90**: **Step 2/5 (Bronze -> Silver)**: Executes `transform_bronze_to_silver(batch_id)`.
* **Lines 91–100**: **Step 3/5 (Data Quality Engine)**: Executes `evaluate_data_quality_rules(batch_id)`.
* **Lines 101–110**: **Step 4/5 (Silver -> Gold)**: Executes `transform_silver_to_gold(batch_id)`.
* **Lines 111–120**: **Step 5/5 (Data Reconciliation)**: Executes `run_reconciliation_checks(batch_id)`.
* **Lines 121–125**: Marks batch status as `COMPLETED` in `ctl_batch_log` using `complete_batch(batch_id)`.
* **Lines 126–129**: Returns complete pipeline summary metrics dictionary.
