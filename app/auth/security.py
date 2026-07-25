import os
from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader

API_KEY_NAME = "X-Predicate-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

MOCK_TENANT_REGISTRY = {
    "pred_live_7f8a9b2c3d4e5f6g7h8i9j0k": {"tenant_id": "tenant_alpha", "plan": "enterprise"},
    "pred_test_1a2b3c4d5e6f7g8h9i0j1k2l": {"tenant_id": "tenant_beta", "plan": "growth"}
}


def validate_api_key(api_key: str = Security(api_key_header)) -> dict:
    if os.getenv("REQUIRE_AUTH", "false").lower() != "true":
        return {"tenant_id": "local_dev_tenant", "plan": "sandbox"}

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication credentials missing. Please provide the '{API_KEY_NAME}' header."
        )

    if api_key not in MOCK_TENANT_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or deactivated API key provided."
        )

    return MOCK_TENANT_REGISTRY[api_key]