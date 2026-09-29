# 📄 Line-by-Line Code Breakdown: `src/zwiggy_dwh/db.py`

**File Name**: `src/zwiggy_dwh/db.py`  
**Total Lines**: 249 Lines  
**Primary Purpose**: Database resilience, transaction safety, and query connection manager. Contains `ConnectionWrapper` (context manager enforcing auto-commit and rollback), `DictCursorWrapper` (converting tuple rows to key-value dictionaries), `with_retry()` (exponential backoff decorator), and helper functions `execute_sql()` and `query_scalar()`.

---

## 📜 Detailed Line-by-Line Walkthrough

* **Lines 1–35**: Header docstring and imports (`sqlite3`, `time`, `logging`, `functools.wraps`, `typing`).
* **Line 41**: `class DatabaseError(Exception):` - Custom base exception for all database and SQL execution errors.
* **Line 50**: `class DictCursorWrapper:` - Cursor wrapper class converting standard SQL tuple results into Python dictionaries.
* **Line 55**: `    def __init__(self, cursor: sqlite3.Cursor):` - Wrapper constructor receiving an underlying `sqlite3.Cursor`.
* **Line 56**: `        self._cursor = cursor` - Stores cursor instance internally.
* **Line 60**: `    def execute(self, sql: str, params: tuple = ()) -> "DictCursorWrapper":` - Executes SQL query with parameters.
* **Line 61**: `        adapted_sql = self._adapt_sql(sql)` - Adapts PostgreSQL style `%s` placeholders to SQLite `?` placeholders.
* **Line 62**: `        self._cursor.execute(adapted_sql, params)` - Delegates execution to underlying SQLite cursor.
* **Line 63**: `        return self` - Returns self to allow method chaining.
* **Line 67**: `    def executemany(self, sql: str, seq_of_params: list) -> "DictCursorWrapper":` - Executes batch SQL inserts.
* **Line 72**: `    def _adapt_sql(self, sql: str) -> str:` - Helper replacing `%s` placeholder markers with `?`.
* **Line 78**: `    def fetchone(self) -> Optional[dict]:` - Fetches single query result row as a dictionary.
* **Line 79**: `        row = self._cursor.fetchone()` - Retrieves row tuple from cursor.
* **Line 80**: `        if row is None:` - Checks if query returned zero rows.
* **Line 81**: `            return None` - Returns `None`.
* **Line 82**: `        cols = [desc[0] for desc in self._cursor.description]` - Extracts column names from cursor description metadata.
* **Line 83**: `        return dict(zip(cols, row))` - Combines column names and row values into a Python dictionary.
* **Line 90**: `    def fetchall(self) -> list[dict]:` - Fetches all matching result rows as a list of dictionaries.
* **Line 91**: `        rows = self._cursor.fetchall()` - Retrieves all row tuples.
* **Line 92**: `        if not rows:` - Checks if result set is empty.
* **Line 93**: `            return []` - Returns empty list.
* **Line 94**: `        cols = [desc[0] for desc in self._cursor.description]` - Extracts column names.
* **Line 95**: `        return [dict(zip(cols, r)) for r in rows]` - Converts every row tuple to a dictionary.
* **Line 111**: `class ConnectionWrapper:` - Connection wrapper managing transaction lifecycles cleanly.
* **Line 116**: `    def __init__(self, conn: sqlite3.Connection):` - Wrapper constructor receiving active SQLite connection.
* **Line 117**: `        self._conn = conn` - Stores connection object internally.
* **Line 121**: `    def cursor(self) -> DictCursorWrapper:` - Creates and returns a new `DictCursorWrapper` instance.
* **Line 132**: `    def commit(self):` - Flushes transaction changes to disk.
* **Line 137**: `    def rollback(self):` - Reverts all uncommitted mutations in case of error.
* **Line 142**: `    def close(self):` - Closes underlying database connection.
* **Line 147**: `    def __enter__(self) -> "ConnectionWrapper":` - Context manager entry point (`with connect() as conn:`).
* **Line 148**: `        return self` - Returns connection wrapper instance.
* **Line 151**: `    def __exit__(self, exc_type, exc_val, exc_tb):` - Context manager exit point enforcing transaction boundaries.
* **Line 152**: `        if exc_type is not None:` - Checks if an exception occurred within the `with` block.
* **Line 153**: `            self.rollback()` - Rollbacks transaction automatically to preserve database integrity.
* **Line 154**: `            logger.error(f"Transaction rolled back due to error: {exc_val}")` - Logs error traceback.
* **Line 155**: `        else:` - Execution succeeded cleanly without exceptions.
* **Line 156**: `            self.commit()` - Commits transaction automatically to persist data.
* **Line 164**: `def connect(db_path: Optional[Path] = None) -> ConnectionWrapper:` - Helper function establishing SQLite database connection.
* **Line 203**: `def with_retry(max_retries: int = 3, backoff_factor: float = 1.5):` - Higher-order decorator function for retry resilience.
* **Line 204**: `    def decorator(func):` - Decorator wrapper receiving target function.
* **Line 205**: `        @wraps(func)` - Preserves function name and docstrings.
* **Line 206**: `        def wrapper(*args, **kwargs):` - Inner wrapper function executing target function.
* **Line 207**: `            retries = 0` - Initializes retry counter.
* **Line 208**: `            while True:` - Retry loop.
* **Line 209**: `                try:` - Attempt block.
* **Line 210**: `                    return func(*args, **kwargs)` - Executes target function and returns result on success.
* **Line 211**: `                except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:` - Catches transient DB errors.
* **Line 212**: `                    retries += 1` - Increments retry counter.
* **Line 213**: `                    if retries > max_retries:` - Checks if retry threshold exceeded.
* **Line 214**: `                        raise DatabaseError(f"Function {func.__name__} failed after {max_retries} retries: {e}")` - Raises error.
* **Line 215**: `                    sleep_time = backoff_factor ** retries` - Computes exponential backoff sleep delay (e.g., $1.5^1 = 1.5s, 1.5^2 = 2.25s$).
* **Line 216**: `                    logger.warning(f"Retry {retries}/{max_retries} for {func.__name__} after {sleep_time:.2f}s due to: {e}")` - Logs warning.
* **Line 217**: `                    time.sleep(sleep_time)` - Pauses execution thread before retrying.
* **Line 228**: `def execute_sql(conn: ConnectionWrapper, sql: str, params: tuple = ()) -> int:` - Helper executing statement and returning affected row count.
* **Line 240**: `def query_scalar(conn: ConnectionWrapper, sql: str, params: tuple = ()):` - Helper returning a single scalar value (e.g. `SELECT COUNT(*)`).
