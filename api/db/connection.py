import threading
from contextlib import contextmanager

from psycopg2.pool import ThreadedConnectionPool

from config import SUPABASE_DB_URL

_pool: ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()

DEFAULT_STATEMENT_TIMEOUT_MS = 5000


def _get_pool() -> ThreadedConnectionPool:
    """Lazy pool initialization — created on first call, not at import time."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = ThreadedConnectionPool(minconn=1, maxconn=10, dsn=SUPABASE_DB_URL)
    return _pool


def close_pool() -> None:
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None


@contextmanager
def get_db():
    """Yield a connection from the pool; return it on exit."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def execute_query(
    sql: str,
    params: tuple | None = None,
    statement_timeout_ms: int = DEFAULT_STATEMENT_TIMEOUT_MS,
) -> tuple[list[str], list[tuple]]:
    """Execute a read query with statement timeout. Returns (columns, rows).

    Note: SET LOCAL requires a transaction block. psycopg2 defaults to
    autocommit=False (implicit transaction), so SET LOCAL + query share
    the same transaction. Do NOT set autocommit=True on pool connections.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = %s", (statement_timeout_ms,))
            cur.execute(sql, params)
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = cur.fetchall()
        conn.commit()
    return columns, rows
