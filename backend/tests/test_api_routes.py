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


def test_health_preflight_allows_loopback_dev_origin():
    client = TestClient(create_app())

    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_video_analysis_endpoint_returns_mock_queue_state():
    client = TestClient(create_app())

    response = client.post(
        "/api/analysis/video",
        json={"video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "mock_queued",
        "mock": True,
        "target_type": "video_url",
        "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    }
