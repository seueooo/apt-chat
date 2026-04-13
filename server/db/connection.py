from contextlib import contextmanager

from psycopg import sql as psql
from psycopg_pool import ConnectionPool

from config import settings

_pool: ConnectionPool | None = None

DEFAULT_STATEMENT_TIMEOUT_MS = 5000


def _get_pool() -> ConnectionPool:
    """Lazy pool initialization — created on first call, not at import time."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=settings.supabase_db_url,
            min_size=1,
            max_size=10,
            open=True,
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def get_db():
    """Yield a connection from the pool; return it on exit."""
    pool = _get_pool()
    with pool.connection() as conn:
        yield conn


def execute_query(
    sql: str,
    params: tuple | None = None,
    statement_timeout_ms: int = DEFAULT_STATEMENT_TIMEOUT_MS,
) -> tuple[list[str], list[tuple]]:
    """Execute a read query with statement timeout. Returns (columns, rows).

    Note: SET LOCAL requires a transaction block. psycopg defaults to
    autocommit=False (transaction block mode), so SET LOCAL + query share
    the same transaction. Do NOT set autocommit=True on pool connections.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            timeout_sql = psql.SQL("SET LOCAL statement_timeout = {}").format(
                psql.Literal(statement_timeout_ms)
            )
            cur.execute(timeout_sql)
            cur.execute(sql, params)
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = cur.fetchall()
        conn.commit()
    return columns, rows
