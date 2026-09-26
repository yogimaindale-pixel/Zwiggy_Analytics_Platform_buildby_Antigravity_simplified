# Zwiggy Analytics Platform - Operational Runbook

## 1. Quick Start & Execution Commands

### Environment Setup
```bash
# Activate virtual environment
source venv/bin/activate

# Install package in editable mode
pip install -e .
```

### Complete Pipeline Execution
```bash
# Seed source DB, initialize DWH, run full Medallion pipeline end-to-end:
zwiggy-dwh run-all
```

---

## 2. Step-by-Step Step Execution

### Step 1: Seed Source Database
Populates source database (`app_*` tables) with 18 source tables, 336,751 rows, and Cohort A & B data anomaly profiles:
```bash
zwiggy-dwh seed-source
```

### Step 2: Initialize DWH Control Layer & Table Skeletons
Idempotently creates control tables, reference mappings, Bronze, Silver, Silver Quarantine, and Gold table schemas:
```bash
zwiggy-dwh init-db
```

### Step 3: Source-to-Bronze Ingestion
Extracts source data using metadata strategies and lands raw records into Bronze layer:
```bash
zwiggy-dwh ingest
```

### Step 4: Bronze-to-Gold Transformation
Executes Silver cleansing, status conformance, cohort tagging, DQ rules, SCD2 dimensions, and Gold facts:
```bash
zwiggy-dwh transform
```

### Step 5: Cross-Layer Reconciliation
Runs mandatory reconciliation checks (RC-1 through RC-10):
```bash
zwiggy-dwh reconcile
```

### Step 6: View Data Quality Scorecard
Displays data completeness, anomaly metrics, and quality scores:
```bash
zwiggy-dwh scorecard
```

---

## 3. Failure Recovery & Replay Procedure
1. If a batch fails, inspect `ctl_audit_run_log` for the error message.
2. The watermark in `ctl_watermark` is NOT advanced on failed batches, ensuring zero data loss.
3. Re-run the batch using `zwiggy-dwh run-all` or `zwiggy-dwh ingest`.
4. Idempotent deletion logic (`DELETE WHERE dw_batch_id = ?`) guarantees no duplicate rows are created on replay.
