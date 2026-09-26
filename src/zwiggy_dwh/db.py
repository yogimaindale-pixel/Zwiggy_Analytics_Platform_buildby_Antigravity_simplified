"""Database connectivity, context management, and query helpers.

Supports SQLite, DuckDB, and PostgreSQL backends with uniform execution,
retries, and cursor wrappers.
"""

from contextlib import contextmanager
import functools
import logging
import sqlite3
import time
from typing import Any, Callable, Dict, List, Optional, TypeVar

from zwiggy_dwh.config import DbTarget, get_settings

logger = logging.getLogger(__name__)

F = TypeVar('F', bound=Callable[..., Any])


class DatabaseError(Exception):
    """Base exception for database errors."""
    pass


class DictCursorWrapper:
    """Wraps DB-API cursor to return dictionary rows."""

    def __init__(self, cursor: Any, engine: str) -> None:
        self.cursor = cursor
        self.engine = engine

    def execute(self, sql: str, params: Optional[Any] = None) -> Any:
        sql_adapted = self._adapt_sql(sql)
        if params is None:
            return self.cursor.execute(sql_adapted)
        return self.cursor.execute(sql_adapted, params)

    def executemany(self, sql: str, seq_of_params: Any) -> Any:
        sql_adapted = self._adapt_sql(sql)
        return self.cursor.executemany(sql_adapted, seq_of_params)

    def _adapt_sql(self, sql: str) -> str:
        if self.engine in ('sqlite', 'duckdb'):
            # Convert %s placeholder to ? if needed
            return sql.replace('%s', '?')
        return sql

    def fetchone(self) -> Optional[Dict[str, Any]]:
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
        return getattr(self.cursor, name)


class ConnectionWrapper:
    """Connection wrapper ensuring consistent schema / table handling across engines."""

    def __init__(self, raw_conn: Any, engine: str) -> None:
        self.raw_conn = raw_conn
        self.engine = engine

    def cursor(self) -> DictCursorWrapper:
        if self.engine == 'sqlite':
            self.raw_conn.row_factory = sqlite3.Row
            return DictCursorWrapper(self.raw_conn.cursor(), self.engine)
        elif self.engine == 'postgres':
            import psycopg2.extras
            return DictCursorWrapper(self.raw_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor), self.engine)
        else: # duckdb
            return DictCursorWrapper(self.raw_conn.cursor(), self.engine)

    def commit(self) -> None:
        if hasattr(self.raw_conn, 'commit'):
            self.raw_conn.commit()

    def rollback(self) -> None:
        if hasattr(self.raw_conn, 'rollback'):
            self.raw_conn.rollback()

    def close(self) -> None:
        if hasattr(self.raw_conn, 'close'):
            self.raw_conn.close()

    def __enter__(self) -> 'ConnectionWrapper':
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
        self.close()


def connect(target: Optional[DbTarget] = None) -> ConnectionWrapper:
    """Establish connection to database target."""
    t = target or get_settings().target
    try:
        if t.engine == 'sqlite':
            raw_conn = sqlite3.connect(t.db_path, timeout=60.0)
            # Enable foreign keys and set busy timeout
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
    """Decorator to retry DB operations on transient errors."""
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
    """Execute SQL query and return dict results if any."""
    cur = conn.cursor()
    cur.execute(sql, params)
    try:
        return cur.fetchall()
    except Exception:
        return []


def query_scalar(conn: ConnectionWrapper, sql: str, params: Optional[Any] = None) -> Any:
    """Execute SQL query and return scalar value."""
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    if row:
        return list(row.values())[0]
    return None
