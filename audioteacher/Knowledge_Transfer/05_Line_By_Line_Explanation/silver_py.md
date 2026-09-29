# 📄 Line-by-Line Code Breakdown: `src/zwiggy_dwh/silver.py`

**File Name**: `src/zwiggy_dwh/silver.py`  
**Total Lines**: 231 Lines  
**Primary Purpose**: Bronze-to-Silver data cleansing and normalization engine. Decodes raw JSON payloads from `br_*` tables, casts strings to strong types (timestamps, decimals, integers), masks PII (emails, phone numbers), handles null replacement, enforces entity deduplication, and routes corrupted records into `sl_*_quarantine`.

---

## 📜 Key Line Walkthrough

* **Line 38**: `def transform_bronze_to_silver(batch_id: int, db_path: Optional[Path] = None) -> dict:` - Main Silver transformation orchestrator.
* **Lines 50–80**: Queries unprocessed rows from Bronze tables where `dw_batch_id = batch_id`.
* **Lines 85–120**: Parses `raw_payload` JSON strings. If JSON parsing fails or required primary keys are missing:
  - Routes row to `sl_{table}_quarantine` with `dw_quarantine_reason = 'INVALID_JSON_PAYLOAD'`.
  - Increments quarantine metric count.
* **Lines 125–170**: Applies data transformations:
  - **Type Casting**: Converts date strings to ISO-8601 timestamps, prices to 2-decimal floats.
  - **PII Masking**: Redacts customer email (`user@domain.com` -> `u***@domain.com`) and phone numbers (`+91 9876543210` -> `+91 ******3210`).
  - **Null Handling**: Replaces missing payment methods with `'UNKNOWN'`, missing delivery notes with `'N/A'`.
* **Lines 175–210**: Inserts clean records into Silver clean tables (`sl_orders`, `sl_customer`, `sl_payments`, etc.) with surrogate business key mappings.
* **Line 231**: Returns summary dictionary containing total Silver clean rows loaded and total quarantine rows isolated.
