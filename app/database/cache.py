import os
import json
import hashlib
from typing import List, Dict, Any, Optional
import redis

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> Optional[redis.Redis]:
    global _redis_client
    if _redis_client is None and os.getenv("REDIS_URL"):
        try:
            _redis_client = redis.Redis.from_url(
                os.getenv("REDIS_URL"),
                decode_responses=True,
                socket_timeout=2.0
            )
        except Exception:
            _redis_client = None
    return _redis_client


def generate_cache_key(sql_string: str, parameters: List[Any]) -> str:
    raw_payload = f"{sql_string}::{str(parameters)}"
    hash_signature = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()
    return f"predicate:query_cache:{hash_signature}"


def get_cached_results(sql_string: str, parameters: List[Any]) -> Optional[List[Dict[str, Any]]]:
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


def set_cached_results(sql_string: str, parameters: List[Any], results: List[Dict[str, Any]], ttl_seconds: int = 300) -> None:
    client = get_redis_client()
    if not client:
        return

    try:
        cache_key = generate_cache_key(sql_string, parameters)
        serialized_payload = json.dumps(results)
        client.setex(cache_key, ttl_seconds, serialized_payload)
    except Exception:
        pass