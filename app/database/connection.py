import os
import contextlib
from typing import List, Dict, Any
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

_db_pool = None


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


@contextlib.contextmanager
def get_db_cursor():
    db_pool = get_connection_pool()
    connection = db_pool.getconn()
    try:
        yield connection.cursor(cursor_factory=RealDictCursor)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        db_pool.putconn(connection)


def execute_secure_query(sql_string: str, parameters: List[Any]) -> List[Dict[str, Any]]:
    if not os.getenv("DATABASE_URL"):
        return [{"mock_data_notice": "DATABASE_URL not configured. This is a simulated record response."}]

    with get_db_cursor() as cursor:
        cursor.execute(sql_string, parameters)
        if cursor.description:
            return cursor.fetchall()
        return []