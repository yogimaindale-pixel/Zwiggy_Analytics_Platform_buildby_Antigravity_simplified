# Zwiggy Analytics Platform (Simplified & Fully Commented Edition)

Welcome to the **Zwiggy Analytics Platform Simplified Edition**. This repository is an exact, simplified, and line-by-line commented mirror of the Zwiggy Analytics Platform Medallion Data Warehouse.

It is designed specifically for **junior developers**, **data engineers**, and **solutions architects** to learn, build, and run production-grade data pipelines locally without needing complex third-party tools or cloud credentials.

---

## 🌟 Key Highlights & Design Goals

1. **100% Standalone Python**: Runs on standard Python 3 (`sqlite3`, `json`, `hashlib`, `logging`, `argparse`). Zero external packages required for core execution!
2. **Line-by-Line Beginner Comments**: Every function, loop, parameter, and transformation step is thoroughly commented for immediate understanding.
3. **Complete Medallion Architecture**: Demonstrates Source Extraction, Bronze Raw Landing, Silver Status Conformance & Data Quality Quarantine, and Gold SCD Type-2 Star Schema Data Modeling.
4. **Interactive CLI**: Easy subcommands to run individual pipeline steps or the full end-to-end pipeline.

---

## ⚡ Quick Start (Run in 1 Minute!)

No `pip install` required for basic execution:

```bash
# 1. Clone the repository
git clone git@github.com:yogimaindale-pixel/Zwiggy_Analytics_Platform_buildby_Antigravity_simplified.git
cd Zwiggy_Analytics_Platform_buildby_Antigravity_simplified

# 2. Run the complete Medallion pipeline (Seed -> Init -> Ingest -> Transform -> Reconcile)
PYTHONPATH=src python3 src/zwiggy_dwh/cli.py run-all

# 3. Check operational health
PYTHONPATH=src python3 src/zwiggy_dwh/cli.py health-check

# 4. View Data Quality Scorecard
PYTHONPATH=src python3 src/zwiggy_dwh/cli.py scorecard

# 5. Simulate 10 days of incremental data ingestion
PYTHONPATH=src python3 src/zwiggy_dwh/cli.py simulate-10-days
```

---

## 🏛️ Medallion Pipeline Runflow

```
 +------------------------+      +------------------------+      +------------------------+      +------------------------+
 |   Operational Source   | ===> |      Bronze Layer      | ===> |      Silver Layer      | ===> |       Gold Layer       |
 |   (18 app_* tables)    |      |    (18 br_* tables)    |      |    (15 slv_* tables)   |      | (14 Dims, 6 Facts, Marts)
 |   61,777+ Raw Orders   |      | Landing JSON & Metadata|      | Conformed Status & DQ  |      | SCD2 Type-2 Star Model |
 +------------------------+      +------------------------+      +------------------------+      +------------------------+
```

---

## 📚 Comprehensive Documentation Index

* 📘 [DOCUMENTATION.md](file:///config/Desktop/Zwiggy_Analytics_Platform_buildby_Antigravity_simplified/DOCUMENTATION.md): Complete technical specification, schema catalog, business rules (BR-R1 to BR-R11), and reconciliation checks (RC-1 to RC-10).
* 🎓 [KNOWLEDGE_TRANSFER.md](file:///config/Desktop/Zwiggy_Analytics_Platform_buildby_Antigravity_simplified/KNOWLEDGE_TRANSFER.md): Junior developer onboarding guide, code walkthrough, and step-by-step KT manual.
