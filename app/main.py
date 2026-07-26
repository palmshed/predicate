import os
import resource
import time
from datetime import UTC, datetime

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field

load_dotenv()

from app.observability import PrometheusExporter, TraceContext, get_logger, metrics, setup_logging
from app.observability.logging import request_id_var, tenant_id_var

setup_logging()
logger = get_logger("main")

from celery.result import AsyncResult

from app.agent.services import AgentService
from app.auth.rate_limiter import TIER_LIMITS, check_rate_limit
from app.compiler.sql_builder import build_secure_query
from app.database.audit import sink_compliance_audit_log
from app.database.cache import get_cached_results, get_redis_client, set_cached_results
from app.database.connection import (
    execute_secure_query,
    get_connection_pool,
)
from app.database.metrics import get_tenant_metrics, record_tenant_metric
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.security import CSRFMiddleware, SecurityHeadersMiddleware
from app.worker import execute_heavy_export_task

MAX_PROMPT_LENGTH = int(os.getenv("MAX_PROMPT_LENGTH", "2000"))
QUERY_TIMEOUT_SECONDS = int(os.getenv("QUERY_TIMEOUT_SECONDS", "30"))
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
GIT_COMMIT = os.getenv("GIT_COMMIT", "unknown")
BUILD_DATE = os.getenv("BUILD_DATE", datetime.now(UTC).isoformat())

app = FastAPI(
    title="Predicate AI Engine",
    description="Secure Natural Language to SQL Compilation Platform",
    version=APP_VERSION,
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware, secret_key=os.getenv("CSRF_SECRET_KEY", os.urandom(32).hex()))

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",")
ALLOWED_ORIGINS = [o.strip() for o in ALLOWED_ORIGINS if o.strip()]
if not ALLOWED_ORIGINS:
    ALLOWED_ORIGINS = ["http://localhost:8000", "http://127.0.0.1:8000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Predicate-API-Key", "X-CSRF-Token", "X-Request-ID"],
)

_start_time = time.time()


class QueryRequest(BaseModel):
    prompt: str = Field(
        ...,
        max_length=MAX_PROMPT_LENGTH,
        description="The plain natural language question from the user.",
        json_schema_extra={"example": "Show me the top 5 orders over 200 dollars."},
    )


class QueryResponse(BaseModel):
    status: str
    request_id: str
    compiled_sql: str
    parameters: list
    cache_hit: bool
    results: list
    agent_blueprint: dict
    trace: dict


agent_service = None


def get_agent_service():
    global agent_service
    if agent_service is None:
        agent_service = AgentService()
    return agent_service


def _get_process_stats() -> dict:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    rss_mb = round(usage.ru_maxrss / 1024, 1)
    uptime_s = round(time.time() - _start_time, 0)
    return {
        "uptime_seconds": uptime_s,
        "memory_rss_mb": rss_mb,
        "pid": os.getpid(),
    }


@app.get("/", response_class=HTMLResponse)
async def serve_workspace_interface():
    static_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(static_path):
        with open(static_path) as file:
            return HTMLResponse(content=file.read(), status_code=200)
    return HTMLResponse(content="<h1>Interface file missing.</h1>", status_code=404)


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    provider = os.getenv("LLM_PROVIDER", "openai")
    if provider == "openrouter":
        key_configured = bool(os.getenv("OPENROUTER_API_KEY"))
    else:
        key_configured = bool(os.getenv("OPENAI_API_KEY"))
    return {
        "status": "healthy",
        "version": APP_VERSION,
        "git_commit": GIT_COMMIT,
        "build_date": BUILD_DATE,
        "llm_provider": provider,
        "llm_key_configured": key_configured,
        **_get_process_stats(),
    }


@app.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check():
    checks = {"db": False, "redis": False}

    try:
        pool = get_connection_pool()
        if pool:
            conn = pool.getconn()
            try:
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.close()
                checks["db"] = True
            finally:
                pool.putconn(conn)
    except Exception:
        pass

    try:
        client = get_redis_client()
        if client and client.ping():
            checks["redis"] = True
    except Exception:
        pass

    all_ok = all(checks.values())
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
        **_get_process_stats(),
    }


@app.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    exporter = PrometheusExporter(metrics)
    return PlainTextResponse(content=exporter.export(), media_type="text/plain")


@app.post("/api/v1/query/compile", response_model=QueryResponse, status_code=status.HTTP_200_OK)
async def compile_natural_language_query(
    payload: QueryRequest, tenant_context: dict = Depends(check_rate_limit)
):
    req_id = request_id_var.get() or "unknown"
    tid = tenant_context["tenant_id"]
    tenant_id_var.set(tid)

    provider = os.getenv("LLM_PROVIDER", "openai")

    trace = TraceContext(request_id=req_id, tenant_id=tid)
    metrics.inc("requests_total")
    metrics.inc("active_executions")
    metrics.inc(f'requests_by_provider_total{{provider="{provider}"}}')

    compile_duration = None
    validate_duration = None
    db_query_duration = None

    prompt = payload.prompt.strip()
    if not prompt:
        metrics.inc("validation_failures")
        metrics.dec("active_executions")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="The prompt string cannot be empty."
        )

    try:
        svc = get_agent_service()

        with trace.span("compile"):
            blueprint_object = svc.translate_text_to_blueprint(prompt)
            blueprint_dict = blueprint_object.model_dump()

        compile_duration = trace.spans[-1]["ms"] if trace.spans else 0
        metrics.observe("compile_duration_milliseconds", compile_duration)
        metrics.observe(
            f'compile_duration_by_provider_milliseconds{{provider="{provider}"}}', compile_duration
        )

        with trace.span("validate"):
            sql_string, query_parameters = build_secure_query(blueprint_dict, tenant_id=tid)
        validate_duration = trace.spans[-1]["ms"] if trace.spans else 0
        metrics.observe("validate_duration_milliseconds", validate_duration)

        with trace.span("cache_lookup"):
            cached_records = get_cached_results(sql_string, query_parameters)

        if cached_records is not None:
            metrics.inc("cache_hits")
            metrics.inc("queries_completed")
            record_tenant_metric(
                tid, is_cache_hit=True, target_table=blueprint_dict["target_table"]
            )

            sink_compliance_audit_log(
                tenant_id=tid,
                user_prompt=prompt,
                compiled_sql=sql_string,
                parameters=query_parameters,
                cache_hit=True,
                request_id=req_id,
                compile_ms=compile_duration,
                validate_ms=validate_duration,
                execute_ms=0,
                rows_returned=len(cached_records),
                target_table=blueprint_dict["target_table"],
            )

            logger.info(
                "query_completed",
                extra={
                    "route": "/api/v1/query/compile",
                    "cache_hit": True,
                    "rows": len(cached_records),
                    "target_table": blueprint_dict["target_table"],
                    "compile_ms": compile_duration,
                    "validate_ms": validate_duration,
                },
            )

            return QueryResponse(
                status="success",
                request_id=req_id,
                compiled_sql=sql_string,
                parameters=query_parameters,
                cache_hit=True,
                results=cached_records,
                agent_blueprint=blueprint_dict,
                trace=trace.to_dict(),
            )

        metrics.inc("cache_misses")

        with trace.span("execute"):
            db_results, db_query_duration = execute_secure_query(
                sql_string, query_parameters, timeout_seconds=QUERY_TIMEOUT_SECONDS
            )
        execute_duration = trace.spans[-1]["ms"] if trace.spans else 0
        metrics.observe("execute_duration_milliseconds", execute_duration)
        metrics.observe("db_query_duration_milliseconds", db_query_duration)

        set_cached_results(sql_string, query_parameters, db_results, ttl_seconds=300)

        metrics.inc("queries_completed")
        record_tenant_metric(tid, is_cache_hit=False, target_table=blueprint_dict["target_table"])

        sink_compliance_audit_log(
            tenant_id=tid,
            user_prompt=prompt,
            compiled_sql=sql_string,
            parameters=query_parameters,
            cache_hit=False,
            request_id=req_id,
            compile_ms=compile_duration,
            validate_ms=validate_duration,
            execute_ms=execute_duration,
            rows_returned=len(db_results),
            target_table=blueprint_dict["target_table"],
        )

        logger.info(
            "query_completed",
            extra={
                "route": "/api/v1/query/compile",
                "cache_hit": False,
                "rows": len(db_results),
                "target_table": blueprint_dict["target_table"],
                "compile_ms": compile_duration,
                "validate_ms": validate_duration,
                "execute_ms": execute_duration,
                "db_query_ms": db_query_duration,
                "duration_ms": trace.total_ms,
            },
        )

        return QueryResponse(
            status="success",
            request_id=req_id,
            compiled_sql=sql_string,
            parameters=query_parameters,
            cache_hit=False,
            results=db_results,
            agent_blueprint=blueprint_dict,
            trace=trace.to_dict(),
        )

    except ValueError as ve:
        metrics.inc("validation_failures")
        metrics.inc(f'errors_by_provider_total{{provider="{provider}"}}')
        logger.warning(
            "query_validation_failed",
            extra={"route": "/api/v1/query/compile", "error_code": "VALIDATION_ERROR"},
        )
        sink_compliance_audit_log(
            tenant_id=tid,
            user_prompt=prompt,
            compiled_sql="",
            parameters=[],
            cache_hit=False,
            request_id=req_id,
            compile_ms=compile_duration,
            error_code="VALIDATION_ERROR",
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve),
        ) from ve
    except Exception:
        metrics.inc("query_failures")
        metrics.inc(f'errors_by_provider_total{{provider="{provider}"}}')
        logger.error(
            "query_failed", extra={"route": "/api/v1/query/compile", "error_code": "INTERNAL_ERROR"}
        )
        sink_compliance_audit_log(
            tenant_id=tid,
            user_prompt=prompt,
            compiled_sql="",
            parameters=[],
            cache_hit=False,
            request_id=req_id,
            error_code="INTERNAL_ERROR",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while compiling your request.",
        ) from None
    finally:
        metrics.dec("active_executions")


@app.get("/api/v1/metrics", status_code=status.HTTP_200_OK)
async def get_live_tenant_analytics(tenant_context: dict = Depends(check_rate_limit)):
    plan = tenant_context["plan"]
    limit_ceiling = TIER_LIMITS.get(plan, 20)
    analytics_payload = get_tenant_metrics(tenant_context["tenant_id"], limit_ceiling)
    return analytics_payload


@app.post("/api/v1/export/async", status_code=status.HTTP_202_ACCEPTED)
async def trigger_bulk_data_export(
    payload: QueryRequest, tenant_context: dict = Depends(check_rate_limit)
):
    req_id = request_id_var.get() or "unknown"
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="The prompt string cannot be empty.")

    svc = get_agent_service()
    blueprint_object = svc.translate_text_to_blueprint(prompt)
    blueprint_dict = blueprint_object.model_dump()

    metrics.inc("exports_total")

    task = execute_heavy_export_task.delay(blueprint_dict, tenant_context["tenant_id"])  # type: ignore[union-attr]

    logger.info("export_queued", extra={"route": "/api/v1/export/async", "request_id": req_id})

    return {"status": "queued", "task_id": task.id, "poll_url": f"/api/v1/export/status/{task.id}"}


@app.get("/api/v1/export/status/{task_id}", status_code=status.HTTP_200_OK)
async def check_bulk_export_status(task_id: str, tenant_context: dict = Depends(check_rate_limit)):
    task_result = AsyncResult(task_id, app=execute_heavy_export_task.app)  # type: ignore[union-attr]

    response_payload = {"task_id": task_id, "state": task_result.state}

    if task_result.state == "PROCESSING":
        response_payload["meta"] = task_result.info
    elif task_result.state == "SUCCESS":
        response_payload["result"] = task_result.result
    elif task_result.state == "FAILURE":
        response_payload["error"] = "Export task failed."

    return response_payload
