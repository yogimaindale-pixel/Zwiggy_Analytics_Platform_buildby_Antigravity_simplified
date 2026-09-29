# 📄 Line-by-Line Code Breakdown: `src/zwiggy_dwh/bronze.py`

**File Name**: `src/zwiggy_dwh/bronze.py`  
**Total Lines**: 184 Lines  
**Primary Purpose**: Ingests raw transactional data from 18 OLTP source tables into Bronze raw landing tables (`br_*`). Implements incremental watermark filtering, encodes source rows into JSON string payloads (`raw_payload`), appends batch metadata (`dw_batch_id`, `dw_extracted_at`), and advances high-watermark timestamps.

---

## 📜 Key Line Walkthrough

* **Line 42**: `def ingest_all_source_tables_to_bronze(batch_id: int, db_path: Optional[Path] = None) -> dict:` - Main orchestrator iterating over all 18 source tables.
* **Line 82**: `def ingest_single_table_to_bronze(conn: ConnectionWrapper, table_config: dict, batch_id: int) -> int:` - Ingests a single table into Bronze.
* **Lines 90–105**: Extracts high-watermark timestamp for `table_config['source_table_name']` using `get_watermark(conn, source_table)`.
* **Lines 110–125**: Queries source delta records:
  ```sql
  SELECT * FROM source_table WHERE updated_at > last_watermark AND updated_at <= current_batch_time
  ```
* **Lines 130–155**: Iterates through source rows, serializes each row tuple into a JSON string (`json.dumps(row_dict)`), and inserts into Bronze:
  ```sql
  INSERT INTO br_{table} (dw_batch_id, dw_extracted_at, source_key, raw_payload)
  VALUES (?, ?, ?, ?)
  ```
* **Lines 160–175**: Calculates maximum `updated_at` timestamp from extracted rows, updates `ctl_watermark` using `update_watermark()`, and logs audit record into `ctl_audit_log`.
* **Line 184**: Returns total rows landed into Bronze for this table.
