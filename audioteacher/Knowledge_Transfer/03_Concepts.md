# 💡 03. Core Data Engineering Concepts & Concept Cards

Welcome to **Lesson 03: Core Concepts & Architectural Patterns**! This guide breaks down every key concept used in the Zwiggy Analytics Data Warehouse using structured **Concept Cards**.

---

## 🃏 Concept Card 1: ETL (Extract, Transform, Load)

* **What is it?**: A 3-step data pipeline process where data is extracted from source operational databases, transformed (cleansed, standardized, aggregated), and loaded into a target data warehouse.
* **Why is it needed?**: Operational OLTP databases are optimized for fast transactional writes, not analytical queries. ETL decouples analytics from production transactions.
* **Real-world Example**: Extracting daily food delivery orders from a MySQL database, converting prices from cents to dollars, and loading into Amazon Redshift for financial reporting.
* **Business Scenario**: Zwiggy executives need a daily revenue dashboard. Running directly against the checkout DB will slow down active customer orders. ETL moves data safely to an analytics DB overnight.
* **Beginner Explanation**: Imagine copying student exam scores from paper sheets into an Excel workbook, fixing misspelled names, and creating a final summary score chart.
* **Advanced Explanation**: Decoupled batch pipeline that extracts delta mutations from transactional log tables, cleanses payload data into conformed relational structures, and updates dimensional star schema representations idempotently.
* **Repository Implementation**: `zwiggy_dwh.pipeline.run_full_etl_pipeline()` orchestrates the 5 Medallion pipeline steps.
* **Files & Lines Involved**: [`src/zwiggy_dwh/pipeline.py:L59-L129`](file:///config/Desktop/Session1/Zwiggy_Analytics_Platform_buildby_Antigravity_simplified/src/zwiggy_dwh/pipeline.py#L59-L129).

---

## 🃏 Concept Card 2: Change Data Capture (CDC) & Incremental Loading

* **What is it?**: A design pattern that identifies and extracts only the data records that have changed (inserted or updated) since the last pipeline run, rather than re-reading the entire database.
* **Why is it needed?**: Full database re-ingestion for 61,000+ orders daily takes excessive CPU, network bandwidth, and storage. CDC reduces processing time from hours to seconds.
* **Real-world Example**: Reading only new WhatsApp messages sent after 9:00 AM rather than re-downloading your entire chat history every minute.
* **Business Scenario**: Zwiggy processes 500,000 orders daily. Re-reading all historical orders every 15 minutes is impossible. CDC extracts only orders updated in the last 15 minutes.
* **Beginner Explanation**: Marking your page in a book with a bookmark so next time you start reading from where you left off instead of starting at page 1.
* **Advanced Explanation**: Timestamp-based high-watermark state tracking against an operational audit column (`updated_at`), capturing micro-batches bounded by $[W_{\text{last}}, W_{\text{current}}]$.
* **Repository Implementation**: `zwiggy_dwh.batch.get_watermark()` and `update_watermark()`.
* **Files & Lines Involved**: [`src/zwiggy_dwh/batch.py:L69-L130`](file:///config/Desktop/Session1/Zwiggy_Analytics_Platform_buildby_Antigravity_simplified/src/zwiggy_dwh/batch.py#L69-L130), [`src/zwiggy_dwh/bronze.py:L82-L184`](file:///config/Desktop/Session1/Zwiggy_Analytics_Platform_buildby_Antigravity_simplified/src/zwiggy_dwh/bronze.py#L82-L184).

---

## 🃏 Concept Card 3: Medallion Architecture (Bronze -> Silver -> Gold)

* **What is it?**: A multi-stage data architecture pattern where data is progressively refined from raw unvalidated format (Bronze), to cleansed conformed tables (Silver), to curated business models (Gold).
* **Why is it needed?**: Isolates data pipeline responsibilities. Raw data loss is impossible because Bronze preserves raw payloads. Data Quality is enforced at Silver. Business queries run fast on Gold Star Schema.
* **Real-world Example**: Crude oil (Bronze) is extracted from the ground, sent to a refinery (Silver) to remove impurities and create gasoline, and delivered to gas stations (Gold) for drivers.
* **Business Scenario**: An analyst finds a bug in tax calculations. Because Bronze stored raw JSON payloads, the team can re-run Silver and Gold transformations without re-extracting from production.
* **Beginner Explanation**: Bronze is raw ingredients from the farm, Silver is washed and chopped vegetables, Gold is a cooked gourmet meal ready to serve.
* **Advanced Explanation**: Progressive structural schema refinement pipeline establishing immutable append-only raw landing, conformed 3NF schema enforcement with quarantine, and Kimball star schema analytical views.
* **Repository Implementation**: `zwiggy_dwh.init_db`, `bronze.py`, `silver.py`, `gold.py`.
* **Files & Lines Involved**: [`src/zwiggy_dwh/bronze.py:L42-L184`](file:///config/Desktop/Session1/Zwiggy_Analytics_Platform_buildby_Antigravity_simplified/src/zwiggy_dwh/bronze.py#L42-L184), [`src/zwiggy_dwh/silver.py:L38-L231`](file:///config/Desktop/Session1/Zwiggy_Analytics_Platform_buildby_Antigravity_simplified/src/zwiggy_dwh/silver.py#L38-L231), [`src/zwiggy_dwh/gold.py:L34-L191`](file:///config/Desktop/Session1/Zwiggy_Analytics_Platform_buildby_Antigravity_simplified/src/zwiggy_dwh/gold.py#L34-L191).

---

## 🃏 Concept Card 4: Data Quality Engine & Quarantine Pattern

* **What is it?**: A automated rule evaluation engine that checks data records against completeness, uniqueness, referential integrity, and range bounds. Bad records are quarantined in `sl_quarantine`.
* **Why is it needed?**: Prevents corrupt, duplicate, or missing data from reaching executive BI dashboards and poisoning analytics.
* **Real-world Example**: Airport security screening baggage before passengers board the aircraft. Contraband items are isolated in security inspection bins.
* **Business Scenario**: If an order arrives with a negative payment amount (`-$500`), the Data Quality firewall flags the anomaly, routes it to `sl_quarantine`, and logs an alert.
* **Beginner Explanation**: A spam filter for your inbox that moves fishy emails into a junk folder so your inbox stays clean.
* **Advanced Explanation**: Declarative SQL/Python rule evaluation framework returning boolean pass/fail conditions. Quarantines non-conforming rows with failure metadata (`rule_id`, `quarantine_reason`).
* **Repository Implementation**: `zwiggy_dwh.dq.evaluate_data_quality_rules()`.
* **Files & Lines Involved**: [`src/zwiggy_dwh/dq.py:L34-L111`](file:///config/Desktop/Session1/Zwiggy_Analytics_Platform_buildby_Antigravity_simplified/src/zwiggy_dwh/dq.py#L34-L111).

---

## 🃏 Concept Card 5: Star Schema & Slowly Changing Dimensions (SCD Type 2)

* **What is it?**: A dimensional modeling pattern consisting of a central Fact table containing quantitative measures (e.g., `gd_fact_orders`) surrounded by Dimension tables containing descriptive context (`gd_dim_customer`, `gd_dim_restaurant`). SCD Type 2 preserves historical changes using `effective_from`, `effective_to`, and `is_current` flags.
* **Why is it needed?**: Enables fast, intuitive analytical queries with simple SQL joins while tracking how customer addresses or restaurant pricing change over time.
* **Real-world Example**: If a customer moves from Mumbai to Delhi in July, an order placed in June is attributed to Mumbai, while an order placed in August is attributed to Delhi.
* **Business Scenario**: Zwiggy wants to measure marketing campaign effectiveness by customer city. Without SCD Type 2, moving to a new city would retroactively alter historical sales history.
* **Beginner Explanation**: Taking a snapshot photo of a customer every time they change their address so you have a complete photo album of their history.
* **Advanced Explanation**: Surrogate key dimension table design tracking attribute mutations through row versioning. Active rows have `is_current = 1` and `effective_to = '9999-12-31'`. Expired rows have `is_current = 0`.
* **Repository Implementation**: `zwiggy_dwh.gold.transform_silver_to_gold()`.
* **Files & Lines Involved**: [`src/zwiggy_dwh/gold.py:L34-L191`](file:///config/Desktop/Session1/Zwiggy_Analytics_Platform_buildby_Antigravity_simplified/src/zwiggy_dwh/gold.py#L34-L191).

---

## 🃏 Concept Card 6: Connection Wrappers & Exponential Backoff Retry Logic

* **What is it?**: Database resilience wrappers that manage SQL transactions safely, convert dictionary rows, and automatically retry failed queries with exponential backoff delays.
* **Why is it needed?**: Network blips or temporary database locks can cause transient query failures. Retrying automatically prevents pipeline crashes.
* **Real-world Example**: Redialing a phone number automatically when you get a busy signal, waiting 2 seconds, then 4 seconds, then 8 seconds before giving up.
* **Business Scenario**: A transient DB lock occurs during midnight backup. The pipeline catches the operational error, waits 1 second, retries successfully, and completes without manual intervention.
* **Beginner Explanation**: A smart safety switch that retries plugging in a cable if the power flickers for a millisecond.
* **Advanced Explanation**: Higher-order decorator function `with_retry(max_retries=3, backoff_factor=1.5)` wrapping cursor executions, catching `DatabaseError` exceptions, and sleeping between retry attempts.
* **Repository Implementation**: `zwiggy_dwh.db.ConnectionWrapper`, `DictCursorWrapper`, `with_retry()`.
* **Files & Lines Involved**: [`src/zwiggy_dwh/db.py:L50-L225`](file:///config/Desktop/Session1/Zwiggy_Analytics_Platform_buildby_Antigravity_simplified/src/zwiggy_dwh/db.py#L50-L225).

---

## 🃏 Concept Card 7: Cross-Layer Data Reconciliation Auditing

* **What is it?**: An automated auditing check that compares record counts, numeric sums (e.g., total GMV), and key integrity across Source, Bronze, Silver, and Gold layers.
* **Why is it needed?**: Guarantees data fidelity. Proves that zero orders were silently dropped or duplicated during transformations.
* **Real-world Example**: A bank teller counting total cash in the drawer at the end of the day and matching it against the receipt register total.
* **Business Scenario**: Finance auditors require proof that total revenue in the Gold Data Warehouse matches total revenue in the Source checkout DB within 0.00% discrepancy.
* **Beginner Explanation**: Double-checking your receipt total against the money in your wallet after grocery shopping.
* **Advanced Explanation**: Automated validation runner executing cross-table SQL aggregation queries (`COUNT(*)`, `SUM(total_amount)`), logging reconciliation metrics into `ctl_audit_log`, and raising alerts if thresholds exceed 0%.
* **Repository Implementation**: `zwiggy_dwh.reconcile.run_reconciliation_checks()`.
* **Files & Lines Involved**: [`src/zwiggy_dwh/reconcile.py:L27-L114`](file:///config/Desktop/Session1/Zwiggy_Analytics_Platform_buildby_Antigravity_simplified/src/zwiggy_dwh/reconcile.py#L27-L114).
