# Zwiggy Analytics Platform - Comprehensive Operational Handoff & Troubleshooting Guide

## 1. Executive Summary & Purpose
This document serves as the primary operational handoff manual, troubleshooting guide, knowledge base, and maintenance runbook for the **Zwiggy Analytics Platform Medallion Data Warehouse**.

---

## 2. Daily Operations Checklist

### Pre-Run Checklist (5:00 AM UTC - 1 hour before 6:00 AM batch)
- [ ] **Source System Connectivity**: Verify PostgreSQL/Source DB connection. Confirm recent orders present (`SELECT COUNT(*) FROM app_orders WHERE order_date >= CURRENT_DATE - 1`).
- [ ] **Target Database & Disk Space**: Ensure target warehouse storage utilization is < 80%.
- [ ] **Last Batch Execution Status**: Verify `ctl_batch.status = 'COMPLETED'` for the previous run.

### Run-Time Monitoring (6:00 AM - 7:00 AM UTC)
- [ ] Execute pipeline: `zwiggy-dwh run-all` or `zwiggy-dwh ingest && zwiggy-dwh transform`.
- [ ] Monitor extraction audit manifests in `ctl_audit_source_extract`.
- [ ] Monitor cross-layer reconciliation results in `ctl_reconciliation`.

### Post-Run Validation (7:00 AM - 7:15 AM UTC)
- [ ] Verify `ctl_batch.status = 'COMPLETED'`.
- [ ] Run health check: `zwiggy-dwh health-check`.
- [ ] Inspect DQ Scorecard: `zwiggy-dwh scorecard`.
- [ ] Confirm zero blocking reconciliation failures.

---

## 3. Incident Response & Troubleshooting Playbooks

### Playbook 1: Batch Status = FAILED
- **Diagnosis**: Query `ctl_audit_run_log WHERE severity = 'ERROR'` and `ctl_audit_source_extract WHERE extract_status != 'SUCCESS'`.
- **Resolution**:
  1. Determine if transient (network/timeout) or persistent (schema modification).
  2. If transient, re-run batch with replay mode: `zwiggy-dwh run-all`.
  3. Watermarks in `ctl_watermark` are automatically preserved on failure to guarantee zero data loss.

### Playbook 2: Reconciliation Check RC-1 Failure (Extract count ≠ Bronze count)
- **Diagnosis**: Query `ctl_reconciliation WHERE check_name = 'RC-1_EXTRACT_VS_BRONZE' AND result = 'FAIL'`.
- **Resolution**:
  1. If mismatch < 1%, log warning and investigate source records.
  2. If mismatch > 1%, check target column data type lengths or null constraints.
  3. Fix schema/mapping and re-run ingestion for the batch.

### Playbook 3: High Quarantine Rate (> 5%)
- **Diagnosis**: Query `slv_*_quarantine` grouped by `dq_rule_id`.
- **Resolution**:
  1. Identify if source system introduced invalid status codes or if data quality rule threshold is overly restrictive.
  2. If new status code, update `silver_ref_status_map`.
  3. Re-evaluate Silver layer transformation.

### Playbook 4: Overlapping SCD2 Validity Intervals
- **Diagnosis**: Query `dim_*` for `is_current = TRUE` with `COUNT(*) > 1` per business key.
- **Resolution**:
  1. Backup dimension table.
  2. Expire duplicate versions by setting `is_current = 0` and updating `valid_to_utc`.
  3. Re-run Gold fact transformation to repair dimension surrogate key assignments.

---

## 4. Maintenance & Performance Tuning

### Monthly Maintenance (First Sunday of Month, 2:00 AM UTC)
1. **Database Vacuum & Reindex**: Reclaim disk space and refresh optimizer statistics (`VACUUM ANALYZE`, `REINDEX`).
2. **Control Log Archiving**: Archive audit logs older than 1 year from `ctl_audit_run_log` and `ctl_audit_source_extract`.
3. **Watermark Audit**: Audit high-watermarks in `ctl_watermark` against source table max timestamps.

---

## 5. Frequently Asked Questions (FAQ)

**Q: How are Cohort A and Cohort B handled differently?**
A: `COHORT_A` (`order_id` ≤ 10,928) contains early testing data with human status vocabulary ("Pending", "Completed", "Cancelled", "PAID"). `COHORT_B` (`order_id` > 10,928) contains production machine vocabulary ("PENDING", "COMPLETED", "CANCELLED"). Silver transformation normalizes both cohorts into conformed status values.

**Q: How is Restaurant 214 treated?**
A: Restaurant 214 accounts for 87.1% of all orders (synthetic test outlier). In business reporting marts, Restaurant 214 should be analyzed separately or filtered depending on analytical requirements.

**Q: How do I query Gold SCD2 dimensions with Facts?**
A: Join fact tables to dimension tables on surrogate key (`*_sk`), or using as-at event date resolution:
```sql
SELECT f.order_id, f.amount, c.first_name, c.last_name
FROM gold.fact_order f
JOIN gold.dim_customer c ON f.customer_sk = c.customer_sk;
```

---

## 6. Handoff Contact Matrix

| Role | Contact Name | Escalation Responsibility |
|------|--------------|---------------------------|
| Lead Data Engineer | DWH Platform Team | Pipeline failures, code changes, schema evolution |
| Database Administrator | DBA Operations | Database connectivity, disk space, indexing |
| Business Analyst | BI Team | Semantic layer definitions, DQ rule recalibration |
