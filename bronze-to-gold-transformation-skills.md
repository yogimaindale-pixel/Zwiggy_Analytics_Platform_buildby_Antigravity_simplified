---
name: bronze-to-gold-transformation
description: Transforms cleansed Silver entities and builds the dimensional Gold layer with 14 SCD2 dimensions, 6 fact tables, aggregates, and complete data quality framework with 40+ rules, quarantine, reconciliation, and scorecard. Implements business logic exactly once per BR-R1 through BR-R11.
---

# Purpose

This skill implements the complete Silver and Gold layer transformation pipeline. It cleanses and conforms Bronze data into typed, deduplicated Silver entities; applies 40+ data quality rules with quarantine framework; builds a dimensional model with 14 SCD2 dimensions and 6 fact tables supporting as-at analysis; creates aggregate marts for dashboard performance; and produces a daily scorecard measuring data quality, freshness, and lineage.

This skill executes **after source-to-bronze-ingestion** and **before BI/dashboard consumption**.

# When to Use This Skill

- **Daily transformation runs**: After source-to-bronze-ingestion completes successfully
- **Backfill operations**: Rebuilding Silver/Gold for historical date ranges
- **Dimension corrections**: Re-loading dimensions after source data remediation
- **SCD2 history building**: Creating full change history from go-live
- **Data quality remediation**: Quarantine processing and rule re-evaluation
- **Aggregate rebuild**: Refreshing dimensional aggregates after fact updates

# When Not to Use This Skill

- Do not use this for initial schema creation (dwh-metadata-and-foundations handles that)
- Do not use this for source data extraction (source-to-bronze-ingestion handles that)
- Do not use this for BI tool configuration or dashboard creation
- Do not use this for PII masking in BI layers (handle in semantic layer)
- Do not use this for generating BI reports (BI developer responsibility)

# Project Context

**Architecture**: Medallion Bronze → Silver → Gold  
**Data Quality Framework**: 40+ rules, quarantine, reconciliation, published scorecard (KPI-33 through KPI-42)  
**Dimensional Model**:
- 14 dimensions (SCD2): customer, address, restaurant, menu_item, delivery_partner, cuisine, restaurant_owner, order_status, payment_method, order_flag, restaurant_cuisine, cuisine_mapping, delivery_carrier, review_sentiment
- 6 fact tables: order, order_item, payment_attempt, payment, delivery, review
- 2 deferred fact/bridge tables: payment (collected), order_fulfilment (accumulating)
- 2 aggregate marts: order_daily, revenue_daily

**Business Rules** (BR-R1 through BR-R11) enforced in Silver/Gold:
- BR-R1: All history from go-live, no pre-go-live data misrepresented
- BR-R2: Cohort tagging (COHORT_A ≤ 10928 vs COHORT_B > 10928)
- BR-R3: Pending-but-paid orders flagged (7,019 rows)
- BR-R4: Tax is always 0.00, expose revenue_is_gross_inclusive = true
- BR-R5: Payment retry collapse (2,944 orders with retries)
- BR-R6: Delivery deduplication (564 orders with duplicates)
- BR-R7: Cancellation flag resolution (6,794 contradictory orders)
- BR-R8: Status vocabulary conformance
- BR-R9: As-at dimension resolution (fact joins to dimension version valid at event_ts)
- BR-R10: Reconciliation mandatory (RC-1 through RC-10)
- BR-R11: Restaurant concentration measurement (87.1% outlier)

**Data Quality Challenges**:
- Two incompatible cohorts with different vocabularies
- 11% orders with contradictory status flags
- 13,133 orders missing payment records (4%)
- 4,239 orders missing delivery records (1.2%)
- Price changes over time (menu_item is SCD2)
- One restaurant (id 214) is synthetic outlier (87% of orders)

# Required Files to Read

Before executing this skill, Antigravity must review:

1. **Complete BRD Part B Document**
   - `BRD-B-DWH-Medallion-Project-v0.1.pdf` - complete mandatory reference
   - §1: Scope and objectives
   - §2: Architecture and layer contracts
   - §5: Bronze layer specification
   - §6: Silver layer specification (S-1 through S-43)
   - §7: Gold layer specification (dimensions G-01 through G-35, facts G-30 through G-36)
   - §8: Source-to-target mapping
   - §9: Data quality framework (40+ rules)
   - §10: Orchestration (control tables, dependencies)
   - §12: Non-functional requirements
   - §14: Engineering standards

2. **BRD Part A - Business Context**
   - `BRD-A-BI-and-Analytics-v0.1.pdf` - sections 1-4
   - §1: Executive summary, source system facts, findings
   - §4: KPIs and reporting requirements (KPI-33 through KPI-42 are DQ metrics)

3. **Functional Requirements Document**
   - `Functional Requirements.docx` - Source-to-Bronze patterns inform Silver logic

4. **Source Schema Details**
   - `Source Schema Details.xlsx` - All 18 source tables and 177 columns

5. **Output from Previous Skills**
   - Bronze data in all 18 br_* tables
   - control.ctl_table_config with all 18 table strategies
   - control.ctl_watermark with current watermarks
   - silver.ref_status_map with conformance mappings
   - silver.ref_cohort_rule with boundary configuration
   - silver.ref_dq_rule_definition with 40+ rules

# Preconditions

Before this skill can execute, verify:

1. **source-to-bronze-ingestion Skill Must Complete**
   - All 18 bronze.br_* tables populated with data
   - control.ctl_batch shows status=COMPLETED for latest run
   - control.ctl_watermark has entries for all 18 tables
   - control.audit_source_extract has manifest for each table
   - All reconciliation checks passed (RC-1)

2. **Silver Schema Ready**
   - silver schema exists and is empty
   - silver_quarantine schema exists and is empty
   - All reference tables exist: ref_status_map, ref_cohort_rule, ref_dq_rule_definition
   - DDL for slv_* tables exists (created by foundations skill)

3. **Gold Schema Ready**
   - gold schema exists and is empty
   - DDL for all 14 dimensions exists (SCD2 structure)
   - DDL for all 6 fact tables exists
   - DDL for 2 deferred tables exists
   - DDL for 2 aggregate marts exists

4. **Configuration Ready**
   - All reference data populated:
     - silver.ref_status_map covers all source status values
     - silver.ref_cohort_rule has COHORT_A and COHORT_B
     - silver.ref_dq_rule_definition has all 40+ rules
   - Business rules (BR-R1 through BR-R11) understood and configured
   - SCD2 change detection hash algorithm specified (MD5 or SHA256)

5. **Data Quality Framework Ready**
   - control.ctl_dq_rule has all rules defined
   - Severity levels assigned: BLOCK, QUARANTINE, WARN, RECONCILE
   - Target tables identified for each rule
   - SQL predicates for each rule available

6. **Python Environment**
   - pandas for data manipulation
   - sqlalchemy for ORM (optional)
   - hashlib for row hashing (MD5, SHA256)
   - datetime, json, logging modules

# Responsibilities

This skill is exclusively responsible for:

1. **Silver Layer Construction**
   - Read Bronze data, cleanse and conform
   - Implement all business rules BR-R1 through BR-R11
   - Apply conformance mappings: order status, payment status, tender
   - Resolve contradictions: cancelled vs cancellation_flag, pending vs paid
   - Tag cohorts: COHORT_A (order_id <= 10928) vs COHORT_B
   - Deduplicate as-per business keys
   - Add data quality flags: dq_flag_cancel_mismatch, dq_flag_pending_but_paid, etc.
   - Populate:
     - 11 Silver entity tables (slv_order, slv_customer, etc.)
     - 2 Silver derived tables (slv_payment_attempt, slv_payment collapsed)
     - Reference tables (already populated by foundations)

2. **Data Quality Rule Evaluation**
   - For each of 40+ DQ rules:
     - Evaluate SQL predicate against Silver data
     - Classify rows: PASS, QUARANTINE, WARN, BLOCK
     - Write BLOCK/QUARANTINE rows to quarantine tables
     - Count affected rows
     - Record results in control.ctl_dq_rule

3. **Quarantine Management**
   - Create slv_<entity>_quarantine tables (mirrors Silver structure plus metadata)
   - Write failed rows with:
     - Original values
     - dq_rule_id (which rule failed)
     - dq_reason (why it failed)
     - dq_detected_ts_utc (when detected)
     - dw_batch_id (which batch)
     - Full raw payload for debugging
   - Enable replay: fixing rule or reference data + re-run brings row into Silver

4. **Dimensional Modeling (Gold)**
   - Build 14 SCD2 dimensions:
     - dim_customer, dim_address, dim_restaurant, dim_menu_item, dim_delivery_partner, dim_cuisine, dim_restaurant_owner, dim_order_status, dim_payment_method, dim_order_flag, dim_restaurant_cuisine
     - For each: apply SCD2 merge logic on business key
     - Change detection: dw_row_hash (MD5 of non-key attributes)
     - Validity intervals: [valid_from_utc, valid_to_utc), half-open, gapless per BK
     - Track versions: dw_version_no, is_current, dw_initial_load
     - Handle late-arriving dimensions: create inferred members
     - Degenerate dimensions: store BK on fact, no dimension table

5. **Fact Table Population (Gold)**
   - Build 6 fact tables:
     - fact_order (one row per order transaction)
     - fact_order_item (one row per order line item)
     - fact_payment_attempt (one row per payment attempt, including retries)
     - fact_payment (one row per collected payment per order, after retry collapse)
     - fact_delivery (one row per delivery transaction)
     - fact_review (one row per review)
   - For each fact:
     - Establish grain explicitly
     - Join to dimensions using as-at resolution (fact_event_ts falls within [valid_from, valid_to))
     - Populate surrogate keys from dimensions
     - Handle dimension key mismatches: use -1 and flag dq_flag_dim_fallback
     - Include degenerate dimensions: order_id, payment_id, delivery_id, review_id
     - Apply measure calculations (amounts, quantities)
     - Tag cohort: dw_source_cohort

6. **Accumulating Snapshot**
   - Build fact_order_fulfilment (accumulating snapshot):
     - One row per order_id
     - Milestone columns: payment_date_key, delivery_date_key, review_date_key
     - Updated in place as payment and delivery facts arrive
     - Initialize with order dates, update when events occur

7. **Aggregate Marts (Gold)**
   - Build mart_order_daily:
     - Grain: (order_date_key, restaurant_id, order_status)
     - Metrics: count, sum(total_price), sum(tax_amount)
     - Filters: active restaurants only, exclude synthetic outlier (restaurant_id != 214 or documented)
   - Build mart_revenue_daily:
     - Grain: (payment_date_key)
     - Metrics: count, sum(payment_amount), sum(refunds)
     - By payment method, by cohort

8. **Data Quality Scorecard**
   - Create mart_dq_scorecard:
     - Run-level metrics per DQ-R1 through DQ-R24
     - Rows affected per rule
     - Quarantine counts per entity table
     - Reconciliation results (RC-1 through RC-10)
     - Cohort mix (COHORT_A vs COHORT_B row counts)
     - Restaurant concentration (87.1% outlier measure, KPI-41)
     - Run duration vs SLA
     - Freshness: max business date >= run date - 1
   - Publish as fact_dq_scorecard one row per run

9. **Reconciliation Checks** (Mandatory Every Run)
   - RC-1: Extract → Bronze (already validated in source-to-bronze skill)
   - RC-2: Bronze → Silver (Bronze rows = Silver loaded + quarantined + explicitly rejected)
   - RC-3: Silver → Gold (fact rows = Silver rows - grain changes, dimension rows within bounds)
   - RC-4 through RC-10: Feature-specific validations per §9.4 BRD-B
   - Record results in control.ctl_reconciliation

10. **Idempotent Transformation**
    - Identify affected business-date range
    - Silver rebuild: MERGE on business key (or partition overwrite)
    - Gold dimensions: SCD2 merge (idempotent: same snapshot in same batch = no new version)
    - Gold facts: merge on (business_key, cohort) or partition overwrite
    - Re-running same batch must not create duplicates

11. **Change Detection for SCD2**
    - For each dimension record:
      - Hash all non-key attributes: MD5 or SHA256
      - Compare current hash vs previous version hash
      - If unchanged: mark as_current=TRUE, do NOT touch valid_to or version_no
      - If changed: EXPIRE current (valid_to = run_cutoff, is_current = FALSE), INSERT new version
      - If key absent in current snapshot: mark dw_is_deleted = TRUE

12. **As-At Dimension Resolution**
    - When joining fact to dimension:
      - Get fact.event_timestamp
      - Find dimension row where business_key matches AND [valid_from, valid_to) contains event_timestamp
      - Join using surrogate key
      - If no version covers event_ts: use earliest version, set dq_flag_dim_fallback
      - If key absent: use _sk = -1, count as dimension quality issue

13. **Late-Arriving Dimension Handling**
    - If fact arrives before dimension member exists:
      - Create inferred dimension member (business key only, all attributes UNKNOWN)
      - Set dw_is_inferred = TRUE
      - Later dimension load enriches this member
      - Track inferred members count as data quality metric

14. **PII and Sensitive Data**
    - Mask in Silver/Gold: customer phone, email, first_name, last_name
    - Method: replace with '***MASKED***' or hash
    - Track which customers have masked PII (for data protection officer)
    - Do NOT mask: customer_id (surrogate key), cohort tag, order amounts

15. **Documentation Generation**
    - Silver entity definitions: one per slv_* table
    - Gold dimension specifications: business key, change drivers, SCD2 strategy
    - Gold fact specifications: grain, dimensions, measures, degenerate dims
    - Aggregate mart definitions: grain, filters, calculations
    - Data quality scorecard: metrics and thresholds
    - Dashboard data lineage: trace from source through Silver/Gold to BI tools

# Step-by-Step Execution Workflow

## Phase 1: Initialization

**1.1 Connect and Read Batch Context**

```python
def get_latest_batch_context(control_conn):
    """Read latest completed batch from control.ctl_batch"""
    cursor = control_conn.cursor()
    cursor.execute("""
        SELECT dw_batch_id, batch_start_ts_utc, run_cutoff_ts_utc, run_type
        FROM control.ctl_batch
        WHERE status = 'COMPLETED'
        ORDER BY dw_batch_id DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    if not row:
        raise ValueError("No completed batch found, run source-to-bronze-ingestion first")
    
    batch_id, batch_start, run_cutoff, run_type = row
    return {
        'batch_id': batch_id,
        'batch_start_ts_utc': batch_start,
        'run_cutoff_ts_utc': run_cutoff,
        'run_type': run_type
    }
```

**1.2 Load Reference Data**

```python
def load_conformance_mappings(control_conn):
    """Read status and payment method mappings from reference tables"""
    cursor = control_conn.cursor()
    
    # Status mappings
    cursor.execute("""
        SELECT source_status_value, conformed_status_value 
        FROM silver.ref_status_map
        WHERE is_valid = TRUE
    """)
    status_map = {row[0]: row[1] for row in cursor.fetchall()}
    
    # Cohort rules
    cursor.execute("""
        SELECT cohort_name, boundary_column, boundary_operator, boundary_value
        FROM silver.ref_cohort_rule
        WHERE is_active = TRUE
    """)
    cohort_rules = {row[0]: row for row in cursor.fetchall()}
    
    return status_map, cohort_rules
```

## Phase 2: Silver Layer Construction

**2.1 Cleanse Orders and Apply Business Rules**

```python
def transform_orders_to_silver(source_conn, target_conn, batch_id, run_cutoff, status_map):
    """
    BR-R2: Tag cohorts
    BR-R3: Flag pending-but-paid
    BR-R7: Resolve cancellation contradictions
    BR-R8: Status conformance
    """
    
    # Read Bronze orders
    source_cursor = source_conn.cursor()
    source_cursor.execute("""
        SELECT * FROM bronze.br_orders
        WHERE dw_batch_id = %s
        ORDER BY order_id
    """, (batch_id,))
    
    orders = []
    quarantined = []
    
    for row in source_cursor.fetchall():
        order = dict(zip([desc[0] for desc in source_cursor.description], row))
        
        # BR-R2: Assign cohort
        order['dw_source_cohort'] = 'COHORT_A' if order['order_id'] <= 10928 else 'COHORT_B'
        
        # BR-R7: Resolve cancellation contradictions
        dq_flag_cancel_mismatch = False
        if order['is_cancelled'] != (order['order_status'] == 'CANCELLED'):
            dq_flag_cancel_mismatch = True
            # Use status over flag (status is more reliable)
            order['is_cancelled'] = order['order_status'] == 'CANCELLED'
        
        order['dq_flag_cancel_mismatch'] = dq_flag_cancel_mismatch
        
        # BR-R3: Flag pending-but-paid orders
        conformed_status = status_map.get(order['order_status'], order['order_status'])
        order['dq_flag_pending_but_paid'] = (
            conformed_status == 'PENDING' and order['payment_status'] == True
        )
        
        # BR-R8: Status conformance
        order['order_status_conformed'] = conformed_status
        
        # Calculate row hash for SCD2
        hash_input = f"{order.get('customer_id')}{order.get('restaurant_id')}{order.get('total_price')}"
        order['dw_row_hash'] = hashlib.md5(hash_input.encode()).hexdigest()
        
        # Add technical columns
        order['dw_batch_id'] = batch_id
        order['dw_ingest_ts_utc'] = datetime.utcnow()
        
        # Determine if blocking
        is_blocking = dq_flag_cancel_mismatch and order['dw_source_cohort'] == 'COHORT_B'
        
        if is_blocking:
            quarantined.append(('orders', order, 'dq_flag_cancel_mismatch'))
        else:
            orders.append(order)
    
    # Load to Silver
    target_cursor = target_conn.cursor()
    
    # Delete existing for idempotency
    target_cursor.execute("""
        DELETE FROM silver.slv_order
        WHERE dw_batch_id = %s
    """, (batch_id,))
    
    # Insert cleaned orders
    for order in orders:
        cols = ', '.join(order.keys())
        vals = ', '.join(['%s'] * len(order))
        sql = f"INSERT INTO silver.slv_order ({cols}) VALUES ({vals})"
        target_cursor.execute(sql, tuple(order.values()))
    
    # Quarantine failed orders
    for entity, row, reason in quarantined:
        quarantine_row(target_cursor, entity, row, reason, batch_id)
    
    target_conn.commit()
    
    return len(orders), len(quarantined)
```

**2.2 Build Dimensions from Master Data**

```python
def transform_customers_to_silver_gold_dimension(source_conn, target_conn, batch_id, run_cutoff):
    """
    Transform customer records through Silver to Gold dimension (SCD2)
    """
    
    # Read Silver customers (after cleansing)
    cursor = source_conn.cursor()
    cursor.execute("""
        SELECT * FROM silver.slv_customer
        WHERE dw_batch_id = %s
    """, (batch_id,))
    
    current_customers = []
    for row in cursor.fetchall():
        cust = dict(zip([desc[0] for desc in cursor.description], row))
        cust['dw_row_hash'] = calculate_row_hash(cust, keys=['customer_id'])
        current_customers.append(cust)
    
    # Load to Gold dimension using SCD2 merge
    cursor = target_conn.cursor()
    
    for cust in current_customers:
        # Check for existing records
        cursor.execute("""
            SELECT customer_sk, dw_row_hash, is_current 
            FROM gold.dim_customer
            WHERE customer_id = %s AND is_current = TRUE
        """, (cust['customer_id'],))
        
        existing = cursor.fetchone()
        
        if existing:
            customer_sk, existing_hash, is_current = existing
            
            # Check for changes
            if cust['dw_row_hash'] != existing_hash:
                # Expire old version
                cursor.execute("""
                    UPDATE gold.dim_customer
                    SET is_current = FALSE, valid_to_utc = %s
                    WHERE customer_sk = %s
                """, (run_cutoff, customer_sk))
                
                # Insert new version
                cursor.execute("""
                    INSERT INTO gold.dim_customer (
                        customer_id, first_name, last_name, email, phone_number, is_active,
                        dw_version_no, dw_row_hash, is_current, valid_from_utc, valid_to_utc,
                        dw_initial_load, dw_batch_id
                    )
                    SELECT customer_id, first_name, last_name, email, phone_number, is_active,
                           dw_version_no + 1, %s, TRUE, %s, NULL, FALSE, %s
                    FROM gold.dim_customer
                    WHERE customer_sk = %s
                """, (cust['dw_row_hash'], run_cutoff, batch_id, customer_sk))
        else:
            # Initial insert
            cursor.execute("""
                INSERT INTO gold.dim_customer (
                    customer_id, first_name, last_name, email, phone_number, is_active,
                    dw_version_no, dw_row_hash, is_current, valid_from_utc, valid_to_utc,
                    dw_initial_load, dw_batch_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, 1, %s, TRUE, %s, NULL, TRUE, %s)
            """, (cust['customer_id'], cust['first_name'], cust['last_name'],
                  cust['email'], cust['phone_number'], cust['is_active'],
                  cust['dw_row_hash'], run_cutoff, batch_id))
    
    target_conn.commit()

def calculate_row_hash(row, keys):
    """Calculate MD5 hash of non-key attributes"""
    attrs = [str(v) for k, v in row.items() if k not in keys]
    return hashlib.md5(''.join(attrs).encode()).hexdigest()
```

**2.3 Handle Payment Retry Collapse (BR-R5)**

```python
def collapse_payment_retries_to_silver(source_conn, target_conn, batch_id):
    """
    BR-R5: Payment attempts → one collected payment per order
    Rank attempts: PAID desc, payment_date desc, payment_id desc
    Keep rank 1, set attempt_count and superseded_count
    """
    
    cursor = source_conn.cursor()
    
    # Read payment attempts from Bronze
    cursor.execute("""
        SELECT * FROM bronze.br_payments
        WHERE dw_batch_id = %s
        ORDER BY order_id, payment_date DESC, payment_id DESC
    """, (batch_id,))
    
    attempts_by_order = {}
    for row in cursor.fetchall():
        payment = dict(zip([desc[0] for desc in cursor.description], row))
        order_id = payment['order_id']
        if order_id not in attempts_by_order:
            attempts_by_order[order_id] = []
        attempts_by_order[order_id].append(payment)
    
    collected_payments = []
    
    for order_id, attempts in attempts_by_order.items():
        # Attempts already ordered by (payment_status DESC, payment_date DESC, payment_id DESC)
        collected_payment = attempts[0].copy()
        collected_payment['attempt_count'] = len(attempts)
        collected_payment['superseded_attempt_count'] = len(attempts) - 1
        collected_payment['dq_flag_payment_retry'] = len(attempts) > 1
        
        collected_payments.append(collected_payment)
    
    # Load to Silver
    target_cursor = target_conn.cursor()
    target_cursor.execute("""
        DELETE FROM silver.slv_payment
        WHERE dw_batch_id = %s
    """, (batch_id,))
    
    for payment in collected_payments:
        cols = ', '.join(payment.keys())
        vals = ', '.join(['%s'] * len(payment))
        sql = f"INSERT INTO silver.slv_payment ({cols}) VALUES ({vals})"
        target_cursor.execute(sql, tuple(payment.values()))
    
    target_conn.commit()
    
    return len(collected_payments)
```

**2.4 Handle Delivery Deduplication (BR-R6)**

```python
def deduplicate_deliveries_to_silver(source_conn, target_conn, batch_id):
    """
    BR-R6: Deliveries - keep latest terminal status
    Tie-break: latest delivery_time_utc, then highest delivery_id
    """
    
    cursor = source_conn.cursor()
    
    cursor.execute("""
        SELECT * FROM bronze.br_delivery_details
        WHERE dw_batch_id = %s
        ORDER BY order_id, 
                 CASE WHEN status IN ('DELIVERED', 'CANCELLED') THEN 0 ELSE 1 END,
                 delivery_time DESC,
                 delivery_id DESC
    """, (batch_id,))
    
    deliveries_by_order = {}
    for row in cursor.fetchall():
        delivery = dict(zip([desc[0] for desc in cursor.description], row))
        order_id = delivery['order_id']
        if order_id not in deliveries_by_order:
            deliveries_by_order[order_id] = delivery
    
    # Load to Silver
    target_cursor = target_conn.cursor()
    target_cursor.execute("""
        DELETE FROM silver.slv_delivery
        WHERE dw_batch_id = %s
    """, (batch_id,))
    
    for delivery in deliveries_by_order.values():
        cols = ', '.join(delivery.keys())
        vals = ', '.join(['%s'] * len(delivery))
        sql = f"INSERT INTO silver.slv_delivery ({cols}) VALUES ({vals})"
        target_cursor.execute(sql, tuple(delivery.values()))
    
    target_conn.commit()
    
    return len(deliveries_by_order)
```

## Phase 3: Gold Layer Facts with As-At Dimension Resolution

**3.1 Build fact_order with As-At Joins**

```python
def build_fact_order_with_as_at_joins(source_conn, target_conn, batch_id, run_cutoff):
    """
    G-30: As-at dimension resolution
    Fact grain: one row per order transaction
    Join to dimension version where fact_event_ts falls within [valid_from, valid_to)
    """
    
    cursor = source_conn.cursor()
    
    # Read orders from Silver
    cursor.execute("""
        SELECT * FROM silver.slv_order
        WHERE dw_batch_id = %s
    """, (batch_id,))
    
    orders = []
    for row in cursor.fetchall():
        orders.append(dict(zip([desc[0] for desc in cursor.description], row)))
    
    # Join to dimensions and create facts
    facts = []
    
    for order in orders:
        fact = {
            'order_id': order['order_id'],
            'order_date_key': int(order['order_date'].strftime('%Y%m%d')),
            'fact_event_ts_utc': order['order_date'],
            'dw_source_cohort': order['dw_source_cohort'],
            'dw_batch_id': batch_id
        }
        
        # As-at join to dim_customer
        customer_cursor = target_conn.cursor()
        customer_cursor.execute("""
            SELECT customer_sk FROM gold.dim_customer
            WHERE customer_id = %s
                AND valid_from_utc <= %s
                AND (valid_to_utc > %s OR valid_to_utc IS NULL)
            LIMIT 1
        """, (order['customer_id'], order['order_date'], order['order_date']))
        
        customer_result = customer_cursor.fetchone()
        if customer_result:
            fact['customer_sk'] = customer_result[0]
        else:
            fact['customer_sk'] = -1
            fact['dq_flag_dim_fallback'] = True
        
        # Similar for restaurant, address, etc.
        # ... (repeat pattern for each dimension)
        
        # Add measures
        fact['total_price'] = order['total_price']
        fact['tax_amount'] = order['tax_amount']
        
        facts.append(fact)
    
    # Load to Gold
    target_cursor = target_conn.cursor()
    target_cursor.execute("""
        DELETE FROM gold.fact_order
        WHERE dw_batch_id = %s
    """, (batch_id,))
    
    for fact in facts:
        cols = ', '.join(fact.keys())
        vals = ', '.join(['%s'] * len(fact))
        sql = f"INSERT INTO gold.fact_order ({cols}) VALUES ({vals})"
        target_cursor.execute(sql, tuple(fact.values()))
    
    target_conn.commit()
    
    return len(facts)
```

## Phase 4: Data Quality Evaluation and Quarantine

**4.1 Evaluate DQ Rules**

```python
def evaluate_dq_rules(control_conn, source_conn, batch_id):
    """
    Execute all 40+ DQ rules from silver.ref_dq_rule_definition
    Categorize: BLOCK, QUARANTINE, WARN, RECONCILE
    """
    
    # Read all active rules
    cursor = control_conn.cursor()
    cursor.execute("""
        SELECT dq_rule_id, rule_name, severity, target_table
        FROM silver.ref_dq_rule_definition
        WHERE is_active = TRUE
    """)
    
    rules = cursor.fetchall()
    dq_results = []
    
    for rule_id, rule_name, severity, target_table in rules:
        # Each rule has specific SQL (stored in rule definition)
        rule_sql = get_rule_sql(rule_id)  # Implementation TBD
        
        src_cursor = source_conn.cursor()
        src_cursor.execute(rule_sql, (batch_id,))
        
        affected_rows = src_cursor.fetchall()
        
        dq_results.append({
            'rule_id': rule_id,
            'rule_name': rule_name,
            'severity': severity,
            'affected_count': len(affected_rows),
            'passed': len(affected_rows) == 0,
            'rows': affected_rows
        })
    
    # Record results
    for result in dq_results:
        if not result['passed']:
            cursor.execute("""
                INSERT INTO control.ctl_dq_rule 
                (dq_rule_id, is_active)
                VALUES (%s, %s)
                ON CONFLICT (dq_rule_id) DO UPDATE
                SET is_active = %s
            """, (result['rule_id'], result['severity'] != 'BLOCK', result['severity'] != 'BLOCK'))
    
    control_conn.commit()
    
    return dq_results
```

**4.2 Write Quarantine Records**

```python
def quarantine_dq_failures(target_conn, entity_type, failed_rows, rule_id, batch_id):
    """
    Write failed rows to slv_<entity>_quarantine with metadata
    """
    
    quarantine_table = f"silver.slv_{entity_type}_quarantine"
    
    cursor = target_conn.cursor()
    
    for row in failed_rows:
        row_dict = row.copy() if isinstance(row, dict) else dict(row)
        row_dict['dq_rule_id'] = rule_id
        row_dict['dq_reason'] = f"Rule {rule_id} violation"
        row_dict['dq_detected_ts_utc'] = datetime.utcnow()
        row_dict['dw_batch_id'] = batch_id
        row_dict['raw_payload'] = json.dumps(row_dict)
        
        cols = ', '.join(row_dict.keys())
        vals = ', '.join(['%s'] * len(row_dict))
        sql = f"INSERT INTO {quarantine_table} ({cols}) VALUES ({vals})"
        
        cursor.execute(sql, tuple(row_dict.values()))
    
    target_conn.commit()
```

## Phase 5: Reconciliation

**5.1 Reconciliation: Bronze → Silver → Gold**

```python
def reconcile_bronze_to_silver_to_gold(control_conn):
    """
    RC-2: Bronze → Silver
    RC-3: Silver → Gold
    """
    
    cursor = control_conn.cursor()
    
    # RC-2: Bronze rows = Silver loaded + quarantined + explicitly rejected
    cursor.execute("""
        SELECT 'orders' as entity,
               (SELECT COUNT(*) FROM bronze.br_orders WHERE dw_batch_id = %s) as bronze_count,
               (SELECT COUNT(*) FROM silver.slv_order WHERE dw_batch_id = %s) as silver_count,
               (SELECT COUNT(*) FROM silver.slv_order_quarantine WHERE dw_batch_id = %s) as quarantine_count
    """, (batch_id, batch_id, batch_id))
    
    # Verify counts balance
    results = cursor.fetchall()
    
    for entity, bronze_cnt, silver_cnt, quarantine_cnt in results:
        expected_total = silver_cnt + quarantine_cnt
        passed = bronze_cnt == expected_total
        
        result_sql = """
        INSERT INTO control.ctl_reconciliation 
        (dw_batch_id, source_table, target_table, check_name, 
         source_row_count, target_row_count, result, details)
        VALUES (%s, %s, %s, 'RC-2_BRONZE_TO_SILVER', %s, %s, %s, %s)
        """
        
        status = 'PASS' if passed else 'FAIL'
        details = f"Bronze: {bronze_cnt}, Silver: {silver_cnt}, Quarantine: {quarantine_cnt}"
        
        cursor.execute(result_sql, (
            batch_id, entity, f"silver.slv_{entity}",
            bronze_cnt, expected_total, status, details
        ))
    
    control_conn.commit()
```

## Phase 6: Scorecard and Publication

**6.1 Create DQ Scorecard**

```python
def create_dq_scorecard(control_conn, batch_id, run_cutoff):
    """
    KPI-33 through KPI-42: DQ metrics
    - Per-rule pass/fail and affected rows
    - Quarantine counts per table
    - Reconciliation results
    - Cohort mix
    - Restaurant concentration (KPI-41)
    - Freshness: max business date >= run date - 1
    - Duration vs SLA
    """
    
    cursor = control_conn.cursor()
    
    # Calculate metrics
    cursor.execute("""
        SELECT 
            (SELECT COUNT(*) FROM silver.slv_order WHERE dw_source_cohort = 'COHORT_A') as cohort_a_orders,
            (SELECT COUNT(*) FROM silver.slv_order WHERE dw_source_cohort = 'COHORT_B') as cohort_b_orders,
            (SELECT COUNT(*) FROM gold.fact_order) as total_facts
    """)
    
    cohort_a, cohort_b, total_facts = cursor.fetchone()
    cohort_concentration_a = (cohort_a / (cohort_a + cohort_b)) if (cohort_a + cohort_b) > 0 else 0
    
    # Restaurant concentration
    cursor.execute("""
        SELECT restaurant_id, COUNT(*) as order_count
        FROM gold.fact_order
        GROUP BY restaurant_id
        ORDER BY order_count DESC
        LIMIT 1
    """)
    
    top_restaurant = cursor.fetchone()
    restaurant_concentration = (top_restaurant[1] / total_facts * 100) if total_facts > 0 else 0
    
    # Insert scorecard
    insert_sql = """
    INSERT INTO gold.mart_dq_scorecard (
        dw_batch_id, cohort_a_count, cohort_b_count, cohort_a_percent,
        restaurant_concentration_percent, total_facts_loaded,
        created_ts
    )
    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
    """
    
    cursor.execute(insert_sql, (
        batch_id, cohort_a, cohort_b, cohort_concentration_a * 100,
        restaurant_concentration, total_facts
    ))
    
    control_conn.commit()
```

# Technical Standards

## Silver Layer Design Patterns

**Entity Deduplication**:
- Business key: natural identifier (order_id, customer_id, etc.)
- Grain: one row per business key
- Merge on business key: INSERT OR UPDATE (or DELETE + INSERT for idempotency)

**Data Quality Flags**:
- Column naming: `dq_flag_<issue>` (e.g., `dq_flag_cancel_mismatch`)
- Type: BOOLEAN
- Meaning: TRUE = this row has this quality issue
- Downstream: flag is readable, but row loads to Silver (non-blocking)

**Conformance Mappings**:
- Apply via JOIN to silver.ref_status_map
- Create conformed columns: order_status_conformed, payment_status_conformed
- Track original: original_status column retained for audit trail

## Gold Dimensional Design (SCD2)

**Surrogate Keys**:
- Every dimension has surrogate key: <entity>_sk (e.g., customer_sk)
- Type: BIGINT, auto-increment
- Degenerate dimensions: no SK, BK lives on fact

**Validity Intervals**:
- Half-open interval: [valid_from_utc, valid_to_utc)
- Non-overlapping, gapless per business key (tested invariant)
- valid_to_utc = NULL for current version

**SCD2 Merge Semantics**:
- ELSE IF dw_row_hash unchanged: NO ACTION (preserve current version, do NOT bump valid_to or version_no)
- ELSE IF dw_row_hash changed: EXPIRE current (set valid_to = run_cutoff, is_current = FALSE), INSERT new version
- ELSE IF key absent: set dw_is_deleted = TRUE, keep version open

**Late-Arriving Dimensions**:
- If fact references missing dimension: create inferred member (all attributes UNKNOWN)
- Set dw_is_inferred = TRUE
- Later dimension load enriches this member
- Idempotent: only create once per key

## Fact Table Grain

**Fact Grain Definition** (explicit per fact table):
- fact_order: ONE row per order (order_id is grain)
- fact_order_item: ONE row per order line item (order_item_id is grain)
- fact_payment_attempt: ONE row per payment attempt (payment_id is grain)
- fact_payment: ONE row per collected payment per order (order_id is grain, post-retry-collapse)
- fact_delivery: ONE row per delivery (delivery_id is grain)
- fact_review: ONE row per review (review_id is grain)
- fact_order_fulfilment: ONE row per order (accumulating, updated in place)

**Degenerate Dimensions**:
- Store business key on fact (order_id, payment_id, delivery_id, review_id)
- No separate dimension table for degenerates
- Enables drill-through in BI tools

## Aggregate Mart Design

**mart_order_daily**:
- Grain: (order_date_key, restaurant_id, order_status)
- Filters: is_active = TRUE (exclude deleted)
- Exclude synthetic outlier: WHERE restaurant_id != 214 (or per business decision)
- Metrics: COUNT(*), SUM(total_price), SUM(tax_amount), COUNT(DISTINCT customer_id)
- Rebuild: TRUNCATE + INSERT (full rebuild every run, safer than UPSERT)

**mart_revenue_daily**:
- Grain: (payment_date_key, payment_method, dw_source_cohort)
- Metrics: COUNT(*), SUM(payment_amount), SUM(superseded_attempt_count)
- Filter by COHORT_A and COHORT_B separately
- Reconcile to fact_payment counts

## Row Hashing for Change Detection

**Standard Approach**:
```python
def calculate_row_hash(row, business_keys):
    """Calculate MD5 hash of non-key attributes"""
    non_key_attrs = [
        str(v) for k, v in row.items()
        if k not in business_keys and not k.startswith('dw_')
    ]
    hash_input = '|'.join(non_key_attrs)
    return hashlib.md5(hash_input.encode()).hexdigest()
```

**Properties**:
- Deterministic: same input always produces same hash
- Order-sensitive: column order matters (use alphabetical or defined order)
- Null-safe: convert NULL to empty string
- Type-safe: convert all to string representation

# Decision Rules

When implementing transformations:

1. **Cohort Assignment** (BR-R2):
   - IF order_id <= 10928 THEN COHORT_A (early, human vocabulary, complete line detail)
   - ELSE COHORT_B (late, machine vocabulary, synthetic)
   - Assign cohort once in Silver, propagate to all child facts

2. **Status Conformance** (BR-R8):
   - Use silver.ref_status_map JOIN on source status value
   - If no mapping found: use 'UNKNOWN' or flag as data quality error
   - Store both source status (audit) and conformed status (analytics)

3. **Contradiction Resolution** (BR-R7):
   - IF is_cancelled != (order_status == 'CANCELLED'):
     - Use order_status (more authoritative)
     - Set dq_flag_cancel_mismatch = TRUE
   - Do NOT arbitrarily pick one; flag for downstream investigation

4. **Payment Retry Collapse** (BR-R5):
   - Rank per order: (PAID DESC, payment_date DESC, payment_id DESC)
   - Keep rank=1, discard others
   - Set attempt_count and superseded_attempt_count
   - Track in dq_flag_payment_retry

5. **Delivery Deduplication** (BR-R6):
   - Keep one row per order
   - Priority: latest terminal status > latest delivery_time > highest delivery_id
   - Discard earlier attempts

6. **SCD2 Version Decision**:
   - IF no existing record: insert with dw_version_no=1, is_current=TRUE, dw_initial_load=TRUE
   - IF hash unchanged: do NOT update (no new version)
   - IF hash changed: expire (valid_to=cutoff, is_current=FALSE), insert new version

7. **As-At Dimension Join**:
   - Lookup dimension row WHERE business_key = fact.fk AND valid_from <= event_ts AND valid_to > event_ts
   - If found: use that version's surrogate key
   - If not found: check earliest version, use that, set dq_flag_dim_fallback
   - If key missing entirely: use _sk=-1

# Error-Handling Rules

**Data Quality Errors**:
- Row fails DQ rule (BLOCK severity): quarantine to slv_<entity>_quarantine
- Row fails DQ rule (QUARANTINE severity): load to Silver with dq_flag_* = TRUE
- Row fails DQ rule (WARN severity): load to Silver, count on scorecard

**Reconciliation Errors**:
- Bronze → Silver row count mismatch: log FAIL, prevent Gold load
- Silver → Gold grain change > threshold (e.g., collapse payment retries): expected, document
- Dimension key missing: create inferred member, flag dq_flag_dim_fallback

**Transformation Errors**:
- Cannot hash row: log error, skip hashing, continue
- Cannot join to dimension: use -1 key, set flag, continue
- Cannot conform status: use UNKNOWN, set flag, continue

**Idempotency Errors**:
- Re-running creates duplicate dimension versions: check hash before inserting
- Re-running creates duplicate facts: check if (batch_id, grain key) already exists

# Validation Requirements

After transformation completes, Antigravity must verify:

1. **Silver Validation**
   - slv_order: count > 0, dw_source_cohort populated (COHORT_A or COHORT_B)
   - slv_customer: no duplicates per customer_id
   - slv_payment: attempt_count populated, no duplicates per order_id
   - slv_delivery: one row per order, no duplicates
   - All dq_flag_* columns populated

2. **Gold Dimension Validation**
   - dim_customer: all versions non-overlapping per customer_id
   - dim_customer: exactly one is_current=TRUE per business key
   - dim_customer: valid_from < valid_to where both present
   - No version gaps per business key

3. **Gold Fact Validation**
   - fact_order: count matches expected (61,777 orders from source)
   - fact_order: all surrogate keys populated or -1
   - fact_order: cohort tagged for all rows
   - fact_order: dq_flag_dim_fallback count < 1% (alert if > 1%)

4. **Reconciliation Validation**
   - RC-2 results: all PASS (Bronze = Silver + quarantine)
   - RC-3 results: all PASS (Silver = Gold at expected grain)

5. **Scorecard Validation**
   - Cohort mix: COHORT_A + COHORT_B = total orders
   - Restaurant concentration: top restaurant >= 87%
   - Freshness: max business date = run date (or run date - 1 for off-peak runs)

6. **Idempotency Validation**
   - Run transformation twice: same batch
   - Query counts before and after: should be identical
   - No duplicate dimension versions, facts, or quarantine rows

# Expected Outputs

After successful transformation, Antigravity will produce:

1. **Silver Layer**
   - slv_order: 61,777 rows (or expected count)
   - slv_customer: customer count rows
   - slv_payment: one row per order with collected amount
   - slv_delivery: one row per order with delivery details
   - slv_<entity>_quarantine: failed rows with dq_rule_id and reason

2. **Gold Dimensions**
   - dim_customer: initial version load (SCD2 structure)
   - dim_restaurant: 370 rows
   - dim_menu_item: 7,298 rows
   - dim_delivery_partner: 2,555 rows
   - dim_cuisine: 38 rows
   - (Plus 8 other dimensions)

3. **Gold Facts**
   - fact_order: 61,777 rows
   - fact_order_item: (count from source)
   - fact_payment_attempt: 60,833 rows
   - fact_payment: (count after retry collapse)
   - fact_delivery: 60,533 rows
   - fact_review: 0 rows (or expected count)

4. **Aggregate Marts**
   - mart_order_daily: (order_date_key, restaurant_id, status) grain
   - mart_revenue_daily: (payment_date_key, method, cohort) grain

5. **Scorecard**
   - mart_dq_scorecard: one row per batch with DQ metrics
   - KPI-33 through KPI-42 values

# Completion Criteria

This skill is COMPLETE when:

1. ✅ All Silver entity tables populated
2. ✅ All Gold dimensions created and versioned (SCD2)
3. ✅ All Gold fact tables populated with correct grain
4. ✅ All aggregate marts built
5. ✅ All DQ rules evaluated and results recorded
6. ✅ Quarantine tables populated with failed rows
7. ✅ All reconciliation checks pass (RC-2, RC-3)
8. ✅ DQ scorecard created with all metrics
9. ✅ Cohort tagging complete (COHORT_A and COHORT_B)
10. ✅ As-at dimension joins validated
11. ✅ SCD2 change detection working
12. ✅ Payment retry collapse applied (BR-R5)
13. ✅ Delivery deduplication applied (BR-R6)
14. ✅ Status conformance applied (BR-R8)
15. ✅ Idempotency validated (transformation can re-run safely)
16. ✅ No incomplete TODO or TBD placeholders
17. ✅ Ready for BI tool consumption

# Handoff to Other Skills

## Next: BI/Analytics Tool Integration

**When to Trigger**:
- After this skill completes successfully
- After all Gold tables populated
- After all reconciliation checks pass
- After scorecard created

**What Must Be Available**:
- gold.fact_order with customer_sk, restaurant_sk, etc. joined
- gold.dim_customer, dim_restaurant, etc. ready for BI semantic layer
- gold.mart_dq_scorecard with daily metrics
- Aggregate marts ready for dashboard queries
- All surrogate keys populated, -1 for missing dimensions

**Information to Pass**:
- Gold layer row counts and sample data
- Dimensional model documentation
- Metric definitions and calculation rules
- Data lineage from source through Silver/Gold
- DQ scorecard metrics and how to interpret

# Prohibited Actions

Antigravity MUST NOT:

1. ❌ Load data to source system
2. ❌ Skip data quality rule evaluation
3. ❌ Bypass quarantine for blocking rule failures
4. ❌ Mix Silver transformations with Gold loading
5. ❌ Reuse surrogate keys across batches or time periods
6. ❌ Skip cohort tagging
7. ❌ Fail idempotency validation
8. ❌ Create dimension duplicates per business key
9. ❌ Skip SCD2 change detection
10. ❌ Omit as-at dimension joins
11. ❌ Hardcode business rules in code (use reference tables)
12. ❌ Skip reconciliation checks
13. ❌ Leave TODO or TBD in SQL or transformation logic
14. ❌ Mask PII at Gold layer (handle in BI semantic layer)
15. ❌ Omit scorecard or DQ metrics

# Final Response Format

After completing this skill, Antigravity must report:

## Summary
- Skill executed: bronze-to-gold-transformation
- Status: COMPLETED or FAILED
- Batch ID: <id>
- Execution time: <seconds>

## Transformation Results
- Silver tables loaded: 11 (entities + reference data)
- Gold dimensions loaded: 14
- Gold facts loaded: 6
- Aggregate marts built: 2
- Quarantine records: <count>

## Data Quality
- DQ rules evaluated: 40+
- Rules passed: <count>
- Rules failed: <count>
- Affected rows quarantined: <count>

## Reconciliation
- RC-2 (Bronze → Silver): PASS/FAIL
- RC-3 (Silver → Gold): PASS/FAIL
- All checks: <summary>

## Row Counts (Gold Facts)
- fact_order: <count>
- fact_order_item: <count>
- fact_payment: <count>
- fact_delivery: <count>
- fact_review: <count>

## Metrics
- Cohort A orders: <count>
- Cohort B orders: <count>
- Restaurant concentration: <percent>%
- Dimension versions created: <count>

## Validation
- Idempotency test: PASS
- SCD2 validity: PASS (no overlaps, no gaps)
- As-at joins: PASS
- Scorecard created: YES

## Ready for BI
- Gold layer: READY
- Semantic layer: Can now build BI queries

# Final Checklist

Antigravity must verify EVERY item before marking COMPLETE:

- ✅ Bronze data available from source-to-bronze skill
- ✅ All reference mappings loaded (status, cohort, DQ rules)
- ✅ Silver entity tables populated
- ✅ Cohort tagging applied (COHORT_A and COHORT_B)
- ✅ Status conformance applied (conformed status columns)
- ✅ Contradiction resolution applied (dq_flags)
- ✅ Payment retry collapse applied (attempt_count, superseded_count)
- ✅ Delivery deduplication applied
- ✅ Gold dimensions created with SCD2 structure
- ✅ Gold facts populated with correct grain
- ✅ Surrogate keys assigned or -1 for missing
- ✅ As-at dimension joins validated
- ✅ Aggregate marts built
- ✅ DQ rules evaluated and results recorded
- ✅ Quarantine tables populated
- ✅ Reconciliation checks all passed
- ✅ Scorecard created with metrics
- ✅ Idempotency validated (transformation re-runs safely)
- ✅ No duplicate dimension versions
- ✅ No gaps in dimension validity intervals
- ✅ No hardcoded credentials
- ✅ No TODO/TBD placeholders
- ✅ Ready for BI consumption
