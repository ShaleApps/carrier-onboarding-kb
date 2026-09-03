from fastapi.testclient import TestClient

from carrier_kb.api.app import create_app


def test_health_and_readiness_expose_request_id(monkeypatch):
    monkeypatch.setenv("KB_DSN", "")
    client = TestClient(create_app())
    response = client.get("/healthz", headers={"X-Request-ID": "smoke-123"})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "smoke-123"
    readiness = client.get("/readyz")
    assert readiness.json()["status"] == "not_ready"
    assert readiness.json()["database"] == "unavailable"
