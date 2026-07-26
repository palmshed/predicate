import hashlib
import json
import os
from typing import Any

import redis

_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis | None:
    global _redis_client
    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            try:
                _redis_client = redis.Redis.from_url(
                    redis_url, decode_responses=True, socket_timeout=2.0
                )
            except Exception:
                _redis_client = None
    return _redis_client


def generate_cache_key(sql_string: str, parameters: list[Any]) -> str:
    raw_payload = f"{sql_string}::{str(parameters)}"
    hash_signature = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()
    return f"predicate:query_cache:{hash_signature}"


def get_cached_results(sql_string: str, parameters: list[Any]) -> list[dict[str, Any]] | None:
    client = get_redis_client()
    if not client:
        return None

    try:
        cache_key = generate_cache_key(sql_string, parameters)
        cached_data = client.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
    except Exception:
        pass
    return None


def set_cached_results(
    sql_string: str, parameters: list[Any], results: list[dict[str, Any]], ttl_seconds: int = 300
) -> None:
    client = get_redis_client()
    if not client:
        return

    try:
        cache_key = generate_cache_key(sql_string, parameters)
        serialized_payload = json.dumps(results)
        client.setex(cache_key, ttl_seconds, serialized_payload)
    except Exception:
        pass
