import json
from typing import List, Any
from app.database.connection import get_db_cursor


def sink_compliance_audit_log(
    tenant_id: str,
    user_prompt: str,
    compiled_sql: str,
    parameters: List[Any],
    cache_hit: bool
) -> None:
    sql_insert = """
        INSERT INTO audit_logs (tenant_id, user_prompt, compiled_sql, execution_parameters, cache_hit)
        VALUES (%s, %s, %s, %s, %s);
    """

    try:
        serialized_params = json.dumps(parameters)

        with get_db_cursor() as cursor:
            cursor.execute(sql_insert, (tenant_id, user_prompt, compiled_sql, serialized_params, cache_hit))
    except Exception:
        pass