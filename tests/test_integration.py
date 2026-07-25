import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# --- SECURITY & AUTHENTICATION INTEGRATION TESTS ---

def test_compile_endpoint_enforces_auth_when_enabled(monkeypatch):
    monkeypatch.setenv("REQUIRE_AUTH", "true")

    response = client.post("/api/v1/query/compile", json={"prompt": "Show all orders"})
    assert response.status_code == 401
    assert "credentials missing" in response.json()["detail"].lower()


def test_compile_endpoint_rejects_invalid_api_key(monkeypatch):
    monkeypatch.setenv("REQUIRE_AUTH", "true")
    headers = {"X-Predicate-API-Key": "pred_invalid_fake_key_12345"}

    response = client.post("/api/v1/query/compile", json={"prompt": "Show all orders"}, headers=headers)
    assert response.status_code == 403
    assert "invalid or deactivated" in response.json()["detail"].lower()


def test_compile_endpoint_accepts_valid_api_key(monkeypatch, mocker):
    monkeypatch.setenv("REQUIRE_AUTH", "true")
    headers = {"X-Predicate-API-Key": "pred_live_7f8a9b2c3d4e5f6g7h8i9j0k"}

    mock_blueprint = mocker.MagicMock()
    mock_blueprint.model_dump.return_value = {
        "target_table": "customers",
        "projection_columns": [],
        "filters": [],
        "sorting": {"column": "", "direction": "asc"},
        "pagination": {"limit": 20, "offset": 0}
    }

    mock_svc = mocker.MagicMock()
    mock_svc.translate_text_to_blueprint.return_value = mock_blueprint

    import app.main as main_module
    main_module.agent_service = None
    main_module.agent_service = mock_svc

    mocker.patch("app.database.cache.get_redis_client", return_value=None)
    mocker.patch("app.database.metrics.get_redis_client", return_value=None)
    mocker.patch("app.database.connection.execute_secure_query", return_value=[])

    response = client.post("/api/v1/query/compile", json={"prompt": "Show all customers"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "customers" in response.json()["compiled_sql"]


# --- ASYNCHRONOUS EXPORT TASK QUEUE TESTS ---

def test_async_export_endpoint_requires_valid_prompt(monkeypatch):
    monkeypatch.setenv("REQUIRE_AUTH", "false")

    response = client.post("/api/v1/export/async", json={"prompt": "   "})
    assert response.status_code == 400
    assert "cannot be empty" in response.json()["detail"].lower()


def test_async_export_endpoint_queues_task_successfully(monkeypatch, mocker):
    monkeypatch.setenv("REQUIRE_AUTH", "false")

    mock_blueprint = mocker.MagicMock()
    mock_svc = mocker.MagicMock()
    mock_svc.translate_text_to_blueprint.return_value = mock_blueprint

    import app.main as main_module
    main_module.agent_service = mock_svc

    mock_task = mocker.MagicMock()
    mock_task.id = "mock-celery-uuid-12345"
    mocker.patch("app.worker.execute_heavy_export_task.delay", return_value=mock_task)

    response = client.post("/api/v1/export/async", json={"prompt": "Export completed orders"})
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert response.json()["task_id"] == "mock-celery-uuid-12345"
    assert "/api/v1/export/status/" in response.json()["poll_url"]