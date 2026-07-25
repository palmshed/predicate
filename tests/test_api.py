from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_compile_endpoint_empty_payload_validation(monkeypatch):
    monkeypatch.setenv("REQUIRE_AUTH", "false")
    response = client.post("/api/v1/query/compile", json={"prompt": ""})
    assert response.status_code == 400
    assert "cannot be empty" in response.json()["detail"]


def test_compile_endpoint_whitespace_payload_validation(monkeypatch):
    monkeypatch.setenv("REQUIRE_AUTH", "false")
    response = client.post("/api/v1/query/compile", json={"prompt": "   "})
    assert response.status_code == 400
    assert "cannot be empty" in response.json()["detail"]


def test_compile_endpoint_missing_prompt_field(monkeypatch):
    monkeypatch.setenv("REQUIRE_AUTH", "false")
    response = client.post("/api/v1/query/compile", json={})
    assert response.status_code == 422