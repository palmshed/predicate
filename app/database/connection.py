import os
import time
import contextlib
from typing import List, Dict, Any, Optional, Tuple
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

_db_pool = None
_readonly_db_pool = None


def get_connection_pool():
    global _db_pool
    if _db_pool is None:
        try:
            _db_pool = pool.SimpleConnectionPool(
                minconn=1,
                maxconn=20,
                dsn=os.getenv("DATABASE_URL")
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize PostgreSQL connection pool: {str(e)}")
    return _db_pool


def get_readonly_connection_pool():
    global _readonly_db_pool
    if _readonly_db_pool is None:
        readonly_url = os.getenv("DATABASE_READONLY_URL")
        if readonly_url:
            try:
                _readonly_db_pool = pool.SimpleConnectionPool(
                    minconn=1,
                    maxconn=10,
                    dsn=readonly_url
                )
            except Exception:
                _readonly_db_pool = None
    return _readonly_db_pool


@contextlib.contextmanager
def get_db_cursor(readonly: bool = False):
    pool_to_use = get_readonly_connection_pool() if readonly else get_connection_pool()
    if pool_to_use is None:
        pool_to_use = get_connection_pool()

    connection = pool_to_use.getconn()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        if readonly:
            cursor.execute("SET statement_timeout = '30s'")
        yield cursor
        if readonly:
            connection.rollback()
        else:
            connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        pool_to_use.putconn(connection)


def execute_secure_query(
    sql_string: str,
    parameters: List[Any],
    timeout_seconds: Optional[int] = None
) -> Tuple[List[Dict[str, Any]], float]:
    """Execute parameterized query. Returns (results, db_query_ms)."""
    if not os.getenv("DATABASE_URL"):
        return ([{"mock_data_notice": "DATABASE_URL not configured. This is a simulated record response."}], 0)

    effective_timeout = timeout_seconds or int(os.getenv("QUERY_TIMEOUT_SECONDS", "30"))

    with get_db_cursor() as cursor:
        cursor.execute(f"SET statement_timeout = '{effective_timeout}s'")
        query_start = time.perf_counter()
        cursor.execute(sql_string, parameters)
        if cursor.description:
            results = cursor.fetchall()
        else:
            results = []
        db_ms = round((time.perf_counter() - query_start) * 1000, 2)
        return results, db_ms
