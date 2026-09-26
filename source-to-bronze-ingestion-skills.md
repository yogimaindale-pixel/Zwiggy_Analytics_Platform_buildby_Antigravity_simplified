---
name: source-to-bronze-ingestion
description: Builds and executes the metadata-driven incremental ingestion pipeline that extracts data from the source PostgreSQL database and lands it into the Bronze layer with full source fidelity. Handles watermark management, reconciliation, idempotency, and initial/incremental load strategies.
---

# Purpose

This skill implements the complete Source-to-Bronze data ingestion pipeline as specified in the Functional Requirements document. It extracts data from the 18 source tables in PostgreSQL `zwiggy_db`, respects the incremental strategy for each table (TIMESTAMP_WATERMARK, CREATED_DATE_WATERMARK, KEY_WATERMARK, FULL_SNAPSHOT, etc.), lands raw data into Bronze layer with source fidelity preserved, and validates extraction using reconciliation checks.

This skill executes **after dwh-metadata-and-foundations** and **before bronze-to-gold-transformation**.

# When to Use This Skill

- **Initial data load**: First ingestion to populate Bronze from empty state
- **Daily incremental runs**: Regular scheduled ingestion of new and updated records
- **Batch replays**: Re-running a failed batch window to recover lost data
- **Backfill operations**: Extracting historical data for new source tables
- **Maintenance windows**: Periodic full refreshes per row configuration policy

# When Not to Use This Skill

- Do not use this for schema creation (dwh-metadata-and-foundations handles that)
- Do not use this for data transformation (belongs to bronze-to-gold-transformation)
- Do not use this for dimensional modeling or aggregations (Gold layer responsibility)
- Do not use this for BI tool configuration or dashboard creation
- Do not use this for fixing data quality issues already identified (use quarantine procedures)

# Project Context

**Source System**: PostgreSQL 18.1, database `zwiggy_db`, schema `app`, 18 tables, 177 columns, 336,751 rows  
**Target**: Bronze layer in PostgreSQL/DuckDB/Parquet (target technology decided in foundations skill)  
**Watermark Strategy**: Per-table configuration, supporting TIMESTAMP_WATERMARK (most common), CREATED_DATE_WATERMARK, KEY_WATERMARK, FULL_SNAPSHOT  
**Scope**: Source extraction and Bronze landing only; no transformation occurs here

**18 Source Tables**:
1. `orders` - 61,777 rows (largest, transactional)
2. `order_items` - transactional (child of orders)
3. `payments` - 60,833 rows (transactional)
4. `delivery_details` - 60,533 rows (transactional)
5. `reviews` - 0 rows (empty at start)
6. `cart` - transactional
7. `cart_items` - transactional
8. `customer` - master data
9. `user_address` - master data
10. `restaurant` - master data
11. `menu_item` - master data
12. `delivery_partner` - master data
13. `cuisines` - 38 rows (reference)
14. `gender` - 1 row (reference)
15. `order_cancellation` - 0 rows (empty at start)
16. `restaurant_cuisine` - 0 rows (empty at start)
17. `restaurant_owner` - 0 rows (empty at start)
18. `refunds` - 0 rows (empty at start)

**Key Data Quality Challenges**:
- Two incompatible cohorts separated at order_id 10,928 (different vocabularies, completeness)
- 11% of orders (7,019) marked paid but pending status
- 11% of orders (6,794) contradictory cancellation flag
- 13,133 orders missing payment records
- 4,239 orders missing delivery records
- One restaurant accounts for 87.1% of orders (concentration outlier)

# Required Files to Read

Before executing this skill, Antigravity must review:

1. **Functional Requirements Document** (complete)
   - `Functional Requirements.docx` - All 36 sections, specifically:
   - §1-3: Purpose, technology scope, core design principles
   - §4: Classification schemes (7 ingestion patterns)
   - §5-25: Detailed functional requirements FR-01 through FR-37
   - §33-36: Classification matrix format, decision flow, target pipeline behavior

2. **BRD Part B - Data Warehouse Document** (relevant sections)
   - `BRD-B-DWH-Medallion-Project-v0.1.pdf`
   - §4: Source system facts, extraction patterns (E1-E5)
   - §4.3: Watermark requirements
   - §5: Bronze layer specification and load patterns

3. **Source Schema Details**
   - `Source Schema Details.xlsx` - Column-level metadata for all 18 tables
   - Data types, primary keys, nullable indicators, defaults, identity sequences

4. **Control Table Configuration**
   - From dwh-metadata-and-foundations skill output
   - `control.ctl_table_config` - 18 rows with ingestion strategies and watermark definitions

# Preconditions

Before this skill can execute, verify:

1. **dwh-metadata-and-foundations Skill Must Complete**
   - control.ctl_batch table exists and is empty
   - control.ctl_table_config has 18 rows, all source tables classified
   - control.ctl_watermark exists and is empty
   - All 18 bronze table skeletons created
   - Source connectivity validated

2. **Source Connectivity**
   - Read-only access to PostgreSQL 18.1 database zwiggy_db
   - Credentials available (not hardcoded)
   - INFORMATION_SCHEMA queryable
   - All 18 tables accessible and readable
   - Source row counts retrieved: 336,751 total rows

3. **Target Storage**
   - Bronze schema accessible and writable
   - All 18 br_* tables created
   - Sufficient disk/storage for initial load (~50MB+ expected)

4. **Batch Configuration**
   - Batch ID generation strategy defined (e.g., BIGINT auto-increment)
   - Run cutoff timestamp generation logic ready
   - Initial vs incremental decision logic available

5. **Python Environment**
   - psycopg2 or equivalent PostgreSQL connector
   - pandas for data manipulation
   - sqlalchemy for ORM (optional)
   - datetime, logging, json, csv modules

6. **Configuration Externalized**
   - Source credentials via environment variables or secrets manager
   - Target credentials via environment variables or secrets manager
   - Batch parameters (concurrency, timeout, retry count) configurable

# Responsibilities

This skill is exclusively responsible for:

1. **Source Metadata Discovery**
   - Query source INFORMATION_SCHEMA for table and column metadata
   - Extract: schema name, table name, column names, data types, PK, nullable, defaults
   - Identify numeric/sequential keys, timestamp columns, delete indicators
   - Validate discovered schema against expected baseline
   - Document schema drift (new columns, removed columns, type changes)

2. **Extraction Strategy Selection**
   - For each table: read ctl_table_config ingestion_strategy value
   - Apply correct extraction predicate per strategy:
     - TIMESTAMP_WATERMARK: `WHERE watermark_column > last_watermark AND watermark_column <= cutoff MINUS lookback days`
     - CREATED_DATE_WATERMARK: `WHERE created_column > last_watermark AND created_column <= cutoff`
     - KEY_WATERMARK: `WHERE primary_key > last_watermark`
     - COMPOSITE_WATERMARK: `WHERE (watermark_column, primary_key) > (last_watermark, last_key)`
     - FULL_SNAPSHOT: `SELECT *` (rebuild every run)
     - FULL_REFERENCE: `SELECT *` (small reference tables)
   - Never combine strategies: one per table, no mixing

3. **Batch Creation and Watermark Initialization**
   - Insert one row into control.ctl_batch per run:
     - dw_batch_id: auto-increment
     - batch_start_ts_utc: CURRENT_TIMESTAMP
     - run_cutoff_ts_utc: fixed for entire batch (same for all tables)
     - run_type: INITIAL_LOAD or INCREMENTAL or REPLAY
     - status: IN_PROGRESS
     - triggered_by: e.g., 'SCHEDULER' or 'MANUAL'
   - This batch ID attached to all extracted rows

4. **Watermark State Retrieval**
   - Before extraction: query control.ctl_watermark for each table
   - If no row: initial load, extract from beginning (X-1: use run_cutoff, not current time)
   - If row exists: read watermark_value and secondary_value
   - Mark as: initial=FALSE if row existed, initial=TRUE otherwise

5. **Source Extraction**
   - For each table: build and execute SQL query based on strategy
   - Respect X-3: never lock OLTP (use read replica if available, off-peak window)
   - Respect X-5: late-arriving data, include 7-day look-back for transactional tables
   - Execute extraction in dependency order or parallel groups per ctl_table_config.table_group
   - Capture min/max watermark values during extraction for manifest

6. **Technical Metadata Addition (Bronze Columns)**
   - Add to every extracted row:
     - `dw_ingest_date`: business date of the run
     - `dw_batch_id`: same batch ID for all rows in run
     - `dw_ingest_ts_utc`: extraction timestamp
     - `dw_source_system`: 'zwiggy_db'
     - `dw_source_schema`: 'app'
     - `dw_source_table`: actual table name (e.g., 'orders')
   - Do NOT transform source values, preserve exactly as received

7. **Bronze Data Load**
   - Write extracted rows to corresponding br_* table
   - Partition by dw_ingest_date (if platform supports)
   - Use idempotent write strategy:
     - Primary key: (dw_batch_id, source_primary_key)
     - On conflict: DELETE old rows for this batch_id and source key, INSERT new
     - Or: DELETE * FROM table WHERE dw_batch_id = current_id, then INSERT ALL
   - Ensure no duplicates if same batch re-run

8. **Extraction Manifest Creation**
   - For each table extraction: create manifest row in control.audit_source_extract:
     - dw_batch_id: this batch
     - source_table: which table
     - extract_row_count: how many rows extracted
     - extract_start_ts / extract_end_ts: extraction duration
     - min_watermark_value / max_watermark_value: actual range extracted
     - checksum_hash: MD5 or SHA256 of row count + min/max watermark (for validation)
     - extract_status: SUCCESS or FAILED

9. **Reconciliation Validation** (Mandatory Every Run)
   - After Bronze load: run reconciliation checks per §9.4 BRD-B:
     - RC-1: Extract manifest row count = Bronze loaded rows (EXACT match)
     - RC-2: For each table, Bronze rows must equal Source rows extracted (no unexplained loss)
     - On mismatch: log error, record in control.ctl_reconciliation with result=FAIL
   - If critical reconciliation fails: mark batch status=FAILED, do NOT advance watermark

10. **Watermark Advance** (Only on Success)
    - After all extraction and Bronze load succeeds:
    - After reconciliation passes:
    - Query Bronze to get actual min/max values loaded for that table
    - Update control.ctl_watermark with new watermark value
    - Update is_initial_load_complete = TRUE for that table (first time only)
    - Update current_status = SUCCESS

11. **Failed Batch Handling**
    - If extraction fails for a table: log to audit_run_log, record in ctl_watermark
    - Do NOT advance that table's watermark
    - If reconciliation fails: mark entire batch FAILED, prevent publish
    - Next run will re-attempt same batch window (X-2: watermark unchanged)

12. **Audit Logging**
    - Log every step to control.audit_run_log:
      - Batch start: 'Batch <id> started, run_type=INITIAL_LOAD/INCREMENTAL'
      - Per table: '<table> extracted <count> rows, min_watermark=<val>, max=<val>'
      - Per table: '<table> loaded <count> rows to Bronze'
      - Per table: '<table> reconciliation PASS/FAIL, details=<info>'
      - Watermark advance: '<table> watermark advanced to <value>'
      - Batch end: 'Batch <id> completed, status=COMPLETED/FAILED, duration=<sec>'
    - All with timestamp and severity level (INFO, WARN, ERROR)

13. **Empty Table Handling**
    - If source table returns 0 rows: still valid, record in manifest
    - Bronze receives 0 rows: reconciliation checks should pass (0=0)
    - Watermark NOT advanced for empty tables in initial load (ambiguous)
    - Empty tables must not fail the batch (per FR-25)

14. **Schema Evolution**
    - Before extraction: query INFORMATION_SCHEMA, compare vs expected schema
    - If new column in source: log warning, append to Bronze (FR-27)
    - If column removed from source: log error, mark table for investigation (FR-28)
    - If data type changed: log error, mark table as failed
    - If watermark column changed: log error, halt ingestion (FR-29)

15. **Retry Logic**
    - Transient failures (connection timeout, network): retry up to 3 times
    - Permanent failures (schema error, SQL syntax): fail immediately, no retry
    - Log retry attempts to audit_run_log with attempt number and delay

16. **Dependency Management**
    - Extract tables in dependency order or parallel groups:
      - GroupA (independent first): Gender, Cuisines
      - GroupB (masters): Customer, User_Address, Restaurant, Delivery_Partner, Menu_Item, Restaurant_Cuisine, Restaurant_Owner
      - GroupC (transactions): Orders, Order_Items, Payments, Delivery_Details, Reviews, Cart, Cart_Items, Order_Cancellation, Refunds
    - Or parallelise within each group if ctl_table_config.table_group is defined
    - Fail entire batch if a GroupB table fails (dependent tables need master data)

17. **Execution Workflow Orchestration**
    - Parse input parameters: run_type (INITIAL_LOAD, INCREMENTAL, REPLAY), target_date
    - Create batch in ctl_batch with status=IN_PROGRESS
    - Loop through active tables in ctl_table_config:
      - Read strategy, watermark, primary key
      - Determine initial vs incremental
      - Read last successful watermark (if exists)
      - Execute extraction query
      - Add technical columns
      - Load to Bronze
      - Create manifest
      - Log results
    - After all tables:
      - Run reconciliation checks
      - If all pass: update watermarks, mark batch COMPLETED
      - If any fail: mark batch FAILED, leave watermarks unchanged
    - Log final batch status and duration

# Step-by-Step Execution Workflow

## Phase 1: Initialization and Validation

**1.1 Establish Connections**

```python
def init_connections():
    # Source connection (read-only)
    source_conn = psycopg2.connect(
        host=os.environ['SOURCE_HOST'],
        port=os.environ['SOURCE_PORT'],
        database=os.environ['SOURCE_DB'],
        user=os.environ['SOURCE_USER'],
        password=os.environ['SOURCE_PASSWORD'],
        connect_timeout=10
    )
    
    # Target connection (write)
    target_conn = psycopg2.connect(
        host=os.environ['TARGET_HOST'],
        port=os.environ['TARGET_PORT'],
        database=os.environ['TARGET_DB'],
        user=os.environ['TARGET_USER'],
        password=os.environ['TARGET_PASSWORD'],
        connect_timeout=10
    )
    
    # Control DB connection (audit tables)
    control_conn = target_conn  # Usually same as target
    
    return source_conn, target_conn, control_conn

def log_event(control_conn, batch_id, event_type, message, severity='INFO'):
    """Audit logging to control.audit_run_log"""
    insert_sql = """
    INSERT INTO control.audit_run_log 
    (dw_batch_id, event_type, message, severity, logged_ts)
    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
    """
    cursor = control_conn.cursor()
    cursor.execute(insert_sql, (batch_id, event_type, message, severity))
    control_conn.commit()
```

**1.2 Validate Preconditions**

```python
def validate_preconditions(source_conn, target_conn):
    """Verify all prerequisites are met"""
    
    # Check source tables exist and are queryable
    source_cursor = source_conn.cursor()
    source_cursor.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'app' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    source_tables = [row[0] for row in source_cursor.fetchall()]
    
    expected_tables = [
        'orders', 'order_items', 'payments', 'delivery_details', 'reviews',
        'cart', 'cart_items', 'customer', 'user_address', 'restaurant',
        'menu_item', 'delivery_partner', 'cuisines', 'gender',
        'order_cancellation', 'restaurant_cuisine', 'restaurant_owner', 'refunds'
    ]
    
    missing = set(expected_tables) - set(source_tables)
    if missing:
        raise ValueError(f"Missing source tables: {missing}")
    
    # Check control tables exist
    target_cursor = target_conn.cursor()
    target_cursor.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'control' AND table_type = 'BASE TABLE'
    """)
    control_tables = {row[0] for row in target_cursor.fetchall()}
    
    required_control = {'ctl_batch', 'ctl_table_config', 'ctl_watermark', 'audit_source_extract'}
    if not required_control.issubset(control_tables):
        raise ValueError(f"Missing control tables: {required_control - control_tables}")
    
    # Check Bronze schema exists
    target_cursor.execute("""
        SELECT schema_name FROM information_schema.schemata 
        WHERE schema_name = 'bronze'
    """)
    if not target_cursor.fetchone():
        raise ValueError("Bronze schema does not exist")
    
    print("✓ All preconditions validated")
```

**1.3 Create Batch Record**

```python
def create_batch(control_conn, run_type='INCREMENTAL', triggered_by='MANUAL'):
    """Insert batch header into control.ctl_batch"""
    
    insert_sql = """
    INSERT INTO control.ctl_batch 
    (batch_start_ts_utc, run_cutoff_ts_utc, run_type, status, triggered_by, code_version)
    VALUES (
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP,
        %s,
        'IN_PROGRESS',
        %s,
        '0.1'
    )
    RETURNING dw_batch_id
    """
    
    cursor = control_conn.cursor()
    cursor.execute(insert_sql, (run_type, triggered_by))
    batch_id = cursor.fetchone()[0]
    control_conn.commit()
    
    return batch_id

def get_run_cutoff(control_conn, batch_id):
    """Get the run_cutoff_ts_utc for this batch"""
    cursor = control_conn.cursor()
    cursor.execute(
        "SELECT run_cutoff_ts_utc FROM control.ctl_batch WHERE dw_batch_id = %s",
        (batch_id,)
    )
    return cursor.fetchone()[0]
```

**1.4 Discover Source Metadata**

```python
def discover_source_schema(source_conn):
    """Extract source metadata from INFORMATION_SCHEMA"""
    
    cursor = source_conn.cursor()
    
    schema = {}
    
    # Get all tables in schema 'app'
    cursor.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'app' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    
    tables = [row[0] for row in cursor.fetchall()]
    
    for table_name in tables:
        # Get columns
        cursor.execute("""
            SELECT 
                column_name, data_type, is_nullable, column_default,
                ordinal_position
            FROM information_schema.columns
            WHERE table_schema = 'app' AND table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        
        columns = {}
        for col_name, col_type, nullable, default, ordinal in cursor.fetchall():
            columns[col_name] = {
                'type': col_type,
                'nullable': nullable == 'YES',
                'default': default,
                'ordinal': ordinal
            }
        
        # Get primary key
        cursor.execute("""
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            JOIN pg_class c ON c.oid = i.indrelid
            WHERE c.relname = %s AND i.indisprimary
            ORDER BY a.attnum
        """, (table_name,))
        
        pk_cols = [row[0] for row in cursor.fetchall()]
        
        schema[table_name] = {
            'columns': columns,
            'primary_key': pk_cols,
            'row_count': None
        }
    
    # Get row counts
    for table_name in tables:
        cursor.execute(f"SELECT COUNT(*) FROM app.{table_name}")
        schema[table_name]['row_count'] = cursor.fetchone()[0]
    
    return schema
```

**1.5 Load Table Configuration**

```python
def load_table_config(control_conn):
    """Read ingestion strategies from control.ctl_table_config"""
    
    cursor = control_conn.cursor()
    cursor.execute("""
        SELECT 
            source_table, ingestion_strategy, watermark_column, secondary_watermark_column,
            primary_key_column, business_key, lookback_days, is_initial_load_complete,
            is_active, table_group
        FROM control.ctl_table_config
        WHERE is_active = TRUE
        ORDER BY CASE table_group 
            WHEN 'GROUP_A' THEN 1
            WHEN 'GROUP_B' THEN 2
            WHEN 'GROUP_C' THEN 3
            ELSE 99 END,
            source_table
    """)
    
    config = {}
    for row in cursor.fetchall():
        source_table, strategy, watermark_col, secondary_col, pk_col, biz_key, \
            lookback, initial_complete, active, group = row
        
        config[source_table] = {
            'strategy': strategy,
            'watermark_column': watermark_col,
            'secondary_watermark_column': secondary_col,
            'primary_key_column': pk_col,
            'business_key': biz_key,
            'lookback_days': lookback or 0,
            'is_initial_load_complete': initial_complete,
            'table_group': group
        }
    
    return config
```

## Phase 2: Extraction Strategy Application

**2.1 Build Extraction Query by Strategy**

```python
def build_extraction_query(table_name, strategy, config, watermark_state, run_cutoff, source_schema):
    """Generate extraction SQL based on ingestion strategy"""
    
    select_clause = f"SELECT * FROM {source_schema}.{table_name}"
    where_clause = ""
    
    if strategy == 'TIMESTAMP_WATERMARK':
        # Most common: WHERE watermark_col > last AND watermark_col <= cutoff - lookback
        watermark_col = config['watermark_column']
        last_watermark = watermark_state.get('watermark_value')
        lookback = timedelta(days=config['lookback_days'])
        adjusted_cutoff = run_cutoff - lookback
        
        if last_watermark:
            where_clause = f"WHERE {watermark_col} > '{last_watermark}' AND {watermark_col} <= '{adjusted_cutoff}'"
        else:
            # Initial load: all rows up to cutoff - lookback
            where_clause = f"WHERE {watermark_col} <= '{adjusted_cutoff}'"
    
    elif strategy == 'CREATED_DATE_WATERMARK':
        # For append-only: WHERE created >= last AND created <= cutoff
        watermark_col = config['watermark_column']  # Usually 'created_at'
        last_watermark = watermark_state.get('watermark_value')
        
        if last_watermark:
            where_clause = f"WHERE {watermark_col} > '{last_watermark}' AND {watermark_col} <= '{run_cutoff}'"
        else:
            where_clause = f"WHERE {watermark_col} <= '{run_cutoff}'"
    
    elif strategy == 'KEY_WATERMARK':
        # For monotonic key: WHERE pk > last_pk
        pk_col = config['primary_key_column']
        last_watermark = watermark_state.get('watermark_value')
        
        if last_watermark:
            where_clause = f"WHERE {pk_col} > {last_watermark}"
        else:
            where_clause = f"WHERE 1=1"  # Initial load: all rows
    
    elif strategy == 'COMPOSITE_WATERMARK':
        # WHERE (ts, pk) > (last_ts, last_pk)
        watermark_col = config['watermark_column']
        pk_col = config['primary_key_column']
        last_ts = watermark_state.get('watermark_value')
        last_pk = watermark_state.get('watermark_secondary_value')
        
        if last_ts and last_pk:
            where_clause = f"WHERE ({watermark_col}, {pk_col}) > ('{last_ts}', {last_pk})"
        else:
            where_clause = f"WHERE 1=1"
    
    elif strategy in ['FULL_SNAPSHOT', 'FULL_REFERENCE']:
        # No WHERE clause: full extract every run
        where_clause = ""
    
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
    
    return f"{select_clause} {where_clause}" if where_clause else select_clause
```

**2.2 Execute Source Extraction**

```python
def extract_table(source_conn, table_name, extraction_sql):
    """Execute extraction query against source database"""
    
    cursor = source_conn.cursor()
    start_ts = datetime.utcnow()
    
    cursor.execute(extraction_sql)
    rows = cursor.fetchall()
    col_names = [desc[0] for desc in cursor.description]
    
    end_ts = datetime.utcnow()
    duration_sec = (end_ts - start_ts).total_seconds()
    
    # Convert to list of dicts
    data = [dict(zip(col_names, row)) for row in rows]
    
    return {
        'rows': data,
        'count': len(data),
        'columns': col_names,
        'start_ts': start_ts,
        'end_ts': end_ts,
        'duration_sec': duration_sec
    }

def add_bronze_columns(data, batch_id, table_name, ingest_date, ingest_ts):
    """Add technical columns to extracted data"""
    
    enriched = []
    
    for row in data:
        row_dict = row.copy()
        row_dict['dw_ingest_date'] = ingest_date
        row_dict['dw_batch_id'] = batch_id
        row_dict['dw_ingest_ts_utc'] = ingest_ts
        row_dict['dw_source_system'] = 'zwiggy_db'
        row_dict['dw_source_schema'] = 'app'
        row_dict['dw_source_table'] = table_name
        enriched.append(row_dict)
    
    return enriched
```

**2.3 Handle Watermark Boundaries**

```python
def get_watermark_boundaries(extracted_data, watermark_col, secondary_col=None):
    """Extract min/max watermark values from extracted data"""
    
    if not extracted_data:
        return None, None, None, None
    
    watermark_values = [row.get(watermark_col) for row in extracted_data if row.get(watermark_col)]
    
    if not watermark_values:
        return None, None, None, None
    
    min_wm = min(watermark_values)
    max_wm = max(watermark_values)
    
    if secondary_col:
        secondary_values = [row.get(secondary_col) for row in extracted_data if row.get(secondary_col)]
        min_secondary = min(secondary_values) if secondary_values else None
        max_secondary = max(secondary_values) if secondary_values else None
        return min_wm, max_wm, min_secondary, max_secondary
    
    return min_wm, max_wm, None, None
```

## Phase 3: Bronze Data Load

**3.1 Load Data to Bronze**

```python
def load_bronze(target_conn, table_name, enriched_data, batch_id):
    """Write enriched data to Bronze table"""
    
    if not enriched_data:
        return 0  # No data to load
    
    bronze_table = f"bronze.br_{table_name}"
    
    # Get column names from first row
    columns = list(enriched_data[0].keys())
    
    # Build INSERT statement
    col_str = ','.join(columns)
    val_str = ','.join(['%s'] * len(columns))
    
    insert_sql = f"INSERT INTO {bronze_table} ({col_str}) VALUES ({val_str})"
    
    cursor = target_conn.cursor()
    
    try:
        for row in enriched_data:
            values = tuple(row[col] for col in columns)
            cursor.execute(insert_sql, values)
        
        target_conn.commit()
        return len(enriched_data)
    
    except Exception as e:
        target_conn.rollback()
        raise ValueError(f"Failed to load {table_name}: {str(e)}")
```

**3.2 Idempotent Load (Handle Re-runs)**

```python
def idempotent_load(target_conn, table_name, enriched_data, batch_id, pk_column):
    """Load data idempotently: delete old batch data, insert new"""
    
    if not enriched_data:
        return 0
    
    bronze_table = f"bronze.br_{table_name}"
    
    cursor = target_conn.cursor()
    
    try:
        # Delete rows from same batch (if re-running)
        cursor.execute(f"DELETE FROM {bronze_table} WHERE dw_batch_id = %s", (batch_id,))
        delete_count = cursor.rowcount
        
        # Insert new data
        columns = list(enriched_data[0].keys())
        col_str = ','.join(columns)
        val_str = ','.join(['%s'] * len(columns))
        insert_sql = f"INSERT INTO {bronze_table} ({col_str}) VALUES ({val_str})"
        
        for row in enriched_data:
            values = tuple(row[col] for col in columns)
            cursor.execute(insert_sql, values)
        
        target_conn.commit()
        return len(enriched_data)
    
    except Exception as e:
        target_conn.rollback()
        raise ValueError(f"Idempotent load failed for {table_name}: {str(e)}")
```

## Phase 4: Reconciliation and Validation

**4.1 Create Extraction Manifest**

```python
def create_manifest(control_conn, batch_id, table_name, extraction_result, 
                    min_watermark, max_watermark, manifest_status='SUCCESS'):
    """Record extraction details in control.audit_source_extract"""
    
    insert_sql = """
    INSERT INTO control.audit_source_extract 
    (dw_batch_id, source_table, extract_row_count, extract_start_ts, extract_end_ts,
     min_watermark_value, max_watermark_value, extract_status, created_ts)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
    """
    
    cursor = control_conn.cursor()
    cursor.execute(insert_sql, (
        batch_id,
        table_name,
        extraction_result['count'],
        extraction_result['start_ts'],
        extraction_result['end_ts'],
        str(min_watermark),
        str(max_watermark),
        manifest_status
    ))
    
    control_conn.commit()
```

**4.2 Reconciliation: Extract vs Bronze**

```python
def reconcile_extract_vs_bronze(control_conn, batch_id, table_name, 
                                manifest_row_count, bronze_row_count):
    """RC-1: Verify extract count matches Bronze load count"""
    
    passed = manifest_row_count == bronze_row_count
    
    result_sql = """
    INSERT INTO control.ctl_reconciliation 
    (dw_batch_id, source_table, target_table, check_name, 
     source_row_count, target_row_count, result, details, checked_ts)
    VALUES (%s, %s, %s, 'RC-1_EXTRACT_VS_BRONZE', %s, %s, %s, %s, CURRENT_TIMESTAMP)
    """
    
    cursor = control_conn.cursor()
    result_status = 'PASS' if passed else 'FAIL'
    details = f"Extract: {manifest_row_count}, Bronze: {bronze_row_count}"
    
    cursor.execute(result_sql, (
        batch_id, table_name, f"bronze.br_{table_name}",
        manifest_row_count, bronze_row_count, result_status, details
    ))
    
    control_conn.commit()
    
    return passed
```

## Phase 5: Watermark Advancement

**5.1 Advance Watermark on Success**

```python
def advance_watermark(control_conn, table_name, new_watermark_value, 
                      secondary_value, batch_id, extract_count, load_count):
    """Update control.ctl_watermark after successful load"""
    
    update_sql = """
    UPDATE control.ctl_watermark
    SET watermark_value = %s,
        watermark_secondary_value = %s,
        last_successful_batch_id = %s,
        last_successful_run_ts = CURRENT_TIMESTAMP,
        extract_row_count = %s,
        load_row_count = %s,
        current_status = 'SUCCESS',
        updated_ts = CURRENT_TIMESTAMP
    WHERE source_table = %s
    """
    
    cursor = control_conn.cursor()
    cursor.execute(update_sql, (
        new_watermark_value, secondary_value, batch_id,
        extract_count, load_count, table_name
    ))
    
    control_conn.commit()
```

**5.2 Initialize Watermark (First Run)**

```python
def initialize_watermark(control_conn, table_name, initial_watermark_value, batch_id):
    """Insert first watermark row for table"""
    
    insert_sql = """
    INSERT INTO control.ctl_watermark 
    (source_system, source_schema, source_table, watermark_value, 
     last_successful_batch_id, last_successful_run_ts, current_status, updated_ts)
    VALUES ('zwiggy_db', 'app', %s, %s, %s, CURRENT_TIMESTAMP, 'SUCCESS', CURRENT_TIMESTAMP)
    """
    
    cursor = control_conn.cursor()
    try:
        cursor.execute(insert_sql, (table_name, initial_watermark_value, batch_id))
        control_conn.commit()
    except Exception as e:
        # Unique constraint might exist, try update
        control_conn.rollback()
        advance_watermark(control_conn, table_name, initial_watermark_value, None, batch_id, 0, 0)
```

## Phase 6: Batch Completion and Cleanup

**6.1 Complete Batch Successfully**

```python
def complete_batch(control_conn, batch_id):
    """Mark batch as COMPLETED"""
    
    update_sql = """
    UPDATE control.ctl_batch
    SET status = 'COMPLETED',
        batch_end_ts_utc = CURRENT_TIMESTAMP
    WHERE dw_batch_id = %s
    """
    
    cursor = control_conn.cursor()
    cursor.execute(update_sql, (batch_id,))
    control_conn.commit()

def fail_batch(control_conn, batch_id, error_reason):
    """Mark batch as FAILED and log reason"""
    
    update_sql = """
    UPDATE control.ctl_batch
    SET status = 'FAILED',
        batch_end_ts_utc = CURRENT_TIMESTAMP
    WHERE dw_batch_id = %s
    """
    
    cursor = control_conn.cursor()
    cursor.execute(update_sql, (batch_id,))
    
    # Log the failure
    log_event(control_conn, batch_id, 'BATCH_FAILED', 
              f"Batch failed: {error_reason}", 'ERROR')
    
    control_conn.commit()
```

**6.2 Main Pipeline Orchestration**

```python
def run_ingestion_pipeline(run_type='INCREMENTAL', triggered_by='SCHEDULER'):
    """Main pipeline entry point"""
    
    try:
        # Phase 1: Initialize
        source_conn, target_conn, control_conn = init_connections()
        
        validate_preconditions(source_conn, target_conn)
        
        batch_id = create_batch(control_conn, run_type, triggered_by)
        run_cutoff = get_run_cutoff(control_conn, batch_id)
        ingest_date = run_cutoff.date()
        ingest_ts = datetime.utcnow()
        
        log_event(control_conn, batch_id, 'BATCH_STARTED', 
                  f"Batch {batch_id} started, run_type={run_type}", 'INFO')
        
        source_schema = discover_source_schema(source_conn)
        table_config = load_table_config(control_conn)
        
        # Phase 2-5: Extract, Load, Reconcile for each table
        all_passed = True
        
        for table_name, config in table_config.items():
            try:
                # Get last watermark
                cursor = control_conn.cursor()
                cursor.execute(
                    "SELECT * FROM control.ctl_watermark WHERE source_table = %s",
                    (table_name,)
                )
                wm_row = cursor.fetchone()
                watermark_state = {
                    'watermark_value': wm_row[3] if wm_row else None,
                    'watermark_secondary_value': wm_row[4] if wm_row else None
                } if wm_row else {}
                
                # Build and execute extraction
                extraction_sql = build_extraction_query(
                    table_name, config['strategy'], config, watermark_state, 
                    run_cutoff, 'app'
                )
                
                extraction_result = extract_table(source_conn, table_name, extraction_sql)
                extract_count = extraction_result['count']
                
                log_event(control_conn, batch_id, f'EXTRACT_{table_name}',
                          f"Extracted {extract_count} rows from {table_name}", 'INFO')
                
                # Add technical columns
                enriched_data = add_bronze_columns(
                    extraction_result['rows'], batch_id, table_name, ingest_date, ingest_ts
                )
                
                # Load to Bronze
                bronze_count = idempotent_load(
                    target_conn, table_name, enriched_data, batch_id,
                    config['primary_key_column']
                )
                
                log_event(control_conn, batch_id, f'LOAD_{table_name}',
                          f"Loaded {bronze_count} rows to bronze.br_{table_name}", 'INFO')
                
                # Get watermark boundaries
                min_wm, max_wm, min_sec, max_sec = get_watermark_boundaries(
                    extraction_result['rows'], config['watermark_column'],
                    config['secondary_watermark_column']
                )
                
                # Create manifest
                create_manifest(control_conn, batch_id, table_name, 
                               extraction_result, min_wm, max_wm, 'SUCCESS')
                
                # Reconcile
                recon_pass = reconcile_extract_vs_bronze(
                    control_conn, batch_id, table_name, extract_count, bronze_count
                )
                
                if not recon_pass:
                    all_passed = False
                    log_event(control_conn, batch_id, f'RECON_FAIL_{table_name}',
                              f"Reconciliation failed: extract={extract_count}, bronze={bronze_count}",
                              'ERROR')
                else:
                    # Advance watermark
                    if extract_count > 0 or config['strategy'] in ['FULL_SNAPSHOT', 'FULL_REFERENCE']:
                        advance_watermark(control_conn, table_name, str(max_wm) if max_wm else None,
                                        str(max_sec) if max_sec else None, batch_id,
                                        extract_count, bronze_count)
                        log_event(control_conn, batch_id, f'WATERMARK_{table_name}',
                                  f"Watermark advanced to {max_wm}", 'INFO')
            
            except Exception as e:
                all_passed = False
                log_event(control_conn, batch_id, f'ERROR_{table_name}',
                          f"Failed to process {table_name}: {str(e)}", 'ERROR')
                create_manifest(control_conn, batch_id, table_name, 
                               {'count': 0, 'start_ts': None, 'end_ts': None},
                               None, None, 'FAILED')
        
        # Phase 6: Finalize
        if all_passed:
            complete_batch(control_conn, batch_id)
            log_event(control_conn, batch_id, 'BATCH_COMPLETED',
                      f"Batch {batch_id} completed successfully", 'INFO')
        else:
            fail_batch(control_conn, batch_id, "Reconciliation failures detected")
        
        return batch_id if all_passed else None
    
    finally:
        if source_conn:
            source_conn.close()
        if target_conn:
            target_conn.close()
```

# Technical Standards

## Extraction Patterns (Per Functional Requirements §4)

**Pattern E1: TIMESTAMP_WATERMARK** (Most Common)
- Use: Table has reliable updated_at that changes on every modification
- Query: `WHERE updated_at > last_watermark AND updated_at <= run_cutoff`
- Lookback: 7 days for late-arriving data (query: `WHERE updated_at > last_watermark - 7 days`)
- Example: orders, payments, delivery_details

**Pattern E2: CREATED_DATE_WATERMARK**
- Use: Table is append-only, only has created_at, no updates
- Query: `WHERE created_at > last_watermark AND created_at <= run_cutoff`
- Lookback: Usually 0 (no late arrivals for created_at)
- Example: reviews, order_cancellation

**Pattern E3: KEY_WATERMARK**
- Use: Table is append-only with monotonic PK (identity sequence)
- Query: `WHERE order_id > last_order_id`
- Lookback: 0
- Example: Very rare in Zwiggy source (most have timestamps)

**Pattern E4: COMPOSITE_WATERMARK**
- Use: Timestamps are non-unique, need tie-breaker
- Query: `WHERE (updated_at, id) > (last_ts, last_id)`
- Lookback: 7 days
- Example: None configured yet (could use for cart_items if needed)

**Pattern E5: FULL_SNAPSHOT**
- Use: No reliable incremental column, table is small, or reference data
- Query: `SELECT *` (entire table every run)
- Lookback: 0
- Example: gender (1 row), cuisines (38 rows)

**Pattern FULL_REFERENCE**
- Use: Small reference tables that change rarely
- Query: `SELECT *` but with less frequent scheduling
- Example: gender, cuisines

## Idempotency Implementation

**Batch ID Reusability**:
- If a batch fails partially, re-run with same batch_id
- Bronze table PK: (dw_batch_id, source_row_identifier)
- Logic: DELETE FROM bronze WHERE dw_batch_id = batch_id, then INSERT

**Watermark Advancement Rules**:
- Advance ONLY after:
  1. Extraction succeeds
  2. Bronze load succeeds
  3. Reconciliation checks pass
- If any step fails: do NOT advance watermark
- Failed batch leaves watermark unchanged → next run re-attempts same window
- This provides automatic retry capability

## Execution Order and Dependencies

**Dependency Groups** (parallel within group, sequential across groups):

Group A (Independent Reference):
- gender
- cuisines

Group B (Master/Dimension Data):
- customer
- user_address
- restaurant
- delivery_partner
- menu_item
- restaurant_cuisine
- restaurant_owner

Group C (Transactional, Dependent):
- orders (primary transaction)
- order_items (depends on orders)
- payments (depends on orders)
- delivery_details (depends on orders)
- reviews (depends on customer, menu_item, orders)
- cart (depends on customer)
- cart_items (depends on cart)
- order_cancellation (depends on orders)
- refunds (depends on payments)

**Execution Order**:
```
1. Run Group A (gender, cuisines) in parallel
2. Run Group B (all master tables) in parallel
3. Run Group C (all transaction tables) in parallel or sequentially
```

## Schema Evolution Detection

**Before Each Extraction**:
```python
def detect_schema_changes(source_conn, table_name):
    """Check source INFORMATION_SCHEMA vs expected schema"""
    
    # Query current source schema
    cursor.execute("""
        SELECT column_name, data_type FROM information_schema.columns
        WHERE table_schema = 'app' AND table_name = %s
    """, (table_name,))
    
    current_columns = {col: dtype for col, dtype in cursor.fetchall()}
    
    # Compare vs expected (from source_metadata discovery)
    expected_columns = {...}  # From initial discovery
    
    # Detect changes
    new_cols = set(current_columns.keys()) - set(expected_columns.keys())
    removed_cols = set(expected_columns.keys()) - set(current_columns.keys())
    type_changes = {col: (expected_columns[col], current_columns[col]) 
                    for col in current_columns 
                    if col in expected_columns and expected_columns[col] != current_columns[col]}
    
    if removed_cols or type_changes:
        raise ValueError(f"Breaking schema change detected: {removed_cols}, {type_changes}")
    
    if new_cols:
        # Log warning, allow new columns to flow to Bronze
        log_event(..., 'SCHEMA_DRIFT_NEW_COLUMNS', f"New columns: {new_cols}", 'WARN')
```

## Error Handling and Retry Strategy

**Transient Errors** (retry up to 3 times):
- Connection timeout
- Network interrupted
- Temporary database lock
- Temporary unavailability

**Permanent Errors** (fail immediately):
- Schema not found
- Column not found
- Type mismatch
- Permission denied
- SQL syntax error

**Retry Pattern**:
```python
def extract_with_retry(source_conn, extraction_sql, max_retries=3):
    for attempt in range(1, max_retries + 1):
        try:
            result = extract_table(source_conn, extraction_sql)
            return result
        except (psycopg2.DatabaseError, ConnectionError) as e:
            if attempt < max_retries and is_transient(e):
                wait_sec = 2 ** attempt  # Exponential backoff
                log_event(..., f'RETRY_ATTEMPT_{attempt}', f"Retrying after {wait_sec}s", 'WARN')
                time.sleep(wait_sec)
            else:
                raise
```

# Decision Rules

When building extraction queries:

1. **Watermark Column Selection** (from FR-36, FH-37):
   - If ctl_table_config.watermark_column is set: use it
   - Verify column exists in source schema
   - Verify column is a timestamp or numeric type
   - Verify column changes on every modification (for TIMESTAMP_WATERMARK)

2. **Initial vs Incremental Decision** (from FR-04, FR-22):
   - If ctl_watermark row does NOT exist for table: INITIAL_LOAD
   - If ctl_watermark row exists with watermark_value: INCREMENTAL
   - If ctl_watermark row exists but watermark_value is NULL: treat as INITIAL

3. **Look-Back Window Decision**:
   - For transactional tables (orders, payments, delivery): 7 days
   - For master tables (customer, restaurant): 0 days
   - For reference tables (gender, cuisines): 0 days
   - Configured in ctl_table_config.lookback_days

4. **Reconciliation Check Decision**:
   - RC-1: Always run (extract count vs Bronze loaded count)
   - If mismatch: log as FAIL, prevent watermark advance, fail batch
   - If reconciliation fails but extract=0 and load=0: pass (empty is valid)

5. **Watermark Value Type**:
   - For TIMESTAMP columns: use string format 'YYYY-MM-DD HH:MM:SS.sss'
   - For numeric columns: use integer or string representation
   - Store in control.ctl_watermark.watermark_value as VARCHAR(500)

# Error-Handling Rules

**Extraction Errors**:
- Cannot connect to source: log error, exit with status 1
- Source table missing: log error, mark table failed, continue
- Source column missing: log error, check schema drift, mark table failed
- Watermark column not found: log error, mark table failed

**Load Errors**:
- Bronze table missing: log error, recreate (should not happen, validation catches this)
- Data type mismatch: log error, retry with type casting (CAST to VARCHAR if needed)
- Null in non-null column: log error, mark row as problematic (Silver will quarantine)
- Duplicate key violation: log error, mark as idempotency issue, retry delete-then-insert

**Reconciliation Errors**:
- Extract count ≠ Bronze count: log FAIL, prevent watermark advance, mark batch FAILED
- Extract count = 0 but Bronze count > 0: log FAIL, prevent watermark advance
- Extract count > 0 but Bronze count = 0: log FAIL, prevent watermark advance

**Batch-Level Failures**:
- If any table fails extraction: mark batch IN_PROGRESS still, continue others
- If reconciliation fails: mark batch FAILED after all tables complete
- If critical table fails (no master data available): optionally fail batch immediately

# Validation Requirements

After successful ingestion, Antigravity must verify:

1. **Extraction Validation**
   - control.audit_source_extract has one row per table extracted
   - All rows have extract_row_count >= 0
   - All rows have extract_status = 'SUCCESS' (or PARTIAL for known misses)
   - Rows extracted sum to expected total

2. **Bronze Loading Validation**
   - bronze.br_orders has records (or intentionally 0)
   - bronze.br_customer has records (or intentionally 0)
   - All br_* tables have dw_batch_id = current batch
   - All rows have dw_ingest_date set correctly
   - Row counts per table match manifest

3. **Reconciliation Validation**
   - control.ctl_reconciliation has RC-1 result for each table
   - All RC-1 results show PASS (extract count = bronze count)
   - No FAIL results (or documented as known misses)

4. **Watermark Validation**
   - control.ctl_watermark updated for each table
   - watermark_value shows actual max watermark from extracted data
   - last_successful_batch_id = current batch_id
   - last_successful_run_ts updated
   - current_status = 'SUCCESS'

5. **Audit Log Validation**
   - control.audit_run_log has entries for batch start and end
   - Per-table entries for EXTRACT_, LOAD_, RECON_, WATERMARK_ events
   - All critical errors logged
   - Duration captured in BATCH_COMPLETED event

6. **Idempotency Validation**
   - Re-run same batch: select count(*) from bronze.br_orders WHERE dw_batch_id = X before and after
   - Count should be same (no duplicates)
   - Watermark should remain same (already advanced after first run)

# Expected Outputs

After successful execution, Antigravity will produce:

1. **Data in Bronze Layer**
   - 18 br_* tables populated with source data
   - Rows include technical columns: dw_batch_id, dw_ingest_date, dw_ingest_ts_utc, etc.
   - Source fidelity preserved: all source columns, values unchanged
   - No transformations applied

2. **Control Table Updates**
   - control.ctl_batch: 1 row, status=COMPLETED
   - control.ctl_watermark: 18 rows, all with watermark_value set
   - control.audit_source_extract: 18 rows, one per table
   - control.audit_run_log: 50+ rows with execution events

3. **Reconciliation Results**
   - control.ctl_reconciliation: 18 RC-1 rows, all PASS

4. **Row Counts** (Expected from source):
   - orders: 61,777
   - order_items: (derived from orders)
   - payments: 60,833
   - delivery_details: 60,533
   - customer: (count from source)
   - user_address: 31,855
   - restaurant: 370
   - menu_item: 7,298
   - delivery_partner: 2,555
   - cart: (count from source)
   - cart_items: (count from source)
   - reviews: 0
   - cuisines: 38
   - gender: 1
   - order_cancellation: 0
   - restaurant_cuisine: 0
   - restaurant_owner: 0
   - refunds: 0

# Completion Criteria

This skill is COMPLETE when:

1. ✅ All 18 source tables extracted successfully
2. ✅ All extracted rows loaded to Bronze (dw_batch_id set correctly)
3. ✅ All reconciliation checks pass (RC-1)
4. ✅ All watermarks advanced (control.ctl_watermark updated)
5. ✅ Batch status marked COMPLETED
6. ✅ No data errors that require manual intervention
7. ✅ Audit log complete and queryable
8. ✅ Source fidelity preserved (no transformations applied)
9. ✅ All technical columns present and populated
10. ✅ Idempotency validated (same batch can re-run safely)
11. ✅ Ready for handoff to bronze-to-gold-transformation skill

# Handoff to Other Skills

## Next Skill: bronze-to-gold-transformation

**When to Trigger**:
- After this skill completes successfully
- After all 18 Bronze tables populated
- After all reconciliation checks pass
- Before transformation and dimensional modeling begins

**What Must Be Available**:
- control.ctl_batch with status=COMPLETED
- control.ctl_watermark with all 18 tables' watermark values
- All 18 bronze.br_* tables populated with source data
- Silver and Gold schemas created (empty, ready for data)
- Reference data in silver.ref_* tables (status mappings, cohort rules)
- control.ctl_table_config with all table strategies

**Information to Pass**:
- Batch ID of completed ingestion
- Row counts per Bronze table
- Watermark values per table (for validation)
- Reconciliation results (all passing)
- Audit log link (table name: control.audit_run_log, batch_id: X)

**Handoff Communication**:
```
SKILL_COMPLETED: source-to-bronze-ingestion
NEXT_SKILL: bronze-to-gold-transformation
BATCH_ID: <completed_batch_id>
READINESS_CHECK: All Bronze data ingested and validated
BRONZE_STATISTICS:
- Orders: 61,777 rows
- Total rows ingested: 336,751
- Reconciliation: 18 tables passed RC-1
ACTION: Proceed to bronze-to-gold-transformation skill
```

# Prohibited Actions

Antigravity MUST NOT:

1. ❌ Modify source data or source system
2. ❌ Transform data before loading to Bronze (no cleansing, no business logic)
3. ❌ Hardcode table names in extraction logic (use ctl_table_config)
4. ❌ Advance watermarks if reconciliation fails
5. ❌ Load data to Silver or Gold layers (Bronze only)
6. ❌ Apply data quality flags in Bronze (that is Silver responsibility)
7. ❌ Skip reconciliation checks
8. ❌ Create new columns in Bronze that don't exist in source
9. ❌ Delete or update source system tables
10. ❌ Lock OLTP system during extraction (use read replica or off-peak window)
11. ❌ Hardcode credentials in code
12. ❌ Leave TODO or TBD placeholders in extraction logic
13. ❌ Re-extract rows from previous batches (watermark isolation)
14. ❌ Skip audit logging

# Final Response Format

After completing this skill, Antigravity must report:

## Summary
- Skill executed: source-to-bronze-ingestion
- Status: COMPLETED or FAILED
- Batch ID: <id>
- Execution time: <seconds>
- Execution date: <timestamp>

## Bronze Data Ingestion Results
- Tables extracted: 18
- Tables loaded successfully: 18 (or list failures)
- Total rows ingested: <count>
- Row counts by table: [list]
- Extractaction duration: <seconds>
- Load duration: <seconds>

## Reconciliation Results
- RC-1 checks: 18 passed
- Extract vs Bronze: all matched
- Reconciliation status: PASSED or FAILED

## Watermarks Advanced
- Tables with new watermarks: 18
- Initial load completed for: 18 tables
- Next run will use incremental strategy

## Audit Trail
- Batch record: control.ctl_batch ID <id>
- Manifest records: 18 rows in control.audit_source_extract
- Log entries: <count> rows in control.audit_run_log
- Reconciliation results: <count> rows in control.ctl_reconciliation

## Validation Results
- Schema drift detected: none or [list if found]
- Null value checks: <summary>
- Type validation: PASS
- Idempotency test: PASS (re-run successful)

## Issues and Warnings
- [Any issues encountered, with resolution]
- [Any data quality observations for downstream]

## Ready for Next Skill
- Bronze-to-Gold Transformation: READY

# Final Checklist

Antigravity must verify EVERY item before marking COMPLETE:

- ✅ Source connectivity verified and working
- ✅ All 18 source tables discovered
- ✅ control.ctl_table_config read successfully (18 rows)
- ✅ Batch created in control.ctl_batch
- ✅ For each table:
  - ✅ Extraction query built per strategy
  - ✅ Data extracted from source
  - ✅ Technical columns added (dw_batch_id, dw_ingest_date, etc.)
  - ✅ Data loaded to Bronze (br_* table)
  - ✅ Manifest created in audit_source_extract
  - ✅ Reconciliation check passed (extract count = load count)
  - ✅ Watermark advanced in control.ctl_watermark
- ✅ All 18 tables processed (successes and failures logged separately)
- ✅ Batch status updated to COMPLETED
- ✅ No data transformations applied
- ✅ Source fidelity preserved
- ✅ All audit logs created
- ✅ No hardcoded credentials
- ✅ No TODO/TBD placeholders
- ✅ Idempotency validated
- ✅ Ready for bronze-to-gold-transformation
