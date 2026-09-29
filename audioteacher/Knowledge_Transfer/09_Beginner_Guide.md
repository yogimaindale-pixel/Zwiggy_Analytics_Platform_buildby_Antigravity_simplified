# 🐣 09. Step-by-Step Beginner Tutorial & Hands-on Guide

Welcome to **Lesson 09: Beginner Hands-On Tutorial**!

This tutorial is written specifically for engineers with 1 year of Python experience who want to run, inspect, and understand every layer of the Zwiggy Analytics Data Warehouse step-by-step.

---

## 🚀 Step 1: Environment Setup

1. Open your terminal and navigate to the project directory:
   ```bash
   cd /config/Desktop/Session1/Zwiggy_Analytics_Platform_buildby_Antigravity_simplified
   ```
2. Activate your Python environment and verify dependencies:
   ```bash
   python3 -m pip install -r requirements.txt
   ```

---

## 🧪 Step 2: Seed the Operational Source Database

Run the source seeder script to populate 18 synthetic operational OLTP tables:
```bash
python3 -m zwiggy_dwh.cli seed-source
```
* **What just happened?**: `seed_source.py` generated 61,777 realistic orders, 1,000 customers, 250 restaurants, 100 delivery partners, and payment records across Cohorts A and B.

---

## 🏗️ Step 3: Initialize Data Warehouse Infrastructure

Initialize all DWH schemas and control tables:
```bash
python3 -m zwiggy_dwh.cli init-db
```
* **What just happened?**: `init_db.py` executed DDL statements creating control tables (`ctl_batch_log`, `ctl_watermark`), Bronze raw tables (`br_*`), Silver clean tables (`sl_*`), Silver quarantine tables, and Gold Star Schema dimensions (`gd_dim_*`) and facts (`gd_fact_*`).

---

## 🔄 Step 4: Run the Complete E2E Pipeline

Execute the full 5-stage Medallion pipeline:
```bash
python3 -m zwiggy_dwh.cli run-all
```
* **Expected Output**:
  - `Step 1/5`: Ingested 235,591 rows into Bronze raw tables.
  - `Step 2/5`: Cleaned 221,407 rows into Silver clean tables.
  - `Step 3/5`: Evaluated Data Quality checks (99.2% completeness, 98.8% conformance).
  - `Step 4/5`: Built 64,165 rows in Gold Star Schema dimensions and facts.
  - `Step 5/5`: Passed 20 cross-layer reconciliation checks with 0.00% discrepancy.

---

## 🔬 Step 5: Query and Inspect Gold Star Schema

You can inspect the generated Gold Star Schema tables directly using SQLite CLI or Python:
```python
from zwiggy_dwh.db import connect, query_scalar

with connect() as conn:
    total_gmv = query_scalar(conn, "SELECT SUM(total_amount) FROM gd_fact_orders")
    total_orders = query_scalar(conn, "SELECT COUNT(*) FROM gd_fact_orders")
    print(f"Gold FactOrders GMV: ${total_gmv:,.2f} across {total_orders:,} orders!")
```
