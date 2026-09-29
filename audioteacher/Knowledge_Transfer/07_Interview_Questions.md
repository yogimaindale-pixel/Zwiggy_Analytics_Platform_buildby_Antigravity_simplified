# ❓ 07. Technical Interview Questions & Spoken Response Bank

Welcome to **Lesson 07: Technical Interview Questions & Spoken Answer Bank**!

This guide provides 10 high-frequency technical interview questions tailored for Data Engineer, Analytics Engineer, and Data Architect roles, structured with 30-second elevator pitches, 2-minute detailed technical responses, and spoken answers.

---

### Q1: What is the Medallion Data Architecture and why did you use it for Zwiggy?
* **30-Second Summary**: Medallion Architecture organizes data into Bronze raw landing, Silver cleansed relational tables, and Gold star schema models. We used it to decouple OLTP ingestion from analytical modeling and prevent query locks on checkout tables.
* **2-Minute Technical Answer**: In Zwiggy, operational databases process thousands of checkout writes per minute. Running direct analytical queries against OLTP schemas causes table locking and performance degradation. The Medallion Architecture extracts raw source records into Bronze append-only tables storing raw JSON strings. Silver cleanses data, enforces data types, masks PII, and quarantines bad records. Gold builds Kimball Star Schema dimensions with SCD Type 2 and Fact tables. This ensures high data quality, historical auditability, and fast query performance for business analysts.
* **Spoken Response**: "In our Zwiggy Data Warehouse, we adopted the Medallion Data Architecture to solve two main problems: operational database performance and data quality. Bronze acts as an append-only raw landing zone capturing JSON payloads. Silver cleanses data, enforces types, and isolates corrupted rows into quarantine. Gold models data into Kimball Star Schemas with SCD Type 2 dimensions. This multi-stage isolation guarantees that raw data is never lost and executive dashboards always query clean, conformed data."

---

### Q2: How do you handle Change Data Capture (CDC) and avoid full table re-ingestion?
* **30-Second Summary**: We use a timestamp-based high-watermark pattern. The pipeline tracks the max `updated_at` timestamp per table in `ctl_watermark` and extracts only records modified since the last batch run.
* **2-Minute Technical Answer**: Re-reading 61,000+ orders on every 15-minute pipeline run consumes excessive CPU and storage. We implement incremental loading using `ctl_watermark`. When a batch starts, `get_watermark()` retrieves the last high-watermark timestamp $W_{\text{last}}$. We execute `SELECT * FROM table WHERE updated_at > W_last AND updated_at <= W_current`. Landed rows are appended into Bronze, and `update_watermark()` advances the high-watermark timestamp upon batch completion.
* **Spoken Response**: "We implement incremental extraction using a high-watermark tracker in `ctl_watermark`. On every pipeline run, we query only source rows where `updated_at` is greater than the last processed timestamp. After landing delta rows in Bronze, we advance the high-watermark to the current batch timestamp. This reduces batch processing time from minutes to seconds."

---

### Q3: How do you track historical changes when customer addresses or driver ratings change?
* **30-Second Summary**: We implement Slowly Changing Dimension Type 2 (SCD Type 2) in Gold dimensions using `effective_from`, `effective_to`, and `is_current` flags.
* **2-Minute Technical Answer**: When a customer changes their address or city, overwriting their record destroys historical audit trails required for point-in-time revenue attribution. In `gd_dim_customer`, when an attribute change is detected, we expire the existing active row by setting `effective_to = current_timestamp` and `is_current = 0`. We insert a new row with a new surrogate key (`customer_sk`), `effective_from = current_timestamp`, `effective_to = '9999-12-31'`, and `is_current = 1`. Fact tables join against the dimension surrogate key active at order placement time.
* **Spoken Response**: "To preserve historical point-in-time accuracy, we use SCD Type 2 in Gold dimensions like `gd_dim_customer`. When a customer updates their address, we expire the previous dimension row by setting `is_current = 0` and `effective_to` to the current time, and insert a new row with `is_current = 1`. This allows us to attribute historical orders to the customer's previous location while attributing new orders to their new location."

---

### Q4: How does your pipeline handle bad data or schema corruption without crashing?
* **30-Second Summary**: We use a Data Quality Firewall and Silver Quarantine Pattern. Corrupted or unparseable JSON payloads are routed to `sl_quarantine` tables while clean rows proceed.
* **2-Minute Technical Answer**: In `src/zwiggy_dwh/silver.py`, JSON payload parsing is wrapped in `try-except` blocks. If payload decoding fails or required business keys are missing, the pipeline inserts the raw row into `sl_{table}_quarantine` with a `dw_quarantine_reason` and increments quarantine metrics. In addition, `src/zwiggy_dwh/dq.py` evaluates 7 mandatory quality checks (not null, uniqueness, referential integrity, range bounds), producing a Data Quality Scorecard without breaking pipeline execution.
* **Spoken Response**: "We isolate corrupt data using a Silver Quarantine Pattern. During Silver transformation, if a row fails JSON parsing or breaks primary key constraints, it is diverted to an `sl_quarantine` table along with failure reason metadata. The rest of the clean batch continues processing, ensuring that bad rows do not crash the pipeline or poison BI dashboards."

---

### Q5: How do you verify that data was not lost or altered across Bronze, Silver, and Gold layers?
* **30-Second Summary**: We run automated cross-layer reconciliation checks comparing row counts and total GMV revenue sums across all layers.
* **2-Minute Technical Answer**: In `src/zwiggy_dwh/reconcile.py`, `run_reconciliation_checks()` executes SQL aggregation queries comparing row counts (`COUNT(*)`) and revenue totals (`SUM(total_amount)`) between Source `app_orders`, Bronze `br_orders`, Silver `sl_orders`, and Gold `gd_fact_orders`. Discrepancies exceeding 0.00% are logged as warnings into `ctl_audit_log`, providing financial auditors with verifiable proof of data integrity.
* **Spoken Response**: "We enforce data integrity using automated reconciliation auditing in `reconcile.py`. We execute cross-table aggregation checks comparing row counts and financial totals between Source, Bronze, Silver, and Gold layers. Any discrepancy between source revenue and Gold fact revenue is instantly flagged in our operational audit logs."
