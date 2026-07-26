import time

from fastapi import Depends, HTTPException, status

from app.auth.security import validate_api_key
from app.database.cache import get_redis_client

TIER_LIMITS = {"sandbox": 60, "growth": 20, "enterprise": 100}


def check_rate_limit(tenant_context: dict = Depends(validate_api_key)) -> dict:
    client = get_redis_client()
    if not client:
        return tenant_context

    tenant_id = tenant_context["tenant_id"]
    plan = tenant_context["plan"]
    limit = TIER_LIMITS.get(plan, 20)

    current_minute = int(time.time() // 60)
    redis_key = f"predicate:rate_limit:{tenant_id}:{current_minute}"

    try:
        current_requests = client.incr(redis_key)

        if current_requests == 1:
            client.expire(redis_key, 60)

        if current_requests > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Rate limit exceeded.",
                    "limit_allowed": limit,
                    "time_window": "60 seconds",
                    "suggestion": "Upgrade your tier to unlock higher limits.",
                },
            )
    except HTTPException:
        raise
    except Exception:
        pass

    return tenant_context
