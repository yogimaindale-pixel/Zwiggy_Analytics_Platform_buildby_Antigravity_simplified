# ==============================================================================
# ZWIGGY ANALYTICS PLATFORM - DATABASE CONNECTIVITY & QUERY HELPERS
# ==============================================================================
# File: src/zwiggy_dwh/db.py
# Purpose: Unified database abstraction supporting SQLite, DuckDB, and PostgreSQL.
#          Provides dict cursor wrappers, connection retries, and scalar helpers.
# ==============================================================================

# Import context manager utilities.
from contextlib import contextmanager

# Import functools for decorator preservation.
import functools

# Import standard logging module.
import logging

# Import sqlite3 database library.
import sqlite3

# Import time module for retry backoff sleeps.
import time

# Import typing generics.
from typing import Any, Callable, Dict, List, Optional, TypeVar

# Import configuration settings and target classes.
from zwiggy_dwh.config import DbTarget, get_settings

# Create module-level logger.
logger = logging.getLogger(__name__)

# Type variable for decorator function binding.
F = TypeVar('F', bound=Callable[..., Any])


# ------------------------------------------------------------------------------
# DATABASE EXCEPTION DEFINITION
# ------------------------------------------------------------------------------

class DatabaseError(Exception):
    """Base custom exception class for database operations."""
    pass


# ------------------------------------------------------------------------------
# DICTIONARY CURSOR WRAPPER CLASS
# ------------------------------------------------------------------------------

class DictCursorWrapper:
    """
    Wraps DB-API cursor objects to ensure all rows are returned as dictionary objects.
    """

    def __init__(self, cursor: Any, engine: str) -> None:
        """Constructor receiving raw DB cursor and engine identifier."""
        self.cursor = cursor
        self.engine = engine

    def execute(self, sql: str, params: Optional[Any] = None) -> Any:
        """Executes a single SQL query adapting placeholder syntax."""
        sql_adapted = self._adapt_sql(sql)
        if params is None:
            return self.cursor.execute(sql_adapted)
        return self.cursor.execute(sql_adapted, params)

    def executemany(self, sql: str, seq_of_params: Any) -> Any:
        """Executes batch SQL insert/update statements."""
        sql_adapted = self._adapt_sql(sql)
        return self.cursor.executemany(sql_adapted, seq_of_params)

    def _adapt_sql(self, sql: str) -> str:
        """Adapts SQL syntax between SQLite (?) and PostgreSQL (%s) parameter formats."""
        if self.engine in ('sqlite', 'duckdb'):
            return sql.replace('%s', '?')
        return sql

    def fetchone(self) -> Optional[Dict[str, Any]]:
        """Fetches a single row as a key-value dictionary."""
        row = self.cursor.fetchone()
        if row is None:
            return None
        if isinstance(row, dict):
            return row
        if hasattr(self.cursor, 'description') and self.cursor.description:
            cols = [col[0] for col in self.cursor.description]
            return dict(zip(cols, row))
        return dict(row)

    def fetchall(self) -> List[Dict[str, Any]]:
        """Fetches all result rows as a list of dictionaries."""
        rows = self.cursor.fetchall()
        if not rows:
            return []
        if isinstance(rows[0], dict):
            return rows
        if hasattr(self.cursor, 'description') and self.cursor.description:
            cols = [col[0] for col in self.cursor.description]
            return [dict(zip(cols, r)) for r in rows]
        return [dict(r) for r in rows]

    def __getattr__(self, name: str) -> Any:
        """Delegates unhandled method calls directly to underlying cursor."""
        return getattr(self.cursor, name)


# ------------------------------------------------------------------------------
# CONNECTION WRAPPER CLASS
# ------------------------------------------------------------------------------

class ConnectionWrapper:
    """
    Unified database connection wrapper supporting context management and auto-commit/rollback.
    """

    def __init__(self, raw_conn: Any, engine: str) -> None:
        """Constructor storing raw connection and engine type."""
        self.raw_conn = raw_conn
        self.engine = engine

    def cursor(self) -> DictCursorWrapper:
        """Returns a DictCursorWrapper instance configured for the active engine."""
        if self.engine == 'sqlite':
            self.raw_conn.row_factory = sqlite3.Row
            return DictCursorWrapper(self.raw_conn.cursor(), self.engine)
        elif self.engine == 'postgres':
            import psycopg2.extras
            return DictCursorWrapper(self.raw_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor), self.engine)
        else:
            return DictCursorWrapper(self.raw_conn.cursor(), self.engine)

    def commit(self) -> None:
        """Commits current transaction."""
        if hasattr(self.raw_conn, 'commit'):
            self.raw_conn.commit()

    def rollback(self) -> None:
        """Rolls back current transaction on error."""
        if hasattr(self.raw_conn, 'rollback'):
            self.raw_conn.rollback()

    def close(self) -> None:
        """Closes active database connection."""
        if hasattr(self.raw_conn, 'close'):
            self.raw_conn.close()

    def __enter__(self) -> 'ConnectionWrapper':
        """Context manager entry point."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit point handling auto-commit or rollback."""
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
        self.close()


# ------------------------------------------------------------------------------
# HELPER FUNCTIONS & DECORATORS
# ------------------------------------------------------------------------------

def connect(target: Optional[DbTarget] = None) -> ConnectionWrapper:
    """
    Establishes connection to specified or configured database target.
    
    Args:
        target (Optional[DbTarget]): Target configuration settings instance.
        
    Returns:
        ConnectionWrapper: Wrapped database connection object.
    """
    t = target or get_settings().target
    try:
        if t.engine == 'sqlite':
            raw_conn = sqlite3.connect(t.db_path, timeout=60.0)
            raw_conn.execute("PRAGMA foreign_keys = ON;")
            raw_conn.execute("PRAGMA busy_timeout = 60000;")
            return ConnectionWrapper(raw_conn, 'sqlite')
        elif t.engine == 'duckdb':
            import duckdb
            raw_conn = duckdb.connect(t.db_path)
            return ConnectionWrapper(raw_conn, 'duckdb')
        elif t.engine == 'postgres':
            import psycopg2
            raw_conn = psycopg2.connect(
                host=t.host,
                port=t.port,
                dbname=t.dbname,
                user=t.user,
                password=t.password,
                connect_timeout=10
            )
            return ConnectionWrapper(raw_conn, 'postgres')
        else:
            raise DatabaseError(f"Unsupported database engine: {t.engine}")
    except Exception as e:
        logger.error("Failed to connect to database %s: %s", t.masked_repr(), e)
        raise DatabaseError(f"Database connection error: {e}") from e


def with_retry(max_retries: int = 3, backoff_seconds: float = 1.0) -> Callable[[F], F]:
    """
    Decorator executing function retries with exponential backoff on transient errors.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_err = None
            delay = backoff_seconds
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_err = e
                    if attempt == max_retries:
                        logger.error("Operation failed after %d retries: %s", max_retries, e)
                        raise
                    logger.warning("DB error on attempt %d/%d (%s). Retrying in %.1fs...", attempt, max_retries, e, delay)
                    time.sleep(delay)
                    delay *= 2.0
            raise last_err  # type: ignore
        return wrapper  # type: ignore
    return decorator


def execute_sql(conn: ConnectionWrapper, sql: str, params: Optional[Any] = None) -> List[Dict[str, Any]]:
    """
    Executes a SQL query and returns list of dictionary result rows.
    """
    cur = conn.cursor()
    cur.execute(sql, params)
    try:
        return cur.fetchall()
    except Exception:
        return []


def query_scalar(conn: ConnectionWrapper, sql: str, params: Optional[Any] = None) -> Any:
    """
    Executes a SQL query and returns single scalar value result.
    """
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    if row:
        return list(row.values())[0]
    return None
