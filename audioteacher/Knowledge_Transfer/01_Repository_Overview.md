# 🎓 01. Repository Overview & Comprehensive Architecture Guide

Welcome to the **Zwiggy Analytics Platform Data Warehouse** audio learning course and architecture guide!

---

## 1. Executive Summary & Problem Statement

### 1.1 The Business Problem
In a fast-growing hyper-local food delivery platform like **Zwiggy**, millions of transactional events occur daily across customers, restaurants, delivery partners, orders, line items, payments, refunds, and customer reviews. 

Operational databases (OLTP systems like PostgreSQL or MySQL) are optimized for fast, single-row transactional writes and reads (e.g., placing an order, updating a delivery status). However, when business executives, growth analysts, or financial auditors attempt to run analytical queries over OLTP databases—such as *"What is the customer retention rate across Cohort A vs Cohort B over 90 days?"* or *"What is our gross merchandise value (GMV) by cuisine type per city?"*—the following critical failures occur:

1. **Severe Performance Degradation**: Complex analytical joins and table scans lock operational tables, causing latency spikes and checkout timeouts for active app users.
2. **Lack of Historical Point-in-Time Accuracy**: Operational tables continuously overwrite state (e.g., driver status changes from `ASSIGNED` to `DELIVERED`), destroying historical audit trails required for Slowly Changing Dimensions (SCD Type 2).
3. **Data Quality & Inconsistency**: Raw application data contains missing fields, unparsed JSON payloads, duplicate records, and invalid values (e.g., negative payment amounts or orphan orders).
4. **Lack of Unified Data Modeling**: Querying normalized 3NF OLTP schemas requires joining 15+ tables, leading to error-prone queries for business analysts.

---

## 2. Business Use Case & Solution Architecture

### 2.1 The Medallion Architecture Solution
The **Zwiggy Analytics Platform Data Warehouse** solves these challenges by implementing an enterprise **Medallion Data Lakehouse Architecture** powered by Python and SQLite/Relational SQL engines.

The platform ingests raw transactional data from 18 OLTP source tables into three progressive refinement layers:

```
[ OLTP Source Database ]
 (18 Tables, 336k+ Rows)
          |
          | Incremental Watermark Extraction (CDC)
          v
+-----------------------------------------------------------------------+
| BRONZE LAYER (br_*) - Raw Ingestion & Immutable Landing              |
| - Preserves raw JSON payloads, source line data, and batch IDs        |
| - Append-only audit trail with ingestion timestamps                   |
+-----------------------------------------------------------------------+
          |
          | Cleansing, Type Casting, Deduplication & DQ Validation
          v
+-----------------------------------------------------------------------+
| SILVER LAYER (sl_*) - Cleaned, Conformed & Quarantined Data           |
| - Standardized schemas, surrogate keys, PII masking                   |
| - Data Quality Firewall (Null checks, FK checks, range validation)    |
| - Failed records isolated in sl_quarantine                            |
+-----------------------------------------------------------------------+
          |
          | Dimensional Modeling (Star Schema) & Business Aggregation
          v
+-----------------------------------------------------------------------+
| GOLD LAYER (gd_*) - Business Intelligence & Analytical Marts           |
| - 14 Slowly Changing Dimensions (SCD Type 2 with effective dates)    |
| - 6 Fact Tables (FactOrders, FactPayments, FactDeliveries, etc.)       |
| - 2 Analytical Aggregation Marts (Cohort Metrics, Executive GMV)      |
+-----------------------------------------------------------------------+
```

---

## 3. Technology Stack

| Layer / Domain | Technology Choice | Rationale & Enterprise Usage |
| :--- | :--- | :--- |
| **Programming Language** | Python 3.10+ | Core orchestration, data transformation, CLI, and type safety (`typing`, `dataclasses`). |
| **Database Engine** | SQLite (Production-grade Relational SQL) | Embedded zero-dependency SQL engine supporting transactions, ACID compliance, and surrogate keys. |
| **Configuration** | `python-dotenv` & Dataclasses | Environment-based settings management with strict parsing and default fallback bounds. |
| **CLI Framework** | `argparse` | Native command-line interface for operational execution and scheduled cron orchestration. |
| **Testing Framework** | `pytest` | Automated unit, integration, and health diagnostic testing suites. |
| **Data Quality Engine** | Custom Python Rules Framework | Automated rule evaluation engine measuring completeness, uniqueness, referential integrity, and range bounds. |
| **Audit & Metadata** | SQLite Control Tables (`ctl_*`) | Centralized job execution logging, batch tracking, watermark management, and audit events. |

---

## 4. Folder Structure Breakdown

```
Zwiggy_Analytics_Platform_buildby_Antigravity_simplified/
├── audioteacher/                                       # Audio Learning Course & Knowledge Transfer Package
│   ├── Knowledge_Transfer/
│   │   ├── 01_Repository_Overview.md                  # Comprehensive Architecture & Overview Guide
│   │   ├── 02_Architecture.md                         # Detailed Medallion Architecture Specification
│   │   ├── 03_Concepts.md                             # Concept Cards (ETL, CDC, Medallion, Star Schema, etc.)
│   │   ├── 04_File_Mapping.md                         # Class, Function, and Line-Number Mapping Matrix
│   │   ├── 05_Line_By_Line_Explanation/               # Exhaustive line-by-line file explanations
│   │   ├── 06_Audio_Scripts/                          # TTS-Optimized Spoken Audio Lesson Scripts (Lesson 01-10)
│   │   ├── 07_Interview_Questions.md                  # Technical Q&A Bank with 30s/2m/Deep answers
│   │   ├── 08_Cheat_Sheet.md                          # Quick Reference, Formulas, and CLI Commands
│   │   ├── 09_Beginner_Guide.md                       # Step-by-Step Beginner Tutorial
│   │   └── 10_Senior_Engineer_Guide.md                # Enterprise Scaling & Extension Guide
│   └── audio/                                         # 10 Generated Voice MP3 Lessons (Lesson 01-10)
├── incremental_data/                                  # Daily JSON delta files for 10-day CDC simulation
├── src/
│   └── zwiggy_dwh/                                    # Primary Source Package
│       ├── __init__.py                                # Package initialization & version metadata
│       ├── config.py                                  # Settings, environment loading, database target paths
│       ├── db.py                                      # Database connection pool, wrapper, and retry logic
│       ├── init_db.py                                 # DWH schema initialization & control table seeding
│       ├── seed_source.py                             # Synthetic OLTP source data generator (61k+ orders)
│       ├── metadata.py                                # Metadata management, table discovery, & classifications
│       ├── batch.py                                   # Batch lifecycle & incremental watermark manager
│       ├── bronze.py                                  # Source-to-Bronze raw ingestion stage
│       ├── silver.py                                  # Bronze-to-Silver cleansing & quarantine stage
│       ├── dq.py                                      # Data Quality rule evaluation engine
│       ├── gold.py                                    # Silver-to-Gold Star Schema dimensional builder
│       ├── reconcile.py                               # Cross-layer row count & metric reconciliation engine
│       ├── pipeline.py                                # End-to-End master pipeline orchestrator
│       ├── simulate_incremental.py                    # 10-Day CDC incremental batch simulation harness
│       ├── health.py                                  # Operational health diagnostic engine
│       └── cli.py                                     # Command Line Interface entrypoint
├── tests/                                             # Automated Pytest Suite
│   ├── test_config.py                                 # Config loading unit tests
│   ├── test_db.py                                     # DB connection & wrapper tests
│   ├── test_foundations.py                            # Schema & table initialization tests
│   ├── test_pipeline.py                               # Full E2E pipeline execution tests
│   ├── test_incremental.py                            # CDC & watermark incremental tests
│   ├── test_health.py                                 # Health check diagnostic tests
│   └── test_cli.py                                    # Command Line Interface execution tests
├── TABLE_INGESTION_CONFIGURATION.csv                   # Table ingestion strategy configuration matrix
├── pyproject.toml                                     # Python package build configuration
├── requirements.txt                                   # Pinned Python package dependencies
├── DATA_DICTIONARY.md                                 # Column-level data dictionary for all layers
├── DOCUMENTATION.md                                   # General technical documentation
└── README.md                                          # Project quick-start & landed summary
```

---

## 5. Major Components & Subsystem Responsibilities

1. **Configuration Subsystem (`config.py`)**: Responsible for reading environment variables (`.env`), validating database file paths, and parsing execution parameters with strict defaults.
2. **Database Resilience Layer (`db.py`)**: Provides connection context managers, dictionary cursor wrappers, transaction commit/rollback safety, and automatic retry execution wrappers (`with_retry`).
3. **Control & Infrastructure Generator (`init_db.py`)**: DDL executor establishing 18 source tables, 18 Bronze tables, 18 Silver clean tables, 18 Silver quarantine tables, 14 Gold SCD2 dimensions, 6 Gold facts, 2 Gold marts, and control tables (`ctl_batch_log`, `ctl_watermark`, `ctl_dq_rules`, `ctl_audit_log`).
4. **Source Seeder (`seed_source.py`)**: Generates 61,777 realistic food delivery transactions across 1,000 customers, 250 restaurants, 100 delivery partners, line items, payments, and reviews over two distinct customer cohorts.
5. **Incremental Watermark Engine (`batch.py`)**: Manages batch lifecycle states (`STARTED`, `COMPLETED`, `FAILED`), tracks high-watermark timestamps per table, and logs audit events.
6. **Bronze Ingestion Engine (`bronze.py`)**: Extracts raw delta records from OLTP tables using watermark bounds and appends raw records with JSON payloads, batch IDs, and ingestion timestamps into Bronze tables.
7. **Silver Cleansing Engine (`silver.py`)**: Decodes raw payloads, casts data types, handles null replacement, masks PII (emails, phone numbers), generates business surrogate keys, and routes corrupted records to quarantine.
8. **Data Quality Engine (`dq.py`)**: Executes 7 mandatory validation checks (completeness, uniqueness, referential integrity, positive amounts) and produces batch quality scorecards.
9. **Gold Star Schema Dimensional Engine (`gold.py`)**: Constructs 14 SCD Type 2 dimensions with `effective_from`, `effective_to`, and `is_current` flags, 6 fact tables, and 2 analytical marts.
10. **Reconciliation Audit Engine (`reconcile.py`)**: Verifies row count consistency, metric sums, and orphan key counts between Source, Bronze, Silver, and Gold layers.
11. **Master Pipeline Orchestrator (`pipeline.py`)**: Coordinates the sequential execution of all 5 Medallion pipeline stages in a single unified execution loop.

---

## 6. Dependency Graph

```
                   +------------------------+
                   |       config.py        |
                   +------------------------+
                                |
                                v
                   +------------------------+
                   |         db.py          |
                   +------------------------+
                                |
        +-----------------------+-----------------------+
        |                       |                       |
        v                       v                       v
+---------------+       +---------------+       +---------------+
|  init_db.py   |       | seed_source.py|       |  metadata.py  |
+---------------+       +---------------+       +---------------+
        |                       |                       |
        +-----------------------+-----------------------+
                                |
                                v
                   +------------------------+
                   |        batch.py        |
                   +------------------------+
                                |
                                v
                   +------------------------+
                   |       bronze.py        |
                   +------------------------+
                                |
                                v
                   +------------------------+
                   |       silver.py        |
                   +------------------------+
                                |
                                v
                   +------------------------+
                   |         dq.py          |
                   +------------------------+
                                |
                                v
                   +------------------------+
                   |        gold.py         |
                   +------------------------+
                                |
                                v
                   +------------------------+
                   |      reconcile.py      |
                   +------------------------+
                                |
                                v
                   +------------------------+
                   |      pipeline.py       |
                   +------------------------+
                                |
                                v
                   +------------------------+
                   |         cli.py         |
                   +------------------------+
```
