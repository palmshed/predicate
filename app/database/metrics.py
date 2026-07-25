import time
from typing import Dict, Any
from app.database.cache import get_redis_client


def record_tenant_metric(tenant_id: str, is_cache_hit: bool, target_table: str) -> None:
    client = get_redis_client()
    if not client:
        return

    try:
        base_key = f"predicate:metrics:{tenant_id}"

        pipe = client.pipeline()
        pipe.incr(f"{base_key}:total_requests")
        pipe.incr(f"{base_key}:table:{target_table}")

        if is_cache_hit:
            pipe.incr(f"{base_key}:cache_hits")
        else:
            pipe.incr(f"{base_key}:db_misses")

        pipe.execute()
    except Exception:
        pass


def get_tenant_metrics(tenant_id: str, plan_limit: int) -> Dict[str, Any]:
    client = get_redis_client()
    if not client:
        return {"error": "Metrics storage cluster currently unreachable."}

    base_key = f"predicate:metrics:{tenant_id}"

    try:
        total = int(client.get(f"{base_key}:total_requests") or 0)
        hits = int(client.get(f"{base_key}:cache_hits") or 0)
        misses = int(client.get(f"{base_key}:db_misses") or 0)

        efficiency_ratio = round((hits / total) * 100, 1) if total > 0 else 0.0

        current_minute = int(time.time() // 60)
        current_rpm = int(client.get(f"predicate:rate_limit:{tenant_id}:{current_minute}") or 0)

        return {
            "tenant_id": tenant_id,
            "current_minute_usage": {
                "requests_per_minute": current_rpm,
                "tier_limit_ceiling": plan_limit,
                "capacity_percentage_used": round((current_rpm / plan_limit) * 100, 1) if plan_limit > 0 else 0
            },
            "historical_aggregates": {
                "total_queries_processed": total,
                "cached_responses_served": hits,
                "database_fallbacks_executed": misses,
                "infrastructure_efficiency_score": f"{efficiency_ratio}%"
            }
        }
    except Exception as e:
        return {"error": f"Failed to calculate real-time usage metrics: {str(e)}"}