import pytest
from fastapi import HTTPException

from app.auth.rate_limiter import check_rate_limit
from app.auth.security import validate_api_key


def test_auth_disabled_by_default(monkeypatch):
    monkeypatch.setenv("REQUIRE_AUTH", "false")
    context = validate_api_key(api_key=None)
    assert context["tenant_id"] == "tenant_alpha"
    assert context["plan"] == "sandbox"


def test_auth_enabled_missing_key(monkeypatch):
    monkeypatch.setenv("REQUIRE_AUTH", "true")
    with pytest.raises(HTTPException) as excinfo:
        validate_api_key(api_key=None)
    assert excinfo.value.status_code == 401
    assert "Authentication credentials missing" in str(excinfo.value.detail)


def test_auth_enabled_invalid_key(monkeypatch):
    monkeypatch.setenv("REQUIRE_AUTH", "true")
    with pytest.raises(HTTPException) as excinfo:
        validate_api_key(api_key="bad_token_123")
    assert excinfo.value.status_code == 403
    assert "Invalid or deactivated" in str(excinfo.value.detail)


def test_auth_enabled_valid_enterprise_key(monkeypatch):
    monkeypatch.setenv("REQUIRE_AUTH", "true")
    context = validate_api_key(api_key="pred_live_7f8a9b2c3d4e5f6g7h8i9j0k")
    assert context["tenant_id"] == "tenant_alpha"
    assert context["plan"] == "enterprise"


def test_auth_enabled_valid_growth_key(monkeypatch):
    monkeypatch.setenv("REQUIRE_AUTH", "true")
    context = validate_api_key(api_key="pred_test_1a2b3c4d5e6f7g8h9i0j1k2l")
    assert context["tenant_id"] == "tenant_beta"
    assert context["plan"] == "growth"


def test_rate_limiter_allows_under_limit(mocker):
    mock_redis = mocker.MagicMock()
    mock_redis.incr.return_value = 5
    mocker.patch("app.auth.rate_limiter.get_redis_client", return_value=mock_redis)

    mock_context = {"tenant_id": "tenant_beta", "plan": "growth"}
    result = check_rate_limit(tenant_context=mock_context)

    assert result == mock_context
    mock_redis.incr.assert_called_once()


def test_rate_limiter_blocks_over_limit(mocker):
    mock_redis = mocker.MagicMock()
    mock_redis.incr.return_value = 21
    mocker.patch("app.auth.rate_limiter.get_redis_client", return_value=mock_redis)

    mock_context = {"tenant_id": "tenant_beta", "plan": "growth"}

    with pytest.raises(HTTPException) as excinfo:
        check_rate_limit(tenant_context=mock_context)

    assert excinfo.value.status_code == 429
    assert excinfo.value.detail["error"] == "Rate limit exceeded."
    assert excinfo.value.detail["limit_allowed"] == 20


def test_rate_limiter_sets_ttl_on_first_request(mocker):
    mock_redis = mocker.MagicMock()
    mock_redis.incr.return_value = 1
    mocker.patch("app.auth.rate_limiter.get_redis_client", return_value=mock_redis)

    mock_context = {"tenant_id": "tenant_alpha", "plan": "enterprise"}
    check_rate_limit(tenant_context=mock_context)

    mock_redis.expire.assert_called_once_with(mock_redis.incr.call_args[0][0], 60)


def test_rate_limiter_bypasses_when_redis_unavailable(mocker):
    mocker.patch("app.auth.rate_limiter.get_redis_client", return_value=None)

    mock_context = {"tenant_id": "tenant_beta", "plan": "growth"}
    result = check_rate_limit(tenant_context=mock_context)

    assert result == mock_context


def test_rate_limiter_enterprise_allows_100(mocker):
    mock_redis = mocker.MagicMock()
    mock_redis.incr.return_value = 100
    mocker.patch("app.auth.rate_limiter.get_redis_client", return_value=mock_redis)

    mock_context = {"tenant_id": "tenant_alpha", "plan": "enterprise"}
    result = check_rate_limit(tenant_context=mock_context)

    assert result == mock_context


def test_rate_limiter_enterprise_blocks_101(mocker):
    mock_redis = mocker.MagicMock()
    mock_redis.incr.return_value = 101
    mocker.patch("app.auth.rate_limiter.get_redis_client", return_value=mock_redis)

    mock_context = {"tenant_id": "tenant_alpha", "plan": "enterprise"}

    with pytest.raises(HTTPException) as excinfo:
        check_rate_limit(tenant_context=mock_context)

    assert excinfo.value.status_code == 429
    assert excinfo.value.detail["limit_allowed"] == 100
