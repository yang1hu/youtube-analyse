from fastapi.testclient import TestClient

from creator_agent.main import create_app


def test_health_endpoint():
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "YouTube Creator Growth Agent"}


def test_dashboard_endpoint_returns_empty_state():
    client = TestClient(create_app())

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    assert response.json()["recent_videos"] == []
    assert response.json()["idea_cards"] == []
    assert response.json()["comment_collector_status"] == "not_configured"
