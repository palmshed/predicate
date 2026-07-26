import json
from typing import Any

from app.database.connection import get_db_cursor
from app.observability.logging import get_logger

logger = get_logger("audit")


def sink_compliance_audit_log(
    tenant_id: str,
    user_prompt: str,
    compiled_sql: str,
    parameters: list[Any],
    cache_hit: bool,
    request_id: str | None = None,
    compile_ms: float | None = None,
    validate_ms: float | None = None,
    execute_ms: float | None = None,
    rows_returned: int | None = None,
    target_table: str | None = None,
    error_code: str | None = None,
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
            cursor.execute(
                sql_insert,
                (
                    tenant_id,
                    user_prompt,
                    compiled_sql,
                    serialized_params,
                    cache_hit,
                    request_id,
                    compile_ms,
                    validate_ms,
                    execute_ms,
                    rows_returned,
                    target_table,
                    error_code,
                ),
            )

        logger.info(
            "audit_logged",
            extra={
                "tenant_id": tenant_id,
                "request_id": request_id,
                "cache_hit": cache_hit,
                "rows": rows_returned,
                "target_table": target_table,
            },
        )
    except Exception:
        logger.warning("audit_sink_failed", extra={"request_id": request_id})
