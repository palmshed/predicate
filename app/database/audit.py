import json
from typing import List, Any, Optional
from app.database.connection import get_db_cursor
from app.observability.logging import get_logger

logger = get_logger("audit")


def sink_compliance_audit_log(
    tenant_id: str,
    user_prompt: str,
    compiled_sql: str,
    parameters: List[Any],
    cache_hit: bool,
    request_id: Optional[str] = None,
    compile_ms: Optional[float] = None,
    validate_ms: Optional[float] = None,
    execute_ms: Optional[float] = None,
    rows_returned: Optional[int] = None,
    target_table: Optional[str] = None,
    error_code: Optional[str] = None,
) -> None:
    sql_insert = """
        INSERT INTO audit_logs
            (tenant_id, user_prompt, compiled_sql, execution_parameters,
             cache_hit, request_id, compile_ms, validate_ms, execute_ms,
             rows_returned, target_table, error_code)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
    """

    try:
        serialized_params = json.dumps(parameters)

        with get_db_cursor() as cursor:
            cursor.execute(sql_insert, (
                tenant_id, user_prompt, compiled_sql, serialized_params,
                cache_hit, request_id, compile_ms, validate_ms, execute_ms,
                rows_returned, target_table, error_code,
            ))

        logger.info(
            "audit_logged",
            extra={
                "tenant_id": tenant_id,
                "request_id": request_id,
                "cache_hit": cache_hit,
                "rows": rows_returned,
                "target_table": target_table,
            }
        )
    except Exception:
        logger.warning("audit_sink_failed", extra={"request_id": request_id})
