# 🏛️ 10. Senior Engineer Architecture, Scaling & Extension Blueprint

Welcome to **Lesson 10: Senior Principal Engineer Guide**!

This guide provides an enterprise scaling blueprint for Principal Engineers and Technical Architects expanding the Zwiggy Analytics Data Warehouse from local SQLite/Python execution to petabyte-scale cloud data platforms.

---

## 1. Enterprise Big Data Scaling Migration Blueprint

To scale the Zwiggy Analytics Platform from single-node Python/SQLite execution to petabyte-scale distributed data platforms, map local components directly to cloud-native technologies:

| Local Component | Enterprise Cloud Equivalent | Migration Strategy |
| :--- | :--- | :--- |
| **SQLite Storage** | **Databricks Delta Lake / Apache Iceberg** | Convert SQLite DDL to Delta Lake / Iceberg ACID tables on AWS S3 / GCS. |
| **Python Core Execution** | **PySpark / Apache Spark 3.5+** | Replace single-node Python loops with distributed Spark DataFrame transformations. |
| **CLI / Python Script Orchestrator** | **Apache Airflow / Dagster / Prefect** | Replace `pipeline.py` loop with an Airflow DAG or Dagster asset graph with SLA retries. |
| **Data Quality Rules Engine** | **Great Expectations / Soda Core / Deequ** | Port `dq.py` rule evaluation logic to Great Expectations or AWS Deequ Spark checks. |
| **Local SQLite Control Tables** | **AWS Glue Data Catalog / Unity Catalog** | Port `ctl_*` metadata to Databricks Unity Catalog or Snowflake Account Usage schema. |

---

## 2. Guide: How to Extend the Codebase with a New Table

Suppose business requests ingesting a new OLTP table: `app_restaurant_coupons`.

Follow this 4-step checklist to extend the platform cleanly:

### Step 1: Update Infrastructure DDL (`init_db.py`)
Add DDL statements for Bronze, Silver clean, Silver quarantine, and Gold dimension/fact tables:
```sql
-- Bronze
CREATE TABLE IF NOT EXISTS br_restaurant_coupons (
    dw_batch_id INTEGER, dw_extracted_at TIMESTAMP, source_key TEXT, raw_payload TEXT
);
-- Silver
CREATE TABLE IF NOT EXISTS sl_restaurant_coupons (
    coupon_id INTEGER PRIMARY KEY, restaurant_id INTEGER, coupon_code TEXT, discount_pct REAL
);
```

### Step 2: Register Table Strategy (`metadata.py` & CSV)
Add ingestion configuration to `TABLE_INGESTION_CONFIGURATION.csv` and `get_classification_matrix()`:
```python
"app_restaurant_coupons": TableClassification(
    source_table_name="app_restaurant_coupons",
    ingestion_strategy="INCREMENTAL_DELTA",
    watermark_column="updated_at",
    primary_key_column="coupon_id"
)
```

### Step 3: Add Cleansing & Transformation Logic (`silver.py` & `gold.py`)
Inside `silver.py`, parse raw JSON, validate `coupon_id` presence, cast `discount_pct` to float, and insert into `sl_restaurant_coupons`.

### Step 4: Write Pytest Unit Test (`tests/test_foundations.py`)
Add automated unit test verifying schema creation, ingestion, and clean transformation:
```python
def test_restaurant_coupons_ingestion(setup_dwh):
    # Verify table existence and zero quarantine rows
    pass
```

---

## 3. Production CI/CD & Governance Best Practices

1. **Automated Schema Migration**: Use `alembic` or `sqitch` for database migration versioning.
2. **Zero-Downtime Pipeline Deployment**: Execute blue-green schema deployments for Gold marts.
3. **Data Observability**: Integrate Slack/PagerDuty webhooks for critical DQ quarantine alerts.
4. **Security & Governance**: Enforce RBAC and PII column hashing (`SHA-256`) at the Silver layer before data reaches Gold analytics.
