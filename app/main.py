import os
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from app.agent.services import AgentService
from app.compiler.sql_builder import build_secure_query
from app.database.connection import execute_secure_query
from app.database.cache import get_cached_results, set_cached_results
from app.auth.security import validate_api_key
from app.auth.rate_limiter import check_rate_limit, TIER_LIMITS
from app.database.metrics import record_tenant_metric, get_tenant_metrics
from app.database.audit import sink_compliance_audit_log
from app.worker import execute_heavy_export_task
from celery.result import AsyncResult

load_dotenv()

app = FastAPI(
    title="Predicate AI Engine",
    description="Secure Natural Language to SQL Compilation Platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    prompt: str = Field(..., description="The plain natural language question from the user.", json_schema_extra={"example": "Show me the top 5 orders over 200 dollars."})


class QueryResponse(BaseModel):
    status: str
    compiled_sql: str
    parameters: list
    cache_hit: bool
    results: list
    agent_blueprint: dict


agent_service = None


def get_agent_service():
    global agent_service
    if agent_service is None:
        agent_service = AgentService()
    return agent_service


@app.get("/", response_class=HTMLResponse)
async def serve_workspace_interface():
    static_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(static_path):
        with open(static_path, "r") as file:
            return HTMLResponse(content=file.read(), status_code=200)
    return HTMLResponse(content="<h1>Interface file missing.</h1>", status_code=404)


@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    return {
        "status": "healthy",
        "openai_key_configured": bool(os.getenv("OPENAI_API_KEY"))
    }


@app.post("/api/v1/query/compile", response_model=QueryResponse, status_code=status.HTTP_200_OK)
async def compile_natural_language_query(
    payload: QueryRequest,
    tenant_context: dict = Depends(check_rate_limit)
):
    if not payload.prompt.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The prompt string cannot be empty."
        )

    try:
        svc = get_agent_service()
        blueprint_object = svc.translate_text_to_blueprint(payload.prompt)
        blueprint_dict = blueprint_object.model_dump()

        sql_string, query_parameters = build_secure_query(blueprint_dict, tenant_id=tenant_context["tenant_id"])

        cached_records = get_cached_results(sql_string, query_parameters)

        if cached_records is not None:
            record_tenant_metric(tenant_context["tenant_id"], is_cache_hit=True, target_table=blueprint_dict["target_table"])

            sink_compliance_audit_log(
                tenant_id=tenant_context["tenant_id"],
                user_prompt=payload.prompt,
                compiled_sql=sql_string,
                parameters=query_parameters,
                cache_hit=True
            )

            return QueryResponse(
                status="success",
                compiled_sql=sql_string,
                parameters=query_parameters,
                cache_hit=True,
                results=cached_records,
                agent_blueprint=blueprint_dict
            )

        db_results = execute_secure_query(sql_string, query_parameters)

        set_cached_results(sql_string, query_parameters, db_results, ttl_seconds=300)

        record_tenant_metric(tenant_context["tenant_id"], is_cache_hit=False, target_table=blueprint_dict["target_table"])

        sink_compliance_audit_log(
            tenant_id=tenant_context["tenant_id"],
            user_prompt=payload.prompt,
            compiled_sql=sql_string,
            parameters=query_parameters,
            cache_hit=False
        )

        return QueryResponse(
            status="success",
            compiled_sql=sql_string,
            parameters=query_parameters,
            cache_hit=False,
            results=db_results,
            agent_blueprint=blueprint_dict
        )

    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while compiling your request: {str(e)}"
        )


@app.get("/api/v1/metrics", status_code=status.HTTP_200_OK)
async def get_live_tenant_analytics(tenant_context: dict = Depends(check_rate_limit)):
    plan = tenant_context["plan"]
    limit_ceiling = TIER_LIMITS.get(plan, 20)

    analytics_payload = get_tenant_metrics(tenant_context["tenant_id"], limit_ceiling)
    return analytics_payload


@app.post("/api/v1/export/async", status_code=status.HTTP_202_ACCEPTED)
async def trigger_bulk_data_export(
    payload: QueryRequest,
    tenant_context: dict = Depends(check_rate_limit)
):
    if not payload.prompt.strip():
        raise HTTPException(status_code=400, detail="The prompt string cannot be empty.")

    svc = get_agent_service()
    blueprint_object = svc.translate_text_to_blueprint(payload.prompt)
    blueprint_dict = blueprint_object.model_dump()

    task = execute_heavy_export_task.delay(blueprint_dict, tenant_context["tenant_id"])

    return {
        "status": "queued",
        "task_id": task.id,
        "poll_url": f"/api/v1/export/status/{task.id}"
    }


@app.get("/api/v1/export/status/{task_id}", status_code=status.HTTP_200_OK)
async def check_bulk_export_status(task_id: str, tenant_context: dict = Depends(check_rate_limit)):
    task_result = AsyncResult(task_id, app=execute_heavy_export_task.app)

    response_payload = {"task_id": task_id, "state": task_result.state}

    if task_result.state == "PROCESSING":
        response_payload["meta"] = task_result.info
    elif task_result.state == "SUCCESS":
        response_payload["result"] = task_result.result
    elif task_result.state == "FAILURE":
        response_payload["error"] = str(task_result.info)

    return response_payload