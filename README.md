# Zwiggy-Antigravity Medallion Data Warehouse Platform

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Architecture](https://img.shields.io/badge/Architecture-Medallion%20(Bronze%2FSilver%2FGold)-green.svg)]()
[![Reconciliation](https://img.shields.io/badge/Reconciliation-100%25%20Pass-brightgreen.svg)]()
[![Tests](https://img.shields.io/badge/Tests-8%20Passed-success.svg)]()

The **Zwiggy-Antigravity Data Warehouse Platform** is an enterprise-grade Medallion Data Warehouse supporting incremental ingestion, status conformance, SCD Type 2 dimension versioning, mandatory cross-layer reconciliation contracts, data quality quarantine routing, automated health diagnostics, and a 10-day incremental simulation engine.

---

## 🚀 Quick Start

### 1. Installation & Environment Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

### 2. Execution Commands (`zwiggy-dwh`)
```bash
# Execute end-to-end baseline load (Seed -> Init DB -> Ingest -> Transform -> Reconcile)
zwiggy-dwh run-all

# Execute 10-day incremental data simulation and pipeline execution
zwiggy-dwh simulate-10-days

# Run operational health check diagnostic
zwiggy-dwh health-check

# View Data Quality Scorecard
zwiggy-dwh scorecard

# Run individual pipeline stages
zwiggy-dwh seed-source
zwiggy-dwh init-db
zwiggy-dwh ingest
zwiggy-dwh transform
zwiggy-dwh reconcile
```

### 3. Run Automated Tests (`pytest`)
```bash
PYTHONPATH=src ./venv/bin/pytest -v
```

---

## 🏛️ Medallion Architecture

```
+------------------+      +------------------+      +------------------+      +------------------+
|  Source (18 Tbls)| ===> |  Bronze (Raw)    | ===> |  Silver (Clean)  | ===> |   Gold (Star)    |
| Cohorts A & B    |      | Append-Only Tech |      | Conformed Status |      | 14 SCD2 Dims     |
| 336k+ Records    |      | Watermarks & MD5 |      | Quarantine Rules |      | 6 Facts / 2 Marts|
+------------------+      +------------------+      +------------------+      +------------------+
```

---

## 📚 Complete Documentation Catalog

1. 📖 **[KNOWLEDGE_TRANSFER_AND_ARCHITECTURE_GUIDE.md](file:///config/Desktop/Session4/KNOWLEDGE_TRANSFER_AND_ARCHITECTURE_GUIDE.md)**: Comprehensive KT manual, step-by-step pipeline execution walkthrough, module architecture catalog, and BI developer onboarding.
2. 🛠️ **[OPERATIONAL_HANDOFF_AND_TROUBLESHOOTING_GUIDE.md](file:///config/Desktop/Session4/OPERATIONAL_HANDOFF_AND_TROUBLESHOOTING_GUIDE.md)**: Daily operational checklist (5 AM, 6 AM, 7 AM UTC), 6 incident response playbooks, and monthly database maintenance runbook.
3. 📜 **[DWH_TECHNICAL_SPECIFICATION.md](file:///config/Desktop/Session4/DWH_TECHNICAL_SPECIFICATION.md)**: Deep-dive architecture design specification and DDL schemas.
4. 📊 **[TABLE_INGESTION_CONFIGURATION.csv](file:///config/Desktop/Session4/TABLE_INGESTION_CONFIGURATION.csv)**: 18-table ingestion strategy matrix.
5. 📖 **[DATA_DICTIONARY.md](file:///config/Desktop/Session4/DATA_DICTIONARY.md)**: Field-level data dictionary for all Bronze, Silver, and Gold tables.
6. 📋 **[OPERATIONAL_RUNBOOK.md](file:///config/Desktop/Session4/OPERATIONAL_RUNBOOK.md)**: Platform runbook and execution instructions.
