---
name: dwh-metadata-and-foundations
description: Establishes the foundational data warehouse infrastructure, control tables, configuration metadata, watermark management, and orchestration framework required before data ingestion can begin. Run this skill first to set up the platform.
---

# Purpose

This skill establishes the complete foundational infrastructure for the Zwiggy Analytics Platform data warehouse. It creates the control layer, configuration tables, batch management system, watermark tracking, and all prerequisite metadata structures that enable the metadata-driven ingestion and transformation pipelines to function correctly.

This is the **first skill to execute**. No data ingestion can occur until this skill completes successfully.

# When to Use This Skill

- **Initial project setup**: Running for the first time to establish the DWH from scratch
- **Environment initialization**: Setting up a new DWH environment (dev, staging, production)
- **Platform reset**: Starting fresh after a complete rebuild
- **Prerequisites satisfied**: PostgreSQL connectivity confirmed, target warehouse connection (PostgreSQL/DuckDB/Parquet) available, schema naming conventions agreed

# When Not to Use This Skill

- Do not use this if the control tables already exist and are functional
- Do not use this for incremental data loads (use source-to-bronze-ingestion instead)
- Do not use this for transformation operations (use bronze-to-gold-transformation instead)
- Do not use this for dashboard or BI configuration (handled by separate BI skill)
- Do not use this for fixing data quality issues in existing tables (use bronze-to-gold-transformation instead)

# Project Context

**Project**: Zwiggy Capstone — Live ETL Design & Development  
**Program**: Zwiggy Analytics Platform  
**Source System**: PostgreSQL 18.1 database `zwiggy_db`, single schema `app`, 18 tables, 177 columns, 336,751 rows  
**Architecture**: Medallion (Bronze → Silver → Gold) data warehouse  
**Scope**: This skill covers control layer setup only; data ingestion and transformation are separate skills  

**Key Project Facts**:
- Source contains two incompatible data cohorts separated at order_id 10,928
- Cohort A: 7,950 orders (12.9%), 1 month window, human status vocabulary, 100% with line detail
- Cohort B: 53,827 orders (87.1%), long window, machine vocabulary, 0% with line detail
- Critical data quality issues exist in source (P-2 through P-9 from BRD-A)
- Must implement 40+ data quality rules with quarantine and reconciliation framework
- Must support idempotent daily batch pipeline with full replaying capability

# Required Files to Read

Before executing this skill, Antigravity must review:

1. **Business Requirements**
   - `BRD-A-BI-and-Analytics-v0.1.pdf` - Business context, KPIs, problems being solved
   - `BRD-B-DWH-Medallion-Project-v0.1.pdf` - Complete data warehouse architecture, layer contracts, naming conventions, standards

2. **Source Schema**
   - `Source Schema Details.xlsx` - Complete source database schema with 18 tables, 177 columns, data types, keys, constraints

3. **Functional Requirements**
   - `Functional Requirements.docx` - Complete specification for Source-to-Bronze pipeline design principles

4. **Architecture References in BRD-B**:
   - §1: Scope and objectives
   - §2: Architecture and layer contracts
   - §10: Orchestration and control tables
   - §12: Non-functional requirements
   - §14: Engineering standards

# Preconditions

Before this skill can execute, verify:

1. **Connectivity Requirements**
   - Source database (PostgreSQL 18.1) is accessible, read-only credentials available
   - Target warehouse storage is provisioned and accessible
   - Network connectivity between execution environment and both databases/storage confirmed

2. **Security Requirements**
   - Database credentials are available through secure configuration (environment variables or secret manager)
   - Credentials are NOT embedded in code or configuration files
   - Source database user has SELECT on INFORMATION_SCHEMA and required application tables
   - Target warehouse has DDL and DML permissions for control and data layers

3. **Technical Requirements**
   - Python 3.10+ environment available with required packages: psycopg2, pandas, sqlalchemy
   - SQL execution capability (native database connection or tools like DuckDB, Parquet API)
   - Storage location for Bronze/Silver/Gold layers identified and provisioned
   - Logging and audit table storage available

4. **Configuration Requirements**
   - Database connection parameters externally configured (host, port, database, schema, username)
   - Target warehouse type decided (PostgreSQL, DuckDB, Parquet files, or other)
   - Schema naming convention confirmed: `bronze`, `silver`, `gold`, `control` schemas
   - Audit and logging table location determined

5. **Documentation Requirements**
   - Project architecture diagrams understood
   - Data dictionary available
   - Source schema details reviewed
   - Control table design understood

# Responsibilities

This skill is exclusively responsible for:

1. **Control Layer Foundation**
   - Create `control` schema
   - Create `ctl_batch` table for run tracking
   - Create `ctl_table_config` table for metadata-driven ingestion configuration
   - Create `ctl_watermark` table for incremental checkpoint tracking
   - Create `ctl_reconciliation` table for validation results
   - Create `ctl_rule_status` table for data quality rule execution tracking

2. **Metadata Configuration**
   - Define table-level ingestion strategies for all 18 source tables
   - Classify each table as: TIMESTAMP_WATERMARK, CREATED_DATE_WATERMARK, KEY_WATERMARK, COMPOSITE_WATERMARK, CDC, FULL_SNAPSHOT, or FULL_REFERENCE
   - Populate `ctl_table_config` with extraction patterns, watermark columns, key columns, look-back windows, initial-load flags
   - Document business key for each entity
   - Define primary key, unique constraints, and change-tracking columns per source table

3. **Schema Preparation**
   - Create `bronze` schema for raw ingested data
   - Create `silver` schema for cleansed, conformed entities
   - Create `gold` schema for dimensional model (dimensions, facts, aggregates)
   - Create `quarantine` subschema within silver for failed records
   - Create `control` schema for all platform infrastructure

4. **Audit and Lineage Tables**
   - Create `control.audit_run_log` for pipeline execution tracking
   - Create `control.audit_source_extract` for extraction manifest details
   - Create `control.audit_reconciliation` for validation results per run
   - Create `control.audit_dq_result` for data quality scorecard

5. **Reference Data and Mappings**
   - Create `silver.ref_status_map` for order status conformance (mapping source vocabulary to conformed vocabulary)
   - Create `silver.ref_payment_status_map` for payment status conformance
   - Create `silver.ref_cohort_rule` for cohort boundary configuration (stores 10,928 as configurable threshold)
   - Create `silver.ref_dq_rule_definition` for all 40+ data quality rules
   - Populate initial conformance mappings for status values

6. **Dimension Skeleton (Structure Only)**
   - Create DDL for 14 Gold dimension tables with standard warehouse columns (see Appendix A)
   - Create DDL for 6 active fact tables
   - Create DDL for 3 deferred fact/bridge tables
   - Create DDL for 2 aggregate marts
   - Do NOT populate these tables (that is the responsibility of bronze-to-gold-transformation skill)

7. **Standard Warehouse Columns**
   - Define and document standard columns applied to all Bronze, Silver, and Gold tables
   - Bronze standard columns: `dw_ingest_date`, `dw_batch_id`, `dw_ingest_ts_utc`, `dw_source_system`, `dw_source_schema`, `dw_source_table`
   - Silver standard columns: add `dw_source_hash`, `dw_row_hash`, all `dq_flag_*` columns for data quality flags
   - Gold standard columns: add `dw_initial_load`, `dw_version_no`, `dw_row_hash`, `is_current`, `valid_from_utc`, `valid_to_utc` (dimensions), plus surrogate keys

8. **Idempotency Framework**
   - Document and configure batch ID generation strategy
   - Define how re-running the same batch window must not create duplicates
   - Configure watermark advance rules: only after successful Bronze write AND successful reconciliation
   - Establish checkpoint isolation so failed runs do not advance watermarks

9. **Logging and Observability**
   - Create logging tables for pipeline execution
   - Define log levels and severity capture
   - Configure retention policy for logs and audit trails
   - Set up batch duration and freshness monitoring framework

10. **Documentation Generation**
    - Generate technical specification document: control table schemas, column definitions, constraints
    - Generate configuration worksheet: table ingestion strategies, watermark definitions, initial-load status
    - Generate data dictionary: field-level lineage from source through Bronze to Silver to Gold
    - Generate platform runbook: operational procedures, failure recovery, manual intervention

# Step-by-Step Execution Workflow

## Phase 1: Validation and Connectivity (Non-Destructive)

**1.1 Validate Preconditions**
- Verify source database connectivity using provided credentials
- Test query against source `INFORMATION_SCHEMA.TABLES` and `INFORMATION_SCHEMA.COLUMNS`
- Confirm row counts in source tables match expected baseline: 336,751 total rows across 18 tables
- Verify target warehouse storage/database is accessible and writable
- Confirm Python environment has required packages (psycopg2, pandas, sqlalchemy)
- Log all validation steps with timestamps

**1.2 Discover Source Metadata**
- Query source `INFORMATION_SCHEMA` to extract:
  - All table names, column names, data types
  - Primary keys, unique keys, foreign keys (21 FKs expected, all clean)
  - Nullable indicators, identity sequences (17 identity sequences expected)
  - Default values, column positions, character set metadata
- Store discovered metadata in memory for analysis
- Compare discovered schema against `Source Schema Details.xlsx` for completeness
- Document any schema drift or unexpected differences

**1.3 Analyze Table Characteristics**
- For each of the 18 source tables, determine:
  - Does table have a primary key? (yes, all 18 do)
  - Does table have created_at, updated_at, or equivalent timestamp? (identify specific columns)
  - Are rows mutable after insertion or append-only?
  - Does table expose delete indicators (is_active, is_deleted, deleted_at)?
  - Is table transactional (orders, payments, delivery) or reference/master (status, gender)?
  - Is table empty in source? (expect 4 empty tables: gender, cuisines, order_cancellation, refunds, restaurant_owner — actually verify)
- Apply extraction pattern decision tree per Functional Requirements §34
- Document final classification for all 18 tables

**1.4 Extract Classification Matrix**
- Create table-level classification matrix:
  ```
  Table Name | Primary Key | Watermark Column | Ingestion Pattern | Look-Back Days | Initial Load? | Active
  orders     | order_id    | updated_at       | TIMESTAMP_WATERMARK | 7            | true         | true
  [... continue for all 18 tables ...]
  ```
- Validate that pattern selection follows decision flow in Functional Requirements §34
- Document decision rationale for non-obvious cases (e.g., why each transactional table uses which pattern)

## Phase 2: Schema Creation (Idempotent, Drop-First if Needed)

**2.1 Create Control Schema and Tables**

Execute these SQL statements in order, idempotent (DROP IF EXISTS first):

```sql
-- Control Schema
DROP SCHEMA IF EXISTS control CASCADE;
CREATE SCHEMA control;
COMMENT ON SCHEMA control IS 'Control layer: batch orchestration, watermarks, configuration metadata';

-- Batch Control Table
CREATE TABLE control.ctl_batch (
    dw_batch_id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    batch_start_ts_utc TIMESTAMP NOT NULL,
    batch_end_ts_utc TIMESTAMP,
    run_cutoff_ts_utc TIMESTAMP NOT NULL,
    run_type VARCHAR(50) NOT NULL DEFAULT 'INCREMENTAL' 
        CHECK (run_type IN ('INITIAL_LOAD', 'INCREMENTAL', 'REPLAY', 'FULL_REFRESH')),
    status VARCHAR(50) NOT NULL DEFAULT 'IN_PROGRESS'
        CHECK (status IN ('IN_PROGRESS', 'COMPLETED', 'FAILED', 'ROLLED_BACK')),
    triggered_by VARCHAR(255),
    code_version VARCHAR(50),
    batch_description TEXT,
    created_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_batch_times CHECK (batch_start_ts_utc <= COALESCE(batch_end_ts_utc, CURRENT_TIMESTAMP))
);
CREATE INDEX idx_ctl_batch_status ON control.ctl_batch(status);
CREATE INDEX idx_ctl_batch_created ON control.ctl_batch(created_ts DESC);

-- Table Configuration (Metadata-Driven)
CREATE TABLE control.ctl_table_config (
    config_id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    source_system VARCHAR(100) NOT NULL DEFAULT 'zwiggy_db',
    source_schema VARCHAR(100) NOT NULL DEFAULT 'app',
    source_table VARCHAR(255) NOT NULL,
    target_bronze_table VARCHAR(255) NOT NULL,
    target_silver_table VARCHAR(255),
    target_gold_table VARCHAR(255),
    ingestion_strategy VARCHAR(50) NOT NULL
        CHECK (ingestion_strategy IN (
            'TIMESTAMP_WATERMARK', 'CREATED_DATE_WATERMARK', 'KEY_WATERMARK', 
            'COMPOSITE_WATERMARK', 'CDC', 'FULL_SNAPSHOT', 'FULL_REFERENCE'
        )),
    business_key VARCHAR(255) NOT NULL COMMENT 'Comma-separated columns forming business key',
    watermark_column VARCHAR(255) COMMENT 'Incremental: updated_at or equivalent',
    secondary_watermark_column VARCHAR(255) COMMENT 'Composite watermark: tie-breaker column',
    primary_key_column VARCHAR(255) NOT NULL COMMENT 'Source PK for deduplication',
    lookback_days INT DEFAULT 7 COMMENT 'Overlap window for late-arriving data',
    is_initial_load_complete BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    table_group VARCHAR(100) COMMENT 'Dependency group for parallel execution',
    row_count_expected INT,
    created_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    config_notes TEXT,
    UNIQUE(source_system, source_schema, source_table)
);
CREATE INDEX idx_table_config_active ON control.ctl_table_config(is_active);

-- Watermark Tracking
CREATE TABLE control.ctl_watermark (
    watermark_id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    source_system VARCHAR(100) NOT NULL DEFAULT 'zwiggy_db',
    source_schema VARCHAR(100) NOT NULL DEFAULT 'app',
    source_table VARCHAR(255) NOT NULL,
    watermark_value VARCHAR(500),
    watermark_secondary_value VARCHAR(500) COMMENT 'For composite watermarks',
    last_successful_batch_id BIGINT,
    last_successful_run_ts TIMESTAMP,
    last_failed_batch_id BIGINT,
    last_failed_run_ts TIMESTAMP,
    extract_row_count INT,
    load_row_count INT,
    reject_row_count INT,
    current_status VARCHAR(50) DEFAULT 'PENDING'
        CHECK (current_status IN ('PENDING', 'SUCCESS', 'PARTIAL_SUCCESS', 'FAILED')),
    updated_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_system, source_schema, source_table),
    FOREIGN KEY (last_successful_batch_id) REFERENCES control.ctl_batch(dw_batch_id)
);

-- Reconciliation Results
CREATE TABLE control.ctl_reconciliation (
    reconciliation_id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    dw_batch_id BIGINT NOT NULL,
    source_table VARCHAR(255) NOT NULL,
    target_table VARCHAR(255) NOT NULL,
    check_name VARCHAR(255) NOT NULL,
    source_row_count INT,
    target_row_count INT,
    expected_row_count INT,
    threshold_percent NUMERIC(5,2),
    result VARCHAR(50) NOT NULL 
        CHECK (result IN ('PASS', 'WARN', 'FAIL')),
    details TEXT,
    checked_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dw_batch_id) REFERENCES control.ctl_batch(dw_batch_id)
);
CREATE INDEX idx_reconciliation_batch ON control.ctl_reconciliation(dw_batch_id);

-- Data Quality Rule Tracking
CREATE TABLE control.ctl_dq_rule (
    dq_rule_id INT PRIMARY KEY,
    rule_category VARCHAR(100),
    rule_name VARCHAR(255) NOT NULL,
    rule_description TEXT,
    severity VARCHAR(50) CHECK (severity IN ('BLOCK', 'QUARANTINE', 'WARN', 'RECONCILE')),
    target_table VARCHAR(255),
    sql_predicate TEXT,
    affected_column VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Run Audit Log
CREATE TABLE control.audit_run_log (
    log_id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    dw_batch_id BIGINT NOT NULL,
    source_table VARCHAR(255),
    event_type VARCHAR(100) NOT NULL,
    message TEXT,
    severity VARCHAR(20) CHECK (severity IN ('INFO', 'WARN', 'ERROR')),
    execution_duration_seconds INT,
    logged_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dw_batch_id) REFERENCES control.ctl_batch(dw_batch_id)
);
CREATE INDEX idx_audit_run_batch ON control.audit_run_log(dw_batch_id);
CREATE INDEX idx_audit_run_ts ON control.audit_run_log(logged_ts DESC);

-- Extract Manifest
CREATE TABLE control.audit_source_extract (
    extract_id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    dw_batch_id BIGINT NOT NULL,
    source_table VARCHAR(255) NOT NULL,
    extract_predicate TEXT,
    extract_row_count INT NOT NULL,
    extract_start_ts TIMESTAMP NOT NULL,
    extract_end_ts TIMESTAMP NOT NULL,
    min_watermark_value VARCHAR(500),
    max_watermark_value VARCHAR(500),
    checksum_hash VARCHAR(64),
    extract_status VARCHAR(50) DEFAULT 'SUCCESS'
        CHECK (extract_status IN ('SUCCESS', 'FAILED', 'PARTIAL')),
    error_message TEXT,
    created_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dw_batch_id) REFERENCES control.ctl_batch(dw_batch_id)
);
CREATE INDEX idx_extract_batch ON control.audit_source_extract(dw_batch_id);
```

**2.2 Create Reference Data Tables (Silver Schema)**

```sql
-- Status Conformance Mapping
DROP TABLE IF EXISTS silver.ref_status_map CASCADE;
CREATE TABLE silver.ref_status_map (
    status_map_id INT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    source_status_value VARCHAR(100) NOT NULL,
    source_table VARCHAR(255) NOT NULL,
    conformed_status_value VARCHAR(100) NOT NULL 
        CHECK (conformed_status_value IN ('PENDING', 'COMPLETED', 'CANCELLED')),
    status_group VARCHAR(100),
    is_valid BOOLEAN DEFAULT TRUE,
    effective_from_date DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_to_date DATE,
    created_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_table, source_status_value, effective_from_date)
);

-- Cohort Boundary Configuration
DROP TABLE IF EXISTS silver.ref_cohort_rule CASCADE;
CREATE TABLE silver.ref_cohort_rule (
    cohort_rule_id INT PRIMARY KEY,
    cohort_name VARCHAR(50) NOT NULL,
    boundary_column VARCHAR(100) NOT NULL,
    boundary_operator VARCHAR(10) NOT NULL CHECK (boundary_operator IN ('<', '<=', '>', '>=')),
    boundary_value VARCHAR(500) NOT NULL,
    cohort_description TEXT,
    effective_from_date DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_to_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Data Quality Rule Definitions
DROP TABLE IF EXISTS silver.ref_dq_rule_definition CASCADE;
CREATE TABLE silver.ref_dq_rule_definition (
    dq_rule_id INT PRIMARY KEY,
    rule_name VARCHAR(255) NOT NULL,
    rule_description TEXT,
    rule_category VARCHAR(100),
    severity VARCHAR(50) CHECK (severity IN ('BLOCK', 'QUARANTINE', 'WARN', 'RECONCILE')),
    target_layer VARCHAR(50) CHECK (target_layer IN ('BRONZE', 'SILVER', 'GOLD')),
    target_table VARCHAR(255),
    affected_column VARCHAR(255),
    is_blocking BOOLEAN,
    is_active BOOLEAN DEFAULT TRUE,
    created_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Payment Status Mapping
DROP TABLE IF EXISTS silver.ref_payment_status_map CASCADE;
CREATE TABLE silver.ref_payment_status_map (
    payment_status_map_id INT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    source_payment_status VARCHAR(100) NOT NULL,
    conformed_payment_status VARCHAR(100) NOT NULL 
        CHECK (conformed_payment_status IN ('PENDING', 'PAID', 'FAILED', 'REFUNDED')),
    is_valid BOOLEAN DEFAULT TRUE,
    effective_from_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_payment_status, effective_from_date)
);
```

**2.3 Create Bronze Schema and Base Tables**

```sql
DROP SCHEMA IF EXISTS bronze CASCADE;
CREATE SCHEMA bronze;
COMMENT ON SCHEMA bronze IS 'Raw data from source, never updated, append-only, preserves source fidelity';

-- Template DDL for all 18 Bronze tables
-- For each source table, apply this pattern with table-specific columns
-- Example: br_orders

CREATE TABLE bronze.br_orders (
    dw_ingest_date DATE NOT NULL,
    dw_batch_id BIGINT NOT NULL,
    dw_ingest_ts_utc TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    dw_source_system VARCHAR(100) NOT NULL DEFAULT 'zwiggy_db',
    dw_source_schema VARCHAR(100) NOT NULL DEFAULT 'app',
    dw_source_table VARCHAR(255) NOT NULL DEFAULT 'orders',
    -- Source columns (exactly as in source)
    row_id UUID,
    order_id BIGINT,
    customer_id BIGINT,
    restaurant_id BIGINT,
    address_id BIGINT,
    total_price NUMERIC(18,10),
    order_date TIMESTAMP WITH TIME ZONE,
    order_status VARCHAR(100),
    payment_status BOOLEAN,
    is_cancelled BOOLEAN,
    tax_amount NUMERIC(10,10),
    cancellation_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    created_by VARCHAR(100),
    updated_at TIMESTAMP WITH TIME ZONE,
    updated_by VARCHAR(100),
    PRIMARY KEY (dw_batch_id, row_id)
);
CREATE INDEX idx_br_orders_batch ON bronze.br_orders(dw_batch_id);
CREATE INDEX idx_br_orders_date ON bronze.br_orders(dw_ingest_date);
CREATE INDEX idx_br_orders_src_key ON bronze.br_orders(order_id);
COMMENT ON TABLE bronze.br_orders IS 'Bronze: raw source data from orders table, unmodified';

-- Repeat for all 18 tables:
-- br_cart, br_cart_items, br_cuisines, br_customer, br_delivery_details,
-- br_delivery_partner, br_gender, br_menu_item, br_order_cancellation,
-- br_order_items, br_payments, br_refunds, br_restaurant, br_restaurant_cuisine,
-- br_restaurant_owner, br_reviews, br_user_address
-- (Actual DDL generation delegated to Python script in implementation)
```

**2.4 Create Silver Schema Skeleton**

```sql
DROP SCHEMA IF EXISTS silver CASCADE;
CREATE SCHEMA silver;
COMMENT ON SCHEMA silver IS 'Cleansed, conformed, typed, one row per business entity';

-- Create quarantine subschema
CREATE SCHEMA silver_quarantine;
COMMENT ON SCHEMA silver_quarantine IS 'Failed/disputed records with data quality issues';

-- Skeleton tables for 14 dimensions and 6 facts (DDL only, no data)
-- slv_customer, slv_address, slv_restaurant, slv_menu_item, slv_delivery_partner,
-- slv_cuisine, slv_restaurant_owner, slv_order_status, slv_payment_method,
-- slv_order_flag, slv_order, slv_order_item, slv_payment_attempt, slv_payment,
-- slv_delivery, slv_review, slv_cart, slv_cart_item
-- (Actual DDL generation delegated to Python script in implementation)
```

**2.5 Create Gold Schema Skeleton**

```sql
DROP SCHEMA IF EXISTS gold CASCADE;
CREATE SCHEMA gold;
COMMENT ON SCHEMA gold IS 'Dimensional model: dimensions, facts, aggregates, ready for BI consumption';

-- Skeleton tables for 14 dimensions (SCD2 with standard warehouse columns)
-- dim_customer, dim_address, dim_restaurant, dim_menu_item, dim_delivery_partner,
-- dim_cuisine, dim_restaurant_owner, dim_order_status, dim_payment_method,
-- dim_order_flag, dim_restaurant_cuisine
-- (Actual DDL generation delegated to Python script in implementation)

-- Skeleton tables for 6 fact tables
-- fact_order, fact_order_item, fact_payment_attempt, fact_payment,
-- fact_delivery, fact_review, fact_order_fulfilment, fact_cart_item
-- (Actual DDL generation delegated to Python script in implementation)

-- Aggregate Marts
-- mart_order_daily, mart_revenue_daily
-- (Actual DDL generation delegated to Python script in implementation)
```

## Phase 3: Configuration Population (Data)

**3.1 Populate Table Configuration Metadata**

Insert 18 rows into `control.ctl_table_config`, one per source table, with classification:

```
Table Name              | Primary Key    | Watermark Column | Strategy              | Look-Back | Initial Load
orders                  | order_id       | updated_at       | TIMESTAMP_WATERMARK   | 7         | true
order_items             | order_item_id  | updated_at       | TIMESTAMP_WATERMARK   | 7         | true
payments                | payment_id     | payment_date     | TIMESTAMP_WATERMARK   | 7         | true
delivery_details        | delivery_id    | delivery_time    | TIMESTAMP_WATERMARK   | 7         | true
reviews                 | review_id      | created_at       | CREATED_DATE_WATERMARK | 7        | true
cart                    | cart_id        | updated_at       | TIMESTAMP_WATERMARK   | 7         | true
cart_items              | cart_item_id   | updated_at       | TIMESTAMP_WATERMARK   | 7         | true
customer                | customer_id    | updated_at       | TIMESTAMP_WATERMARK   | 0         | true
user_address            | address_id     | updated_at       | TIMESTAMP_WATERMARK   | 0         | true
restaurant              | restaurant_id  | updated_at       | TIMESTAMP_WATERMARK   | 0         | true
menu_item               | menu_item_id   | updated_at       | TIMESTAMP_WATERMARK   | 0         | true
delivery_partner        | delivery_partner_id | updated_at  | TIMESTAMP_WATERMARK   | 0         | true
cuisines                | cuisine_id     | updated_at       | FULL_REFERENCE        | 0         | true
gender                  | id             | (none)           | FULL_SNAPSHOT         | 0         | true
order_cancellation      | cancellation_id| created_at       | CREATED_DATE_WATERMARK | 0        | true
restaurant_cuisine      | restaurant_cuisine_id | created_at | CREATED_DATE_WATERMARK | 0      | true
restaurant_owner        | owner_id       | updated_at       | TIMESTAMP_WATERMARK   | 0         | true
refunds                 | refund_id      | refund_date      | TIMESTAMP_WATERMARK   | 7         | true
```

**3.2 Populate Reference Conformance Mappings**

Insert order status mappings into `silver.ref_status_map`:

```
Source Value | Conformed Value | Status Group
Pending      | PENDING         | In Progress
PENDING      | PENDING         | In Progress
Completed    | COMPLETED       | Terminal
COMPLETED    | COMPLETED       | Terminal
Cancelled    | CANCELLED       | Terminal
CANCELLED    | CANCELLED       | Terminal
Delivered    | COMPLETED       | Terminal
PAID         | COMPLETED       | Terminal
```

Populate `silver.ref_cohort_rule`:

```
Cohort Name | Boundary Column | Operator | Boundary Value | Description
COHORT_A    | order_id        | <=       | 10928          | Early cohort: human vocabulary, complete line detail
COHORT_B    | order_id        | >        | 10928          | Late cohort: machine vocabulary, synthetic data
```

**3.3 Populate Data Quality Rules**

Insert 40+ DQ rule definitions into `control.ctl_dq_rule` and `silver.ref_dq_rule_definition`, covering:
- DQ-R1 through DQ-R24 from BRD-B §9
- Rules for Bronze: extract vs load row counts, manifest validation
- Rules for Silver: type validation, null handling, status conformance, cohort tagging
- Rules for Gold: dimension validity intervals, fact grain, as-at resolution, surrogate key fallback
- Quarantine and reconciliation rules

## Phase 4: Documentation and Validation

**4.1 Generate Technical Specification**

Create document: `DWH_TECHNICAL_SPECIFICATION.md`
- Control table schemas with full column definitions
- Standard warehouse column definitions (Appendix A from BRD-B)
- Naming conventions: schema, table, column prefixes
- Constraint and index strategy
- Retention and archival policies

**4.2 Generate Configuration Worksheet**

Create document: `TABLE_INGESTION_CONFIGURATION.csv`
- All 18 source tables with final ingestion strategies
- Watermark configuration per table
- Initial load status
- Dependency grouping for parallel execution

**4.3 Generate Data Dictionary**

Create document: `DATA_DICTIONARY.md`
- Source table: column definitions, data types, keys
- Bronze table: mirror of source plus technical columns
- Silver table: conformed column names, business keys, dq_flags
- Gold dimension: surrogate keys, SCD2 columns, validity intervals
- Gold fact: grain definition, dimension keys, metrics

**4.4 Validate Schema Creation**

Execute Python validation script:

```python
def validate_schemas_created():
    """Verify all schemas and core control tables exist"""
    expected_schemas = ['control', 'bronze', 'silver', 'silver_quarantine', 'gold']
    expected_control_tables = [
        'ctl_batch', 'ctl_table_config', 'ctl_watermark',
        'ctl_reconciliation', 'ctl_dq_rule', 'audit_run_log',
        'audit_source_extract'
    ]
    
    for schema in expected_schemas:
        result = query("SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s", (schema,))
        assert result, f"Schema {schema} not found"
    
    for table in expected_control_tables:
        result = query("SELECT table_name FROM information_schema.tables WHERE table_schema = 'control' AND table_name = %s", (table,))
        assert result, f"Control table {table} not found"
    
    # Verify control.ctl_table_config has 18 rows
    result = query("SELECT COUNT(*) as cnt FROM control.ctl_table_config")
    assert result[0]['cnt'] == 18, f"Expected 18 table configs, found {result[0]['cnt']}"
    
    # Verify reference data is populated
    result = query("SELECT COUNT(*) as cnt FROM silver.ref_status_map WHERE is_valid = true")
    assert result[0]['cnt'] > 0, "No valid status mappings found"
    
    return True
```

**4.5 Generate Operational Runbook**

Create document: `OPERATIONAL_RUNBOOK.md`
- Startup procedures: schema verification, control table checks
- Daily pipeline execution flow
- Failure recovery procedures: how to replay a batch
- Manual intervention procedures: how to quarantine and restore rows
- Scaling and maintenance: archival, purge policies

**4.6 Log Completion and Handoff**

Record in `control.audit_run_log`:
```
Event: SKILL_COMPLETED: dwh-metadata-and-foundations
Status: SUCCESS
Summary: All schemas, control tables, and reference data created and validated
Ready for: source-to-bronze-ingestion skill
```

# Technical Standards

## Data Warehouse Architecture

**Medallion Pattern** (Bronze → Silver → Gold):
- **Bronze**: Source fidelity layer, append-only, immutable, no business logic
- **Silver**: Conformed, typed, deduplicated entities, business rules applied exactly once
- **Gold**: Dimensional model (dimensions, facts), BI-ready, aggregates for performance

## Naming Conventions

**Schemas**:
- `control` - platform infrastructure
- `bronze` - raw data layer
- `silver` - cleansed/conformed layer
- `silver_quarantine` - data quality failures
- `gold` - dimensional model

**Tables**:
- Bronze: `br_<source_table_name>` (e.g., `br_orders`, `br_customer`)
- Silver: `slv_<entity_name>` (e.g., `slv_order`, `slv_customer`)
- Silver Reference: `ref_<reference_type>` (e.g., `ref_status_map`, `ref_cohort_rule`)
- Gold Dimensions: `dim_<entity_name>` (e.g., `dim_customer`, `dim_restaurant`)
- Gold Facts: `fact_<event_name>` (e.g., `fact_order`, `fact_payment`)
- Gold Aggregates: `mart_<subject>_<grain>` (e.g., `mart_order_daily`)
- Quarantine: `slv_<entity>_quarantine` (e.g., `slv_order_quarantine`)

**Columns**:
- Surrogate keys: `<entity>_sk` (e.g., `customer_sk`, `restaurant_sk`)
- Business keys: `<entity>_bk` or just the natural key (e.g., `order_id`, `customer_id`)
- Flags: `dq_flag_<issue>` (e.g., `dq_flag_cancel_mismatch`, `dq_flag_pending_but_paid`)
- Technical: `dw_*` prefix (e.g., `dw_batch_id`, `dw_ingest_ts_utc`)
- Date/time: `*_date` or `*_ts_utc` (e.g., `order_date`, `delivery_ts_utc`)

## Standard Warehouse Columns (Appendix A)

**All Bronze tables include**:
- `dw_ingest_date` DATE - partition column, business date of ingestion
- `dw_batch_id` BIGINT FK - which batch loaded this row
- `dw_ingest_ts_utc` TIMESTAMP - when ingestion occurred
- `dw_source_system` VARCHAR - which source (always 'zwiggy_db')
- `dw_source_schema` VARCHAR - which schema (always 'app')
- `dw_source_table` VARCHAR - which table in source

**All Silver tables include** (plus Bronze columns):
- `dw_source_hash` VARCHAR(64) - hash of source values for change detection
- `dw_row_hash` VARCHAR(64) - hash for SCD2 in Gold
- `dq_flag_<issue>` BOOLEAN - data quality flags (example: `dq_flag_cancel_mismatch`)
- `dw_source_cohort` VARCHAR(50) - which cohort (COHORT_A or COHORT_B)

**All Gold Dimension tables include** (SCD2):
- `<entity>_sk` BIGINT - surrogate key (auto-incremented)
- `<entity>_bk` BIGINT or VARCHAR - business key
- `dw_version_no` INT - which version in history
- `dw_row_hash` VARCHAR(64) - change detection
- `is_current` BOOLEAN - is this the active version?
- `valid_from_utc` TIMESTAMP - when this version became valid
- `valid_to_utc` TIMESTAMP - when this version expired
- `dw_initial_load` BOOLEAN - was this loaded at go-live?
- `dw_is_deleted` BOOLEAN - is the business key deleted in source?
- `dw_is_inferred` BOOLEAN - is this an inferred member (late-arriving dimension)?

**All Gold Fact tables include**:
- `<entity>_event_id` BIGINT - surrogate key for the fact
- `<entity>_date_key` INT - degenerate dimension for drill-through
- `<dimension>_sk` BIGINT FK - surrogate key to dimension
- `fact_event_ts_utc` TIMESTAMP - when the event occurred
- `dw_batch_id` BIGINT FK - which batch loaded this fact
- `dw_source_cohort` VARCHAR(50) - which cohort
- `dq_flag_dim_fallback` BOOLEAN - did dimension resolution fallback occur?

## Idempotency and Watermark Rules

**Watermark Advance Rules (§10.1 from BRD-B)**:
- X-2: Watermarks advance only after Bronze load AND reconciliation succeeds
- X-3: Extraction reads from replica or off-peak window; never locks OLTP
- X-5: Late-arriving data: look-back window of 7 days per table
- Re-running same batch must not create duplicate rows (batch_id + source_key uniqueness)

**Batch Idempotency Pattern**:
```python
# Pattern for any failed batch:
# 1. Do not advance watermark
# 2. Same batch ID can be re-run
# 3. Bronze is partitioned by dw_ingest_date and has PK (dw_batch_id, source_key)
# 4. Reload with same batch_id: DELETE then INSERT, or INSERT with conflict resolution
```

## Configuration-Driven Design

**ctl_table_config Drives Pipeline Behavior**:
- For each table: pipeline looks up strategy, watermark column, lookback days from config
- Adding new source table: insert row into `ctl_table_config`, no code change
- Changing strategy for table: update `ctl_table_config`, restart pipeline
- Deactivating table: set `is_active = false` in `ctl_table_config`

## Security Standards

**Credential Management**:
- Database credentials provided through environment variables or secret manager
- Never hardcoded in scripts or version control
- Connection strings include: host, port, database, schema, username, password/token reference
- Queries run with minimal necessary permissions: SELECT on source, DDL/DML on target

**PII Masking** (§12.2 from BRD-B):
- Customer phone_number, email, first_name, last_name: mask in Silver/Gold
- Delivery partner contact info: mask
- Restaurant owner contact: mask
- Method: replace with '***MASKED***' or hash in BI layer

## Logging and Observability

**Log Levels**:
- INFO: batch start, batch end, row counts, watermark advances
- WARN: reconciliation threshold breaches, data quality warnings
- ERROR: failed extractions, failed loads, schema drift, validation failures

**Audit Trail**:
- Every batch creation: logged to `control.audit_run_log`
- Every extraction: manifest saved to `control.audit_source_extract`
- Every reconciliation result: saved to `control.ctl_reconciliation`
- Every DQ rule evaluation: saved to `control.ctl_dq_rule` execution status

**Retention**:
- Control tables: indefinite
- Audit logs: 1 year minimum
- Bronze data: indefinite (minimum 25 months per BR-21)

## Data Quality and Reconciliation

**Mandatory Reconciliation Checks** (§9.4 from BRD-B):
- RC-1: Extract manifest row count = Bronze loaded rows (exactly)
- RC-2: Bronze rows = Silver loaded + quarantined + explicitly rejected (no gaps)
- RC-3: Silver rows = Gold facts loaded + deferred rows (accounts for grain changes)

**DQ Framework**:
- 40+ rules defined in `silver.ref_dq_rule_definition`
- Four severity levels: BLOCK, QUARANTINE, WARN, RECONCILE
- Blocking failures prevent publish (§10.3 release)
- Quarantined rows land with `dq_flag_*` columns and full payload in quarantine table

## Testing Standards

**Pre-Publication Checks**:
1. All 18 Bronze tables loaded (or intentionally empty)
2. All reconciliation checks pass (RC-1 through RC-10)
3. No blocking DQ rule violations
4. Watermarks advanced only on success
5. Batch marked COMPLETED or FAILED (never partial)

# Decision Rules

When implementing control table DDL:

1. **Watermark Strategy Decision**:
   - If table has `updated_at` that changes on every modification → TIMESTAMP_WATERMARK
   - If table has `created_at` but no update tracking and is append-only → CREATED_DATE_WATERMARK
   - If table has monotonic identity/sequence and is append-only → KEY_WATERMARK
   - If timestamps are non-unique and need tie-breaker → COMPOSITE_WATERMARK
   - If CDC available → CDC
   - If none of above and table is small/reference → FULL_REFERENCE
   - If none of above and table is small/transactional → FULL_SNAPSHOT
   - **Never invent a watermark strategy** - pick closest match or use FULL_SNAPSHOT

2. **Look-Back Window Decision**:
   - For transactional tables (orders, payments, delivery): 7 days (captures late-arriving data)
   - For master/reference tables (customer, restaurant): 0 days (assume no late arrivals)
   - For event/audit tables (reviews, cancellations): 0 days

3. **Initial Load Flag**:
   - All 18 tables: `is_initial_load_complete = FALSE` at start
   - After first successful initial load: set to TRUE
   - Prevents re-extraction of historical data on subsequent runs

4. **Active Flag**:
   - All 18 tables: `is_active = TRUE` at start
   - If a table must be skipped: set to FALSE
   - Pipeline always checks this before attempting extraction

5. **Dependency Grouping**:
   - Customer → User_Address (FK: customer_id)
   - Restaurant → Menu_Item (FK: restaurant_id)
   - Restaurant → Restaurant_Cuisine (FK: restaurant_id)
   - Restaurant → Restaurant_Owner (FK: restaurant_id)
   - Orders → Order_Items (FK: order_id)
   - Orders → Payments (FK: order_id)
   - Orders → Delivery_Details (FK: order_id)
   - Orders → Reviews (FK: order_id, menu_item_id)
   - Customer → Cart (FK: customer_id)
   - Cart → Cart_Items (FK: cart_id)
   - GroupA (independent): Gender, Cuisines
   - GroupB (master): Customer, User_Address, Restaurant, Delivery_Partner, Menu_Item, Restaurant_Cuisine, Restaurant_Owner
   - GroupC (transactional): Orders, Order_Items, Payments, Delivery_Details, Reviews, Cart, Cart_Items, Order_Cancellation, Refunds

6. **Control Table Constraints**:
   - Primary keys: use GENERATED ALWAYS AS IDENTITY for surrogate keys
   - Foreign keys: use DEFERRABLE for idempotency
   - Check constraints: enforce valid values (status, run_type)
   - Unique constraints: prevent duplicate config rows
   - Indexes: create on frequently queried columns (batch_id, table_name, status)

# Error-Handling Rules

**Validation Errors** (must stop execution):
- Source database unreachable → Log error, exit with status 1
- Target warehouse unreachable → Log error, exit with status 1
- Required credentials missing → Log error, exit with status 1
- Source table missing or schema mismatch → Log error, exit with status 1
- Row count mismatch (discovered vs expected) → Log warning, mark for investigation, continue

**Schema Creation Errors** (must handle):
- Schema already exists → DROP IF EXISTS, recreate (idempotent)
- Table already exists → DROP IF EXISTS, recreate
- Column type mismatch → Log error, show expected vs actual, halt
- Primary key violation → Should not occur on create, log and investigate
- Permission denied on CREATE → Log error with permission requirements, exit

**Configuration Errors** (must validate):
- Duplicate source table rows in ctl_table_config → Reject, log error
- Invalid ingestion_strategy value → Reject row, log error
- Missing watermark_column for TIMESTAMP_WATERMARK → Log warning, use default
- Circular dependency in table_group → Detect and log, break cycle

**Logging Errors** (must handle gracefully):
- Cannot write to audit_run_log → Log to stderr, continue (do not fail pipeline)
- Cannot insert to ctl_reconciliation → Log to stderr, continue
- Disk full on logging → Alert and continue (upstream of data)

# Validation Requirements

Before marking this skill COMPLETE, Antigravity must verify:

1. **Schema Validation**
   - All 5 schemas exist: control, bronze, silver, silver_quarantine, gold
   - All 7 control tables exist with correct structure
   - All reference tables exist: ref_status_map, ref_payment_status_map, ref_cohort_rule, ref_dq_rule_definition
   - Query each control table: SELECT COUNT(*) returns expected rows
   - Query each schema: SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '<schema>'

2. **Configuration Validation**
   - 18 rows in ctl_table_config, one per source table
   - All 18 rows have: source_table, ingestion_strategy, watermark_column, business_key, primary_key_column
   - All 18 rows have is_active = TRUE, is_initial_load_complete = FALSE
   - No duplicate (source_system, source_schema, source_table) combinations
   - All ingestion_strategy values valid (from enum)
   - Watermark columns actually exist in source (verify against source schema)

3. **Reference Data Validation**
   - Order status mapping covers: PENDING, COMPLETED, CANCELLED, PAID, Delivered variants
   - Cohort rule configured: COHORT_A for order_id <= 10928, COHORT_B for order_id > 10928
   - All status mappings marked is_valid = TRUE
   - Effective dates are valid (effective_from <= effective_to or to_date is null)

4. **Constraint Validation**
   - All FK relationships valid and deferrable
   - Check constraints enforced for status, run_type, severity
   - Unique constraints prevent duplicate configs
   - Primary key columns not null

5. **Idempotency Validation**
   - Run this script twice: should succeed both times, no errors
   - Second run should produce identical schema and data
   - No duplicate rows after second run

6. **Documentation Validation**
   - DWH_TECHNICAL_SPECIFICATION.md generated and complete
   - TABLE_INGESTION_CONFIGURATION.csv has 18 rows
   - DATA_DICTIONARY.md covers all entities
   - OPERATIONAL_RUNBOOK.md has procedures for startup, recovery, maintenance

# Expected Outputs

After successful execution, Antigravity will produce:

1. **Schema Objects**
   - 5 schemas: control, bronze, silver, silver_quarantine, gold
   - 7 control tables fully implemented
   - 4 reference tables with seed data
   - 18 bronze table skeletons (DDL only)
   - 14 silver table skeletons (DDL only)
   - 14 gold dimension table skeletons (DDL only, SCD2 structure)
   - 6 gold fact table skeletons (DDL only)
   - 2 gold aggregate mart skeletons (DDL only)

2. **Configuration Data**
   - ctl_table_config: 18 rows, one per source table, all strategies classified
   - ref_status_map: minimum 8 rows covering order status vocabulary
   - ref_payment_status_map: minimum 4 rows covering payment statuses
   - ref_cohort_rule: 2 rows for COHORT_A and COHORT_B
   - ref_dq_rule_definition: 40+ rows covering all DQ rules

3. **Indexes and Constraints**
   - Primary key indexes on all control tables
   - Foreign key relationships
   - Unique constraints on configuration key columns
   - Performance indexes on dw_batch_id, table_name, status

4. **Documentation**
   - `DWH_TECHNICAL_SPECIFICATION.md` - schema design, standards, column definitions
   - `TABLE_INGESTION_CONFIGURATION.csv` - 18-row matrix with strategy for each table
   - `DATA_DICTIONARY.md` - field-level definitions for source, bronze, silver, gold
   - `OPERATIONAL_RUNBOOK.md` - how to operate, recover, maintain the platform

5. **Audit Trail**
   - control.audit_run_log entry recording skill completion
   - Execution timestamp and summary

# Completion Criteria

This skill is COMPLETE when:

1. ✅ All 5 schemas created and verified to exist
2. ✅ All 7 control tables created, indexed, and validated
3. ✅ All 4 reference tables created with seed data
4. ✅ 18 entries in ctl_table_config with all source tables classified
5. ✅ Status and cohort reference data populated and verified
6. ✅ 18 bronze tables created (DDL only)
7. ✅ 14 silver tables created (DDL only)
8. ✅ 14 gold dimension tables created (DDL only)
9. ✅ 6 gold fact tables created (DDL only)
10. ✅ 2 gold aggregate marts created (DDL only)
11. ✅ All validation checks pass (schema counts, config rows, constraints)
12. ✅ All documentation generated
13. ✅ Idempotency validated (can run twice successfully)
14. ✅ Audit log entry created marking skill completion
15. ✅ No hardcoded credentials or secrets in any file
16. ✅ No incomplete TODO or TBD placeholders
17. ✅ Ready for handoff to source-to-bronze-ingestion skill

# Handoff to Other Skills

## Next Skill: source-to-bronze-ingestion

**When to Trigger**:
- After this skill completes successfully
- After all schemas, control tables, and reference data validated
- Before any source data extraction attempts

**What Must Be Available**:
- control.ctl_batch (empty, ready for runs)
- control.ctl_table_config (18 rows, all strategies classified)
- control.ctl_watermark (empty, ready for initial state)
- 18 bronze table skeletons created and ready to receive data
- Source connectivity confirmed working

**Information to Pass**:
- List of 18 source tables with their ingestion strategies
- Watermark column per table
- Primary key per table
- Look-back window per table
- Initial load flags (all set to FALSE)
- Configuration metadata query results
- Source row count baseline for reconciliation

**Handoff Communication**:
```
SKILL_COMPLETED: dwh-metadata-and-foundations
NEXT_SKILL: source-to-bronze-ingestion
READINESS_CHECK: All prerequisites satisfied
CONFIGURATION_SUMMARY:
- 18 source tables classified with ingestion strategies
- 7 control tables operational
- Reference data populated
- Bronze schema ready for data
ACTION: Proceed to source-to-bronze-ingestion skill
```

## Back to This Skill: If Errors During Ingestion

**Reasons to Return**:
- Configuration incorrect for a source table (watermark column wrong, strategy wrong)
- Missing reference data (status mapping missing)
- Control table schema inadequate (missing columns)
- Standard warehouse columns incomplete

**Corrections Possible**:
- Update ctl_table_config: change strategy, watermark column, look-back days, add missing config
- Insert missing reference data: add missing status mappings, conformance rules
- Add columns to control tables: if new audit requirement discovered

**How to Re-Handoff**:
- After correction, revalidate the corrected objects
- Run reconciliation check to ensure consistency
- Re-execute handoff communication
- Proceed with source-to-bronze-ingestion

# Prohibited Actions

Antigravity MUST NOT:

1. ❌ Hardcode database credentials or passwords anywhere
2. ❌ Create data in Bronze/Silver/Gold tables (this is DML, not DDL)
3. ❌ Extract or load any source data (belongs to source-to-bronze-ingestion)
4. ❌ Perform transformation or cleansing logic (belongs to bronze-to-gold-transformation)
5. ❌ Drop or modify any existing schemas without explicit confirmation
6. ❌ Create table-specific pipeline logic in control tables (keep it generic/configurable)
7. ❌ Assume table strategies without classification decision tree (per §34 of Functional Requirements)
8. ❌ Leave TODO, TBD, or "implement later" placeholders in DDL or documentation
9. ❌ Skip idempotency validation (run schema creation twice)
10. ❌ Omit audit trail for this skill execution
11. ❌ Implement secrets in reference data (all values must be non-sensitive)
12. ❌ Create non-configurable pipelines (all control must be in metadata, not code)
13. ❌ Alter data types of standard columns (always use specified types)
14. ❌ Skip documentation generation (runbook, dictionary, specification required)

# Final Response Format

After completing this skill, Antigravity must report:

## Summary
- Skill executed: dwh-metadata-and-foundations
- Status: COMPLETED or FAILED
- Execution time: <seconds>
- Execution date: <timestamp>

## Changes Made
- Schemas created: [list]
- Control tables created: [7 table names]
- Reference tables populated: [4 table names]
- Indexes created: [count]
- Foreign key constraints: [count]

## Validation Results
- Schema validation: PASS/FAIL with details
- Configuration validation: PASS/FAIL with row counts
- Reconciliation validation: PASS/FAIL
- Idempotency test: PASS/FAIL (run twice result)
- Documentation: COMPLETE/INCOMPLETE

## Files Generated
- DWH_TECHNICAL_SPECIFICATION.md: <path>
- TABLE_INGESTION_CONFIGURATION.csv: <path>
- DATA_DICTIONARY.md: <path>
- OPERATIONAL_RUNBOOK.md: <path>

## Artifacts
- control.ctl_batch: 0 rows (awaiting first run)
- control.ctl_table_config: 18 rows (all 18 source tables configured)
- silver.ref_status_map: [count] rows
- silver.ref_cohort_rule: 2 rows

## Assumptions
- [List any assumptions made, e.g., "Assumed all watermark columns exist in source"]
- [Any deviations from spec documented here]

## Pending Items
- [Any items unable to complete, with reason]
- [Configuration decisions awaiting business review]

## Readiness for Next Skill
- Source-to-Bronze Ingestion: READY (or list blocking issues)

## Audit Trail
- Batch ID created for this setup: [ID if applicable]
- Audit log entry: control.audit_run_log [entry details]

# Final Checklist

Antigravity must verify EVERY item before marking COMPLETE:

- ✅ All 5 schemas exist (control, bronze, silver, silver_quarantine, gold)
- ✅ 7 control tables created with all required columns
- ✅ All control tables have appropriate indexes
- ✅ Foreign key relationships defined
- ✅ Check constraints enforce valid values
- ✅ 4 reference tables created with seed data
- ✅ 18 source tables classified in ctl_table_config
- ✅ All ingestion strategies valid and documented
- ✅ Watermark columns verified against source schema
- ✅ 18 bronze tables exist (DDL only, no data)
- ✅ 14 silver tables exist (DDL only)
- ✅ 14 gold dimensions exist (DDL only)
- ✅ 6 gold facts exist (DDL only)
- ✅ 2 gold marts exist (DDL only)
- ✅ All standard warehouse columns applied correctly
- ✅ Idempotency validated (ran twice, no errors)
- ✅ DWH_TECHNICAL_SPECIFICATION.md generated
- ✅ TABLE_INGESTION_CONFIGURATION.csv generated (18 rows)
- ✅ DATA_DICTIONARY.md generated
- ✅ OPERATIONAL_RUNBOOK.md generated
- ✅ No hardcoded credentials anywhere
- ✅ No TODO/TBD/incomplete placeholders
- ✅ All sample data and reference values reviewed
- ✅ Audit log entry created for skill completion
- ✅ Configuration ready for source-to-bronze-ingestion skill
- ✅ Error handling strategy documented
- ✅ Security standards applied
- ✅ Logging standards applied
- ✅ Comments added to all objects for clarity
