---
name: operations-and-knowledge-transfer
description: Comprehensive operational runbook, troubleshooting guide, knowledge base, and handoff documentation for operating, maintaining, and troubleshooting the Zwiggy Analytics Platform data warehouse in production. Use this skill to document operational procedures, resolve issues, and transfer knowledge to operations teams.
---

# Purpose

This skill provides comprehensive operational documentation for the Zwiggy Analytics Platform data warehouse. It captures operational procedures, troubleshooting guides, common issues and resolutions, performance tuning recommendations, security and compliance procedures, knowledge base articles, and all information necessary to hand off the platform to operations and support teams for long-term maintenance and optimization.

This skill is **not executed as part of initial build**, but rather **consulted during and after production operations** to guide troubleshooting, maintenance, and knowledge transfer.

# When to Use This Skill

- **Production troubleshooting**: Pipeline fails, data looks wrong, performance degrades
- **Operational procedures**: Daily monitoring, weekly maintenance, monthly reporting
- **Incident response**: Data quality alert, reconciliation failure, dimension mismatch
- **Knowledge transfer**: Onboarding new team members, documenting lessons learned
- **Performance optimization**: Slow queries, storage growth, refresh delays
- **Security/compliance**: Access reviews, PII audit, change management
- **Disaster recovery**: Restore from backup, replay batch, rebuild dimension history
- **Maintenance windows**: Schema updates, reference data fixes, capacity planning

# When Not to Use This Skill

- Do not use this to build the initial data warehouse (use dwh-metadata-and-foundations, source-to-bronze-ingestion, bronze-to-gold-transformation)
- Do not use this for first-time data ingestion (use source-to-bronze-ingestion)
- Do not use this for BI/dashboard configuration (BI Developer responsibility)
- Do not use this to modify source system (source data remediation is separate process)

# Project Context

**Platform**: Zwiggy Analytics Platform (Medallion Architecture Data Warehouse)  
**Operational Environment**: Production PostgreSQL databases, daily batch pipeline  
**Critical Success Factors**: Daily refresh at 6 AM UTC, <2% data quality issues, <1 second query latency for mart tables  
**Stakeholders**: Operations team, BI users, business analysts, data protection officer

**Key Operational Challenges**:
- Two incompatible data cohorts (COHORT_A vs COHORT_B) with different vocabularies
- One restaurant (id 214) is synthetic outlier (87% of orders)
- 11% orders have contradictory data (pending vs paid, cancelled vs flags)
- Missing payment/delivery records (3-4% orders incomplete)
- SCD2 dimension history must survive rollbacks and replays

**Service Level Objectives (SLOs)**:
- Pipeline availability: 99.5% (1 failure per 200 runs acceptable)
- Data freshness: Latest data available by 7 AM UTC
- Query latency: Dimension tables < 100ms, fact tables < 500ms, aggregates < 50ms
- Data quality: <2% rows quarantined, reconciliation 100% pass rate
- Recovery time objective (RTO): <30 minutes (replay latest batch)
- Recovery point objective (RPO): <24 hours (previous day available)

# Required Files to Read

Before consulting this skill, review:

1. **Technical Documentation** (created by dwh-metadata-and-foundations):
   - DWH_TECHNICAL_SPECIFICATION.md
   - TABLE_INGESTION_CONFIGURATION.csv
   - DATA_DICTIONARY.md
   - OPERATIONAL_RUNBOOK.md (output from Skill 1)

2. **Project Requirements** (original project documents):
   - BRD-A-BI-and-Analytics-v0.1.pdf (business context)
   - BRD-B-DWH-Medallion-Project-v0.1.pdf (technical architecture)
   - Functional Requirements.docx (ingestion specifications)
   - Source Schema Details.xlsx (column-level metadata)

3. **Production Logs** (generated during operations):
   - control.audit_run_log (execution history)
   - control.ctl_reconciliation (validation results)
   - control.ctl_batch (batch status)
   - gold.mart_dq_scorecard (daily quality metrics)

# Preconditions

Before using this skill, verify:

1. **Platform Is Deployed**:
   - All three build skills (Skill 1, 2, 3) completed successfully
   - All schemas created (control, bronze, silver, gold)
   - At least one successful daily batch completed
   - Data available in Gold layer for BI tools

2. **Observability Ready**:
   - audit_run_log populated with execution history
   - ctl_reconciliation populated with validation results
   - mart_dq_scorecard populated with daily metrics
   - Source database accessible for direct queries

3. **Team Resources**:
   - Database administrator with write access to control tables
   - Python developer for script modifications
   - BI developer for semantic layer questions
   - Business analyst for data interpretation

4. **Monitoring Infrastructure** (optional but recommended):
   - Log aggregation system (CloudWatch, ELK, Splunk)
   - Alerting system (PagerDuty, Opsgenie)
   - Performance monitoring (New Relic, DataDog)

# Responsibilities

This skill owns:

1. **Daily Operational Procedures**
   - Pre-flight checks before scheduled run
   - Monitoring during batch execution
   - Post-run validation and health checks
   - Alert escalation and incident response

2. **Troubleshooting Guide**
   - Common failures: extraction timeouts, reconciliation mismatches, dimension misses
   - Root cause analysis: where to look, what to check, how to diagnose
   - Resolution procedures: fix steps, testing, re-run procedures
   - Prevention: how to avoid recurring issues

3. **Data Quality Troubleshooting**
   - Understanding quarantine rows
   - Interpreting DQ scorecard metrics
   - Investigating rule failures
   - Remediating and replaying affected data

4. **Performance Tuning**
   - Query optimization: indexing, partitioning, statistics
   - Batch optimization: parallelization, chunk sizing
   - Storage optimization: compression, partitioning, retention

5. **Maintenance Procedures**
   - Reference data updates (status mappings, cohort rules)
   - Archive and purge (old control records, old data)
   - Schema evolution (adding new columns, new tables)
   - Backup and restore procedures

6. **Security and Compliance**
   - Access control: who can query what
   - PII masking verification
   - Change management: tracking modifications
   - Compliance: audit trails, data protection

7. **Knowledge Base**
   - Documented answers to frequently asked questions
   - Lessons learned from incidents
   - Best practices and anti-patterns
   - Reference implementation examples

8. **Handoff Documentation**
   - Runbook for operations team
   - Architecture overview for new team members
   - Organizational knowledge capture
   - Training materials and demonstrations

# Step-by-Step Operational Procedures

## Part 1: Daily Operations Checklist

### Pre-Run (5 AM UTC, 1 hour before scheduled 6 AM execution)

```
[ ] 1. Verify source system connectivity
      - Connect to PostgreSQL 18.1 source
      - Run: SELECT COUNT(*) FROM app.orders WHERE order_date >= CURRENT_DATE - 1
      - Confirm row count is plausible (>100 new orders/day expected)
      - If failed: investigate source DB status, network connectivity, credentials

[ ] 2. Verify target warehouse availability
      - Connect to target database/storage
      - Run: SELECT COUNT(*) FROM control.ctl_batch WHERE batch_start_ts_utc >= CURRENT_TIMESTAMP - 1
      - Confirm connection works, basic queries respond
      - If failed: investigate target DB status, disk space, connectivity

[ ] 3. Check control table state
      - Run: SELECT MAX(batch_start_ts_utc), status FROM control.ctl_batch LIMIT 1
      - Confirm last batch status = 'COMPLETED' (not FAILED or IN_PROGRESS)
      - If FAILED: review previous batch logs, determine if replayable or needs investigation
      - If IN_PROGRESS: investigate if batch is truly running or hung; may need manual intervention

[ ] 4. Review previous day's metrics
      - Run: SELECT * FROM gold.mart_dq_scorecard ORDER BY created_ts DESC LIMIT 1
      - Check: cohort mix, restaurant concentration, quarantine counts
      - Compare to baseline: significant changes may indicate data issue
      - Note: which rules failed, which tables quarantined

[ ] 5. Verify disk space
      - Bronze schema size: SELECT pg_size_pretty(pg_total_relation_size('bronze')) (if PostgreSQL)
      - Silver schema size: SELECT pg_size_pretty(pg_total_relation_size('silver'))
      - Gold schema size: SELECT pg_size_pretty(pg_total_relation_size('gold'))
      - If usage > 80% capacity: escalate to DBA, may need purge/archive
      - If usage growth > 20% day-over-day: unusual, investigate data issue

[ ] 6. Review alerts and warnings from overnight
      - Check email/Slack/PagerDuty for any alerts (failed extractions, late data arrival)
      - Review error logs: SELECT * FROM control.audit_run_log WHERE severity='ERROR' AND logged_ts > CURRENT_TIMESTAMP - 24 HOURS
      - For each error: categorize as transient (network) or persistent (schema, logic)
      - Escalate persistent errors before running today's batch
```

### Run-Time Monitoring (6 AM – 6:45 AM UTC)

```
[ ] 1. Start pipeline execution
      - Execute: python run_ingestion_pipeline.py --run_type INCREMENTAL --triggered_by SCHEDULER
      - Capture: batch_id for this run
      - Start time: log the batch_start_ts_utc
      - Expected duration: 30-45 minutes for daily incremental run

[ ] 2. Monitor table extraction (6:00 – 6:30 AM)
      - Every 5 minutes: SELECT source_table, extract_row_count, extract_status 
                         FROM control.audit_source_extract 
                         WHERE dw_batch_id = <current_batch_id>
      - Confirm all 18 tables showing extract_row_count > 0 or status='SUCCESS'
      - Any table stuck (extract_start_ts > 5 min ago but no complete): may indicate lock/timeout
      - If timeout: check source DB for queries, locks, or performance issues

[ ] 3. Monitor Bronze load (6:30 – 6:40 AM)
      - SELECT source_table, load_row_count FROM bronze 
              WHERE dw_batch_id = <current_batch_id>
      - Confirm row counts loading to Bronze
      - Any null load_row_count: load may still in progress

[ ] 4. Monitor reconciliation (6:40 – 6:45 AM)
      - SELECT check_name, result, COUNT(*) as count 
        FROM control.ctl_reconciliation 
        WHERE dw_batch_id = <current_batch_id>
        GROUP BY check_name, result
      - Confirm: all checks show result='PASS'
      - Any FAIL: note which check, which table, investigate after batch completes

[ ] 5. Monitor transformation (6:45 – 7:15 AM)
      - SELECT COUNT(*) FROM silver.slv_order WHERE dw_batch_id = <current_batch_id>
      - SELECT COUNT(*) FROM gold.fact_order WHERE dw_batch_id = <current_batch_id>
      - Confirm Silver and Gold tables being populated
      - Monitor data quality: SELECT COUNT(*) FROM gold.mart_dq_scorecard WHERE created_ts > CURRENT_TIMESTAMP - 1 HOUR
```

### Post-Run Validation (7:15 AM – 7:30 AM UTC)

```
[ ] 1. Verify batch completion
      - Query: SELECT batch_end_ts_utc, status FROM control.ctl_batch WHERE dw_batch_id = <current_batch_id>
      - Confirm: status = 'COMPLETED' and batch_end_ts_utc is populated
      - If status = 'FAILED': jump to Troubleshooting section below

[ ] 2. Verify all 18 tables loaded
      - For each table: SELECT COUNT(*) FROM bronze.br_<table> WHERE dw_batch_id = <current_batch_id>
      - Compare to previous day's counts (should be similar for steady-state tables)
      - If 0 rows (but expected > 0): possible extraction failure, check audit_source_extract
      - If negative change > 20%: possible data issue, investigate source

[ ] 3. Verify reconciliation passed
      - Query: SELECT result, COUNT(*) FROM control.ctl_reconciliation WHERE dw_batch_id = <current_batch_id> GROUP BY result
      - Confirm: all results = 'PASS', count = expected (usually 20-30 checks)
      - Any FAIL: record which check failed, flag for investigation

[ ] 4. Verify DQ scorecard published
      - Query: SELECT * FROM gold.mart_dq_scorecard WHERE dw_batch_id = <current_batch_id>
      - Confirm: scorecard has all metrics (cohort_a_count, cohort_b_count, etc.)
      - Review: quarantine counts, restaurant_concentration
      - Alert if: restaurant_concentration > 88% (change from 87% baseline) or quarantine > 5%

[ ] 5. Notify stakeholders
      - BI users: "Daily data refresh complete, Gold layer available for queries"
      - Business analyst: "DQ scorecard available, see <link>"
      - Data protection officer: "Reconciliation complete, 0 blocking issues"
      - If issues: notify immediately with issue description and ETA for resolution

[ ] 6. Log completion in operations log
      - Record in shared log/wiki: "Batch <id> completed at 7:15 AM, 18 tables loaded, all reconciliation passed"
      - Note any anomalies: "Orders up 10% from yesterday (seasonal?)"
      - Note any alerts: "Payment dimension missing 5 keys, added to dim_fallback"
```

## Part 2: Troubleshooting Guide

### Issue 1: Batch Status = FAILED (Entire pipeline failed)

**Symptoms**:
- control.ctl_batch.status = 'FAILED'
- control.audit_run_log has ERROR entries
- No data in Silver/Gold tables for this batch

**Root Cause Analysis**:

```sql
-- Step 1: Get error messages
SELECT event_type, message, severity 
FROM control.audit_run_log 
WHERE dw_batch_id = <batch_id> AND severity = 'ERROR'
ORDER BY logged_ts;

-- Step 2: Identify failed table (if any)
SELECT source_table, extract_status, error_message 
FROM control.audit_source_extract 
WHERE dw_batch_id = <batch_id> AND extract_status != 'SUCCESS';

-- Step 3: Check reconciliation failures
SELECT source_table, target_table, check_name, result, details 
FROM control.ctl_reconciliation 
WHERE dw_batch_id = <batch_id> AND result = 'FAIL';
```

**Common Causes and Resolutions**:

| Cause | Symptom | Resolution |
|-------|---------|-----------|
| Source DB unreachable | audit_run_log: "Cannot connect to source" | Check PostgreSQL 18.1 is up, network is accessible, credentials valid |
| Target DB unreachable | audit_run_log: "Cannot connect to target" | Check target DB is up, storage is available, credentials valid |
| Extract timeout on large table | audit_source_extract.error_message: "Query timeout" | Increase query timeout (currently 60s), check source DB for locks, consider narrower look-back window |
| Reconciliation check failed | ctl_reconciliation.result='FAIL', details show count mismatch | Review which rows were extracted but not loaded; may indicate data type conversion issue or constraint violation |
| Duplicate primary key | audit_run_log: "Unique constraint violated" | Check if batch_id already exists from previous run; may need to clean up aborted batch |
| Schema changed in source | audit_run_log: "Column not found" | Verify source schema matches expected; may need to update ctl_table_config if new column added |

**Resolution Procedure**:

```
Step 1: Determine recoverability
  - If transient (network, timeout, lock): PROCEED to Step 2 (replay)
  - If persistent (schema, logic): HALT, escalate to engineer

Step 2: Replay the batch
  - Delete aborted data: DELETE FROM bronze.br_* WHERE dw_batch_id = <batch_id>
  - Reset batch status: UPDATE control.ctl_batch SET status='IN_PROGRESS', batch_end_ts_utc=NULL WHERE dw_batch_id = <batch_id>
  - Do NOT reset watermarks (X-2: keep them unchanged for retry)
  - Re-execute: python run_ingestion_pipeline.py --run_type REPLAY --batch_id <batch_id>

Step 3: Verify replay success
  - Check: control.ctl_batch.status = 'COMPLETED' for this batch
  - Confirm: all 18 tables reloaded
  - Validate: reconciliation all PASS
  - Proceed to next batch or alert if still failing

Step 4: If replay fails again
  - Escalate to engineer: provide batch_id, all logs, and error messages
  - Do NOT attempt manual fixes without investigation
  - Consider using previous day's successful batch as baseline for BI users
```

### Issue 2: Reconciliation Check RC-1 Fails (Extract count ≠ Bronze load count)

**Symptoms**:
- control.ctl_reconciliation has RC-1 row with result='FAIL'
- Details show: "Extract: 1000, Bronze: 999"
- Source has data but not all loaded

**Root Cause Analysis**:

```sql
-- Step 1: Get the mismatch details
SELECT source_table, extract_row_count, target_row_count, details 
FROM control.ctl_reconciliation 
WHERE dw_batch_id = <batch_id> AND check_name = 'RC-1_EXTRACT_VS_BRONZE';

-- Step 2: Query manifest vs actual
SELECT extract_row_count, load_row_count 
FROM bronze.br_<table> 
WHERE dw_batch_id = <batch_id> LIMIT 1;

-- Step 3: Check if specific rows failed to insert
SELECT COUNT(*) FROM bronze.br_<table> WHERE dw_batch_id = <batch_id>;

-- Step 4: Look for rejected rows (if captured)
SELECT * FROM control.audit_run_log 
WHERE dw_batch_id = <batch_id> AND source_table = '<table>' AND severity = 'WARN'
ORDER BY logged_ts;
```

**Common Causes**:

| Cause | Indicator | Resolution |
|-------|-----------|-----------|
| Data type conversion error | None of a specific column datatype loaded | Check column data type: is VARCHAR(100) field receiving value >100 chars? Cast to longer VARCHAR |
| Null constraint violation | Rows with NULL in NOT NULL column | Check source: are required columns null? Update dq_flag to mark, allow NULL in Bronze |
| Primary key violation | Same batch_id + source_key inserted twice | Idempotent load should have handled; check if cleanup failed from previous aborted run |
| Late-arriving data | New row inserted after extraction completed | Expected for 7-day look-back window; reconciliation should show row in next batch |

**Resolution Procedure**:

```
Step 1: Determine if fixable
  - If count difference < 1%: log as warning, continue (acceptable data loss within threshold)
  - If count difference > 1%: stop, escalate to investigation

Step 2: Investigate specific rows
  - Find which rows didn't load:
    SELECT * FROM source.app.<table> WHERE updated_at BETWEEN <watermark_window>
    EXCEPT
    SELECT source_columns FROM bronze.br_<table> WHERE dw_batch_id = <batch_id>
  - Check: why didn't these load? Data type issue? Constraint issue?

Step 3: Fix and retry
  - Fix the root cause (e.g., increase VARCHAR length, add dq_flag)
  - Re-run extraction for this table using manual query
  - Load to Bronze with same batch_id (idempotent)
  - Re-run reconciliation check

Step 4: Document
  - Update incident log with root cause and resolution
  - If systemic: update ctl_table_config or source schema analysis
  - Add to monthly review: prevent recurrence
```

### Issue 3: Dimension Key Mismatch (dq_flag_dim_fallback > 1%)

**Symptoms**:
- Gold fact table has many dq_flag_dim_fallback = TRUE
- fact_order.customer_sk = -1 for many rows (10%+)
- Gold.mart_dq_scorecard shows "Dimension fallback: 8%"

**Root Cause Analysis**:

```sql
-- Step 1: Identify missing dimension keys
SELECT customer_id, COUNT(*) as count 
FROM gold.fact_order 
WHERE customer_sk = -1 AND dw_batch_id = <batch_id>
GROUP BY customer_id
ORDER BY count DESC;

-- Step 2: Check if customer exists in Silver
SELECT * FROM silver.slv_customer 
WHERE customer_id IN (123, 456, 789)  -- from above query
AND dw_batch_id = <batch_id>;

-- Step 3: Check if dimension member exists in Gold
SELECT * FROM gold.dim_customer 
WHERE customer_id IN (123, 456, 789)
ORDER BY valid_from_utc DESC;

-- Step 4: Check if it's a late-arriving dimension
SELECT * FROM gold.dim_customer 
WHERE dw_is_inferred = TRUE
AND customer_id IN (123, 456, 789);
```

**Common Causes**:

| Cause | Indicator | Resolution |
|-------|-----------|-----------|
| Late-arriving dimension | dim.dw_is_inferred=TRUE, Bronze has order before customer | Expected for 1-2%; next day dimension load enriches inferred member |
| Extraction order wrong | Customer table didn't load before orders | Check: Group B (master) must load before Group C (transactions); verify dependency order |
| Dimension extraction failed | slv_customer.dw_batch_id is NULL or missing | Check: did customer extraction complete? Query control.audit_source_extract |
| Deleted customer | Original customer_id doesn't exist in current snapshot | Normal: SCD2 marks as dw_is_deleted=TRUE; fallback is expected |
| Cohort boundary issue | All missing are COHORT_B orders | Check: cohort tagging correct? Verify boundary_value in ref_cohort_rule |

**Resolution Procedure**:

```
Step 1: Assess impact
  - If < 1%: expected (late-arriving dimensions), monitor closely
  - If 1-5%: investigate cause, may need schema fix
  - If > 5%: halt Gold layer publication, escalate to engineer

Step 2: For late-arriving dimensions
  - No action needed today (dimension load next batch enriches it)
  - Document in scorecard: "8 customers created after first order, enriched on day 2"
  - Verify: next batch's reconciliation shows these now resolved

Step 3: For extraction order issues
  - Check: ctl_table_config.table_group
  - Verify: Group B tables load before Group C tables
  - If not: update table_group assignment, re-run entire pipeline

Step 4: For deleted customers
  - Verify: SCD2 marked dw_is_deleted=TRUE
  - Expected: old orders still reference the (deleted) customer version at order_date
  - No fix needed: this is correct SCD2 behavior

Step 5: Document
  - Record: which customers, when detected, root cause
  - Update: dimension quality baseline (currently accept <1%)
```

### Issue 4: Data Quality Quarantine Rate High (>5%)

**Symptoms**:
- gold.mart_dq_scorecard shows quarantine_count > 5% of total
- silver.slv_<entity>_quarantine has many rows
- BI queries return 95% of expected rows

**Root Cause Analysis**:

```sql
-- Step 1: Which entities are quarantined?
SELECT 'order' as entity, COUNT(*) as count FROM silver.slv_order_quarantine WHERE dw_batch_id = <batch_id>
UNION ALL
SELECT 'payment', COUNT(*) FROM silver.slv_payment_quarantine WHERE dw_batch_id = <batch_id>
UNION ALL
SELECT 'customer', COUNT(*) FROM silver.slv_customer_quarantine WHERE dw_batch_id = <batch_id>
ORDER BY count DESC;

-- Step 2: Which DQ rules are failing?
SELECT dq_rule_id, COUNT(*) as count 
FROM silver.slv_<entity>_quarantine 
WHERE dw_batch_id = <batch_id>
GROUP BY dq_rule_id
ORDER BY count DESC;

-- Step 3: What are the specific failures?
SELECT dq_rule_id, dq_reason, COUNT(*) as count 
FROM silver.slv_<entity>_quarantine 
WHERE dw_batch_id = <batch_id>
GROUP BY dq_rule_id, dq_reason;
```

**Common Causes**:

| Cause | Indicator | Resolution |
|-------|-----------|-----------|
| Source data degradation | Suddenly high quarantine (was <1%, now >5%) | Check source DB: bad data load? Changed validation? Communicate with source owner |
| Mapping missing | Specific status values not in ref_status_map | Add mapping to ref_status_map, re-run batch for this table |
| Rule threshold too tight | Rule flags 5% of orders as "pending but paid" normally | Re-baseline rule: check if 5% is expected, adjust threshold or accept as normal |
| Schema change in source | New column causing type mismatch | Update Bronze DDL, update ctl_table_config, re-run extraction |

**Resolution Procedure**:

```
Step 1: Assess severity
  - If quarantine > 10%: halt publication, escalate to business analyst
  - If 5-10%: publish with warning, investigate root cause
  - If < 5%: publish normally, track trend over time

Step 2: Investigate specific rules
  - For each failing rule: review dq_reason
  - Categorize: rule is working as designed? Or rule is too strict?
  - Check: is this expected for this data? (e.g., pending_but_paid is 7,019 rows = 11%)

Step 3: Fix source or rule
  Option A (Fix Source): If source data error, communicate with source owner
    - Remediate source: fix bad data
    - Re-run batch (replay last batch_id)
    - Quarantine should decrease
  
  Option B (Fix Rule): If rule is too strict, recalibrate
    - Update silver.ref_dq_rule_definition: adjust severity or threshold
    - Change BLOCK to QUARANTINE or WARN if not truly blocking
    - Re-run DQ evaluation
    - Document business decision: why rule relaxed

Step 4: Replay and retest
  - After fix: DELETE FROM silver.slv_<entity>_quarantine WHERE dw_batch_id = <batch_id>
  - Re-run transformation: python run_transformation_pipeline.py --batch_id <batch_id>
  - Verify: quarantine counts decreased

Step 5: Document
  - Log incident: date, cause, resolution, business impact
  - Update: DQ rule definitions document
  - Add to: knowledge base for operations team
```

### Issue 5: SCD2 Dimension Has Overlapping Validity Intervals (Data Corruption)

**Symptoms**:
- Query returns multiple is_current=TRUE rows for same business_key
- Two versions overlap in validity date range
- As-at join returns wrong version for specific event_date

**Root Cause Analysis**:

```sql
-- Step 1: Identify the dimension with overlaps
SELECT customer_id, COUNT(*) as version_count, COUNT(DISTINCT is_current) as current_count
FROM gold.dim_customer
WHERE is_current = TRUE
GROUP BY customer_id
HAVING COUNT(*) > 1;

-- Step 2: See the overlapping versions
SELECT customer_id, customer_sk, valid_from_utc, valid_to_utc, is_current, dw_version_no
FROM gold.dim_customer
WHERE customer_id = <affected_customer_id>
ORDER BY valid_from_utc, customer_sk;

-- Step 3: Check if gap exists (non-overlapping but gapped)
SELECT customer_id, valid_to_utc as gap_start, 
       LEAD(valid_from_utc) OVER (PARTITION BY customer_id ORDER BY valid_from_utc) as gap_end
FROM gold.dim_customer
WHERE customer_id = <affected_customer_id>
AND valid_to_utc IS NOT NULL
AND LEAD(valid_from_utc) OVER (PARTITION BY customer_id ORDER BY valid_from_utc) > valid_to_utc;
```

**Common Causes**:

| Cause | Indicator | Resolution |
|-------|-----------|-----------|
| Failed SCD2 merge (duplicate key issue) | Multiple is_current=TRUE, same batch_id | Idempotent merge failed; dimension loaded twice in same batch |
| Replay without cleanup | Two versions from two separate batches overlapping | Replay didn't delete old versions; manual cleanup needed |
| Manual intervention (INSERT) | Versions inserted outside of merge logic | Check audit trail: who inserted? Undo and use merge logic |
| Constraint not enforced | No unique constraint on (business_key, is_current) | Add constraint to prevent future duplicates |

**Resolution Procedure**:

```
Step 1: BACKUP IMMEDIATELY
  - Create snapshot of dimension table
  - Export to CSV: SELECT * FROM gold.dim_customer ORDER BY customer_sk
  - Save to: /backups/dim_customer_<date>_<batch_id>.csv

Step 2: Investigate root cause
  - Check: control.audit_run_log for errors during dimension load
  - Check: was dimension reloaded (loaded twice in same batch)?
  - Look for: manual INSERTs or UPDATEs outside of pipeline

Step 3: Clean up
  - Delete duplicate is_current versions:
    DELETE FROM gold.dim_customer
    WHERE customer_sk IN (
      SELECT customer_sk FROM (
        SELECT customer_sk, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY customer_sk DESC) as rn
        FROM gold.dim_customer
        WHERE customer_id = <affected_customer_id> AND is_current = TRUE
      ) WHERE rn > 1
    )
  - Verify: SELECT COUNT(*) FROM gold.dim_customer WHERE customer_id = <affected_customer_id> AND is_current = TRUE
  - Should return exactly 1

Step 4: Repair as-at joins
  - Facts using this dimension may have wrong version
  - Rebuild affected facts: DELETE FROM gold.fact_order WHERE customer_sk = <wrong_sk>
  - Re-run transformation: python run_transformation_pipeline.py --batch_id <batch_id>

Step 5: Add constraint to prevent future
  - ALTER TABLE gold.dim_customer ADD CONSTRAINT uk_dim_customer_current UNIQUE (customer_id, is_current) WHERE is_current = TRUE;
  - This forces: only one is_current=TRUE per customer_id

Step 6: Document incident
  - Root cause: [explanation]
  - Impact: [how many facts affected]
  - Prevention: [what changed to prevent recurrence]
```

### Issue 6: Pipeline Hung (IN_PROGRESS status for > 2 hours)

**Symptoms**:
- control.ctl_batch.status = 'IN_PROGRESS'
- batch_end_ts_utc is NULL
- Started 2+ hours ago, no updates to audit logs

**Root Cause Analysis**:

```sql
-- Step 1: Get batch info
SELECT dw_batch_id, batch_start_ts_utc, batch_end_ts_utc, run_type
FROM control.ctl_batch
WHERE dw_batch_id = <current_batch_id>;

-- Step 2: Check last audit event
SELECT event_type, logged_ts, message
FROM control.audit_run_log
WHERE dw_batch_id = <current_batch_id>
ORDER BY logged_ts DESC
LIMIT 1;

-- Step 3: Check for locks (if PostgreSQL)
SELECT * FROM pg_stat_activity 
WHERE state = 'active' 
AND query LIKE '%bronze%' OR query LIKE '%silver%' OR query LIKE '%gold%';

-- Step 4: Check for failed extraction
SELECT source_table, extract_status, extract_end_ts
FROM control.audit_source_extract
WHERE dw_batch_id = <current_batch_id>
ORDER BY extract_end_ts DESC;
```

**Common Causes**:

| Cause | Indicator | Resolution |
|-------|-----------|-----------|
| Long-running extraction locked | pg_stat_activity shows query from 2h ago, state='active' | Kill query: SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE ... |
| Dimension merge hang (deadlock) | Last log: "Loading dimensions", then nothing | Rollback transaction, investigate dependency order |
| Disk full (I/O hanging) | os.df shows target filesystem at 100% | Free space: archive old control records, delete old batches |
| Network timeout (no reconnect) | Python process still running but no DB queries | Restart pipeline process, re-run with same batch_id |

**Resolution Procedure**:

```
Step 1: Stop hung process
  - Get process ID: ps aux | grep "run.*pipeline"
  - Kill process: kill -9 <pid>
  - Verify stopped: ps aux | grep "run.*pipeline" should be empty

Step 2: Investigate and fix root cause
  - If lock: kill blocking query
  - If disk full: free space, then retry
  - If network: restart connection pool

Step 3: Reset batch status
  - DO NOT advance watermarks
  - UPDATE control.ctl_batch SET status='IN_PROGRESS', batch_end_ts_utc=NULL WHERE dw_batch_id = <batch_id>
  - Optionally ROLLBACK any partial writes: DELETE FROM bronze WHERE dw_batch_id = <batch_id>, DELETE FROM silver WHERE dw_batch_id = <batch_id>, etc.

Step 4: Replay batch
  - python run_ingestion_pipeline.py --run_type REPLAY --batch_id <batch_id>
  - Monitor closely for same hang

Step 5: Escalate if repeats
  - If hangs again: infrastructure issue (disk, network, DB performance)
  - Escalate to: DBA, infrastructure team
  - Do not attempt third retry (may compound issue)
```

## Part 3: Data Quality and Performance Tuning

### Understanding the DQ Scorecard (mart_dq_scorecard)

**Columns and Interpretation**:

```
Cohort Mix:
- cohort_a_count: rows in COHORT_A (early data, 12.9%, ~7,950 rows)
- cohort_b_count: rows in COHORT_B (late data, 87.1%, ~53,827 rows)
- Baseline: should be stable day-to-day
- Alert: if cohort_a grows or cohort_b shrinks >1% (data replay?)

Restaurant Concentration:
- restaurant_concentration_percent: % of orders from top restaurant
- Baseline: 87.1% (restaurant_id 214, synthetic/test data)
- Alert: if < 85% (lost synthetic orders?) or > 89% (data duplication?)
- Action: filter this outlier from mart_order_daily for business reporting

Quarantine Rates:
- <entity>_quarantine_count: rows failed DQ rules
- By severity: BLOCK (fail), QUARANTINE (flag), WARN (count)
- Baseline: <1% quarantine (mostly late-arriving dimensions)
- Alert: if > 5% quarantine (investigate which rule)

Reconciliation:
- rc_1_pass, rc_2_pass, rc_3_pass: reconciliation check results
- Baseline: all TRUE (100% pass rate)
- Alert: if any FALSE (data loss or grain mismatch)

Freshness:
- max_business_date: latest order date in dataset
- Expected: >= run_date - 1 (yesterday's data available)
- Alert: if < run_date - 2 (data is 2+ days old)

Performance:
- pipeline_duration_seconds: total time for batch
- baseline: 30-45 minutes = 1800-2700 seconds
- Alert: if > 60 minutes (performance degradation) or < 15 minutes (extraction too fast?)
- Track: trend over time (should be stable)
```

**Example Query to Monitor Trends**:

```sql
SELECT 
  created_ts::DATE as run_date,
  cohort_a_count,
  cohort_b_count,
  ROUND(restaurant_concentration_percent, 1) as restaurant_conc_pct,
  total_quarantine_count,
  ROUND(100.0 * total_quarantine_count / (cohort_a_count + cohort_b_count), 2) as quarantine_pct,
  pipeline_duration_seconds / 60.0 as duration_minutes,
  rc_1_pass AND rc_2_pass AND rc_3_pass as all_reconciliation_passed
FROM gold.mart_dq_scorecard
ORDER BY created_ts DESC
LIMIT 30;
```

**Performance Tuning Recommendations**:

```
If pipeline_duration_seconds > 60 minutes (degrading):
  1. Check: do extractions run in parallel or sequentially?
     - Parallel: extract all 18 tables at once (Group A, B, C) → faster
     - Sequential: extract tables one-by-one → slower
  2. Check: any extraction timeout (5+ minutes for single table)?
     - If yes: check source DB performance, add index to watermark column
  3. Check: Silver/Gold transformation time
     - Rebuild dimensions: should be < 5 minutes
     - Rebuild facts: should be < 10 minutes
     - If > 20 minutes: check for inefficient joins, add indexes

If quarantine_count spiking:
  1. Check: which rule is firing?
  2. Determine: is rule working correctly or too loose?
  3. Action: tighten rule or accept as baseline

If restaurant_concentration_percent changing:
  1. Alert: may indicate data issue (duplicate orders? synthetic outlier changed?)
  2. Check: source DB for data changes
  3. Investigate: did extraction predicate change?
```

# Technical Knowledge Base

## Frequently Asked Questions (FAQ)

**Q1: How do I query the Gold layer for BI dashboards?**

A1: Use the dimensional model:
```sql
SELECT 
  o.order_id,
  dc.customer_id, dc.first_name, dc.last_name,  -- Customer dimension
  dr.restaurant_id, dr.restaurant_name,          -- Restaurant dimension
  DO.order_status_conformed,                     -- Order status (conformed)
  o.order_date,
  o.total_price, o.tax_amount,
  COUNT(DISTINCT oi.order_item_id) as line_item_count
FROM gold.fact_order o
JOIN gold.dim_customer dc ON o.customer_sk = dc.customer_sk
  AND o.order_date BETWEEN dc.valid_from_utc AND COALESCE(dc.valid_to_utc, '9999-12-31')
JOIN gold.dim_restaurant dr ON o.restaurant_sk = dr.restaurant_sk
  AND o.order_date BETWEEN dr.valid_from_utc AND COALESCE(dr.valid_to_utc, '9999-12-31')
LEFT JOIN gold.fact_order_item oi ON o.order_id = oi.order_id
WHERE o.order_date >= CURRENT_DATE - 30
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
ORDER BY o.order_date DESC;
```

**Q2: How do I interpret a dq_flag_*=TRUE column?**

A2: Data quality flags indicate data quality concerns (not necessarily errors):
- `dq_flag_cancel_mismatch=TRUE`: order.is_cancelled contradicts order.order_status (6,794 rows, 11%)
- `dq_flag_pending_but_paid=TRUE`: order status=PENDING yet payment_status=TRUE (7,019 rows, 11%)
- `dq_flag_payment_retry=TRUE`: order had multiple payment attempts, we collapsed them (2,944 orders)
- `dq_flag_dim_fallback=TRUE`: fact couldn't find dimension version at event_date, used earliest version
Action: Include flag in WHERE clause to filter if needed, or accept as data variance

**Q3: What's the difference between COHORT_A and COHORT_B?**

A3:
| Attribute | COHORT_A | COHORT_B |
|-----------|----------|----------|
| Order ID Range | <= 10,928 | > 10,928 |
| Date Range | Apr 15 - May 16, 2025 | Jun 3, 2024 - Jun 4, 2025 |
| Volume | 7,950 orders (12.9%) | 53,827 orders (87.1%) |
| Order Line Detail | 100% have order_items | 0% have order_items |
| Status Vocabulary | Human (Pending, Completed, Cancelled) | Machine (various codes) |
| Use Case | Development/testing? | Production data |
Action: Always filter by cohort when reporting; results will differ

**Q4: How do I investigate a quarantine row?**

A4:
```sql
-- Find quarantine records for a specific rule
SELECT * FROM silver.slv_order_quarantine
WHERE dq_rule_id = <rule_id> AND dw_batch_id = <batch_id>
LIMIT 5;

-- Understand the issue
SELECT dq_reason FROM silver.slv_order_quarantine
WHERE dq_rule_id = <rule_id>
GROUP BY dq_reason;

-- Fix and replay
-- Option A: Fix source data, re-run extraction
-- Option B: Update dq_rule_definition (change BLOCK to QUARANTINE), re-run evaluation
-- Option C: Accept quarantine as normal (e.g., pending_but_paid is expected for 11%)
```

**Q5: How do I know if a dimension is slowly changing?**

A5:
```sql
-- Count versions per business key (should be 1 for SCD1, >1 for SCD2)
SELECT COUNT(*) as version_count, COUNT(DISTINCT business_key) as unique_keys
FROM gold.dim_customer;
-- Example: 1,000 unique customers, 1,050 versions = some customers changed

-- See which attributes changed
SELECT customer_id, valid_from_utc, dw_version_no, first_name, last_name, email
FROM gold.dim_customer
WHERE customer_id = <specific_customer_id>
ORDER BY dw_version_no;
```

**Q6: How do I fix a wrong reconciliation check failure?**

A6:
```sql
-- Example: RC-2 failed, Bronze count ≠ Silver count
-- Step 1: Get expected vs actual
SELECT (SELECT COUNT(*) FROM bronze.br_orders) as bronze_count,
       (SELECT COUNT(*) FROM silver.slv_order) as silver_count,
       (SELECT COUNT(*) FROM silver.slv_order_quarantine) as quarantine_count;

-- Step 2: Find missing rows
SELECT order_id FROM bronze.br_orders
WHERE dw_batch_id = <batch_id>
EXCEPT
SELECT order_id FROM silver.slv_order WHERE dw_batch_id = <batch_id>
UNION ALL
SELECT order_id FROM silver.slv_order_quarantine WHERE dw_batch_id = <batch_id>;

-- Step 3: Determine why missing
-- - If in quarantine: expected (dq rule failed it)
-- - If not found: transformation didn't process it (check transformation logs)

-- Step 4: If transformation issue, replay
DELETE FROM silver.slv_order WHERE dw_batch_id = <batch_id>;
-- Re-run transformation for this batch
```

## Operational Playbooks

### Playbook 1: Emergency Data Fix (Source Data Issue Found)

**Scenario**: Analyst discovers 100 orders in Gold have wrong customer_id (data entry error in source)

**Steps**:

```
1. Confirm the issue:
   SELECT * FROM gold.fact_order WHERE order_id IN (<list>) AND customer_sk != -1
   
2. Notify stakeholders:
   Email: "100 orders have bad customer mapping, investigating root cause and fix ETA"
   
3. Investigate source:
   Query source DB: SELECT * FROM app.orders WHERE order_id IN (<list>)
   Confirm: customer_id is wrong in source (or correct there, issue in our pipeline?)
   
4. If source is wrong:
   Work with source owner: remediate orders in source
   Wait for source to confirm fix
   
5. If our pipeline is wrong:
   Investigate Bronze: SELECT * FROM bronze.br_orders WHERE order_id IN (<list>)
   Check: is Bronze value correct (matches source) or wrong?
   If Bronze correct: issue is in Silver/Gold transformation (likely JOIN failed)
   If Bronze wrong: issue is in extraction (incorrect transformation of source column)
   
6. Fix and replay:
   Determine minimal batch to replay (just affected orders, or full day?)
   Option A (Minimal replay):
     DELETE FROM silver.slv_order WHERE order_id IN (<list>);
     DELETE FROM gold.fact_order WHERE order_id IN (<list>);
     Re-run transformation just for these orders (manual query)
   
   Option B (Full batch replay):
     Identify which batch loaded these orders (check dw_batch_id)
     Replay entire batch: python run_ingestion_pipeline.py --run_type REPLAY --batch_id <batch_id>
   
7. Verify fix:
   SELECT * FROM gold.fact_order WHERE order_id IN (<list>)
   Confirm: customer_sk now correct (not -1), customer details proper
   
8. Notify stakeholders:
   "Issue resolved, affected 100 orders, re-calculated correctly, Gold layer updated"
   BI users refresh dashboards
   
9. Root cause analysis:
   Document: how did issue happen? How to prevent?
   Update: data quality rules if applicable
   Update: source schema analysis if column interpretation wrong
```

### Playbook 2: Dimension Key Missing (Late-Arriving Dimension)

**Scenario**: Gold fact_order has 5% customer_sk=-1 (dimension key missing), when expected <1%

**Steps**:

```
1. Assess scope:
   SELECT COUNT(*) as affected_count, 
          ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM gold.fact_order), 2) as pct
   FROM gold.fact_order
   WHERE customer_sk = -1;
   
2. Identify late-arriving customers:
   SELECT DISTINCT o.customer_id
   FROM gold.fact_order o
   LEFT JOIN gold.dim_customer d ON o.customer_id = d.customer_id
   WHERE o.customer_sk = -1 AND o.dw_batch_id = <batch_id>
   LIMIT 10;
   
3. Check if customers exist in Silver:
   SELECT customer_id, COUNT(*) as customer_count
   FROM silver.slv_customer
   WHERE customer_id IN (<list from step 2>)
   GROUP BY customer_id;
   
4. If customers exist in Silver but not Gold dimension:
   This is expected: customers created after first order (late-arriving)
   Gold dimension will be enriched on next batch load
   Action: Document in scorecard "5 customers created after first order"
   
5. If customers don't exist anywhere:
   This is a problem: order references customer that doesn't exist
   Action: Flag as data quality issue, investigate source
   
6. Monitor resolution:
   Run next day's batch
   Query: SELECT COUNT(*) FROM gold.fact_order WHERE customer_sk = -1 AND dw_batch_id = <next_batch_id>
   Should decrease as dimension load enriches inferred members
   
7. If not resolved after 2 batches:
   Escalate: investigate why dimension extraction failed
```

### Playbook 3: Partition/Index Maintenance (Monthly)

**Schedule**: First Sunday of each month, 2 AM UTC

**Steps**:

```
1. Analyze table bloat:
   SELECT 
     schemaname, tablename, 
     pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
     round(100 * (pg_total_relation_size(schemaname||'.'||tablename) - 
                  pg_relation_size(schemaname||'.'||tablename)) / 
           pg_total_relation_size(schemaname||'.'||tablename)) as external_ratio
   FROM pg_tables
   WHERE schemaname IN ('bronze', 'silver', 'gold')
   ORDER BY pg_total_relation_size DESC;
   
2. VACUUM and ANALYZE (reclaim space, update statistics):
   VACUUM ANALYZE bronze.br_orders;
   VACUUM ANALYZE silver.slv_order;
   VACUUM ANALYZE gold.fact_order;
   -- Repeat for other large tables
   
3. Rebuild indexes if needed:
   SELECT schemaname, tablename, indexname
   FROM pg_indexes
   WHERE schemaname IN ('bronze', 'silver', 'gold')
   ORDER BY tablename;
   REINDEX INDEX idx_bronze_batch;  -- if index is bloated
   
4. Check for missing indexes:
   If query performance degraded, add index on frequently queried columns:
   CREATE INDEX idx_fact_order_customer_sk ON gold.fact_order (customer_sk);
   
5. Archive old control records (>1 year):
   DELETE FROM control.audit_run_log 
   WHERE logged_ts < CURRENT_TIMESTAMP - INTERVAL '1 year';
   DELETE FROM control.ctl_batch
   WHERE batch_end_ts_utc < CURRENT_TIMESTAMP - INTERVAL '1 year';
   
6. Verify:
   REINDEX DATABASE <target_db>;
   -- Confirm: no errors
   
7. Document:
   Record in maintenance log: date, tables vacuumed, space reclaimed
```

# Handoff Documentation

## Runbook for Operations Team

**Essential Knowledge**:
1. Three-skill architecture: foundations → ingestion → transformation
2. Daily run: 6 AM UTC, 30-45 minute execution window
3. On failure: check logs, replay if transient, escalate if persistent
4. On data issue: check quarantine, check reconciliation, investigate root cause
5. On performance: check DQ scorecard trends, identify slow table

**Contact List**:
- On-call Data Engineer: [name] +[phone]
- Database Admin: [name] +[phone]
- Business Analyst (data owner): [name] +[email]
- Data Protection Officer: [name] +[email] (for PII/compliance issues)

**Key Metrics to Monitor**:
- pipeline_duration_seconds: should be 1800-2700 (30-45 min)
- quarantine_pct: should be <1-2%
- restaurant_concentration_pct: should be ~87% (stable)
- max_business_date: should be >= run_date - 1

## Knowledge Base Articles for Training

**Article 1: Medallion Architecture 101**
- Bronze: raw data, never modified, append-only
- Silver: conformed data, business rules applied, deduplicated
- Gold: dimensional model, ready for BI
- Why three layers? Separate concerns, enable replay, support audit trail

**Article 2: How to Query Gold Layer for Dashboard**
- Use dimensional joins with as-at logic
- Always use valid_from_utc and valid_to_utc to get correct version at event_date
- Filter by cohort when needed (different data vocab for COHORT_A vs B)
- Aggregate in marts (mart_order_daily, mart_revenue_daily) for dashboard performance

**Article 3: Understanding Data Quality Flags**
- Not errors, but quality concerns worth knowing about
- Examples: pending_but_paid, cancel_mismatch, dim_fallback
- Where to find: Silver entity tables have dq_flag_* columns
- Action: Usually filter or document in dashboard

**Article 4: SCD2 Dimension Queries**
- To see history: SELECT * FROM gold.dim_customer WHERE customer_id = X ORDER BY dw_version_no
- To see current: SELECT * FROM gold.dim_customer WHERE customer_id = X AND is_current = TRUE
- To see when changed: SELECT dw_version_no, valid_from_utc, valid_to_utc FROM dim_customer
- To join fact: fact.event_date BETWEEN dim.valid_from_utc AND COALESCE(dim.valid_to_utc, '9999-12-31')

**Article 5: How to Investigate Failed Batch**
1. Query: control.ctl_batch - what was status?
2. Query: control.audit_run_log - what error occurred?
3. Query: control.audit_source_extract - which table extraction failed?
4. Query: control.ctl_reconciliation - which reconciliation check failed?
5. Determine: transient (network, timeout) or persistent (schema, logic)?
6. Action: replay if transient, escalate if persistent

# Validation Checklist

Before handing over to operations team:

- ✅ Operations team trained on daily checklist
- ✅ Troubleshooting guide reviewed (everyone knows how to investigate)
- ✅ Contact list updated with on-call names and numbers
- ✅ Monitoring dashboards configured (pipeline duration, quarantine rate, freshness)
- ✅ Alerting configured (on batch FAILED, on quarantine >5%, on duration >60 min)
- ✅ Backup procedures documented (how to restore from backup)
- ✅ Disaster recovery tested (replay old batch, rebuild dimension, etc.)
- ✅ Knowledge base published (FAQ, articles, training materials)
- ✅ Runbook printed or accessible offline
- ✅ Questions answered and concerns addressed

# Final Response Format

When consulting this skill for operational guidance, report:

## Issue Description
- What went wrong?
- When did it happen?
- What was the impact?

## Investigation Steps Taken
- Which logs queried?
- What was root cause?
- Is it transient or persistent?

## Resolution Applied
- What action taken?
- How verified fix?
- Any residual issues?

## Preventive Measures
- How to prevent recurrence?
- Any rule/config/code changes needed?
- Monitoring added?

## Knowledge Captured
- What did we learn?
- Document for future reference?
- Update runbook/FAQ?

---

## Appendix: Common Queries for Operations

**Check daily health**:
```sql
SELECT 
  (SELECT COUNT(*) FROM control.ctl_batch WHERE batch_end_ts_utc > CURRENT_TIMESTAMP - 24 HOURS AND status='COMPLETED') as successful_batches,
  (SELECT COUNT(*) FROM control.ctl_batch WHERE batch_end_ts_utc > CURRENT_TIMESTAMP - 24 HOURS AND status='FAILED') as failed_batches,
  (SELECT COALESCE(MAX(batch_end_ts_utc), 'N/A'::TEXT) FROM control.ctl_batch WHERE status='COMPLETED') as last_completed_run,
  (SELECT COUNT(*) FROM silver.slv_order_quarantine WHERE dw_batch_id = (SELECT MAX(dw_batch_id) FROM control.ctl_batch WHERE status='COMPLETED')) as today_quarantine_count;
```

**Check Gold layer row counts**:
```sql
SELECT 
  'fact_order' as table_name, COUNT(*) as rows FROM gold.fact_order WHERE dw_batch_id = (SELECT MAX(dw_batch_id) FROM control.ctl_batch WHERE status='COMPLETED')
UNION ALL
SELECT 'fact_payment', COUNT(*) FROM gold.fact_payment WHERE dw_batch_id = (SELECT MAX(dw_batch_id) FROM control.ctl_batch WHERE status='COMPLETED')
UNION ALL
SELECT 'dim_customer', COUNT(*) FROM gold.dim_customer WHERE is_current = TRUE
UNION ALL
SELECT 'mart_dq_scorecard', COUNT(*) FROM gold.mart_dq_scorecard WHERE created_ts > CURRENT_TIMESTAMP - 24 HOURS;
```

**Check data freshness**:
```sql
SELECT 
  MAX(order_date) as max_order_date,
  MAX(order_date)::DATE as max_order_date_key,
  CURRENT_DATE as today,
  CURRENT_DATE - MAX(order_date)::DATE as days_lag
FROM gold.fact_order;
```
