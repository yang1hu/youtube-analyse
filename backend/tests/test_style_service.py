import json

import httpx
from fastapi.testclient import TestClient

from creator_agent.main import create_app


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self.payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "fake error",
                request=httpx.Request("POST", "http://test.local/responses"),
                response=httpx.Response(self.status_code),
            )


def _workspace_data() -> dict:
    return {
        "channels": [],
        "recent_videos": [],
        "jobs": [],
        "idea_cards": [],
        "style_profiles": [],
        "copy_drafts": [],
        "reports": [
            {
                "id": "report-1",
                "video_url": "https://www.youtube.com/watch?v=real",
                "video_title": "Every Dollar a Goddess Spends on Me Returns 1,000,000x",
                "summary": "核心是女神消费返现带来的身份差和信息差。",
                "collection_evidence": {"analysis_source": "llm", "analysis_status": "ok"},
                "creative_breakdown": {
                    "topic_type": "story_recap",
                    "title_hook": "女神消费返现一百万倍。",
                    "opening_hook": "先把穷学生放进富人宴会，再触发返现系统。",
                    "structure": ["穷学生入场", "女神消费触发返现", "旁人误会身份"],
                    "emotional_curve": ["卑微", "惊喜", "打脸"],
                },
                "growth_judgement": {
                    "score": 90,
                    "reasons": ["高概念一句话能懂", "身份差信息差强"],
                },
                "idea_cards": [
                    {
                        "title": "校花买咖啡触发商业大厦返现",
                        "angle": "从小额消费触发巨额身份变化。",
                        "why_it_works": "小钱变巨富，反差明确。",
                        "outline": ["咖啡店打工", "校花买咖啡", "触发返现", "商场经理称呼老板"],
                        "risk_notes": "不要照抄原视频桥段。",
                        "score": 9,
                    }
                ],
            }
        ],
    }


def _client(tmp_path, monkeypatch, data: dict | None = None) -> TestClient:
    data_path = tmp_path / "workspace-data.json"
    data_path.write_text(json.dumps(data or _workspace_data(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(data_path))
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))
    monkeypatch.setenv("YCA_OPENAI_BASE_URL", "http://127.0.0.1:53881/v1")
    monkeypatch.setenv("YCA_OPENAI_ANALYSIS_MODEL", "test-model")
    return TestClient(create_app())


def test_style_learning_and_copywriting_with_llm_success(tmp_path, monkeypatch):
    def fake_post(url, headers, json, timeout):
        assert url == "http://127.0.0.1:53881/v1/responses"
        assert headers["Authorization"].startswith("Bearer ")
        assert json["model"] == "test-model"
        return FakeResponse({"output_text": "## 标题备选\n1. 原创返现爽文标题\n\n## 前 60 秒口播脚本\n新的角色和新的触发事件。"})

    monkeypatch.setattr("creator_agent.services.style_service.httpx.post", fake_post)
    client = _client(tmp_path, monkeypatch)

    learned = client.post("/api/styles/learn-latest", json={"name": "系统返现爽文风格"})
    styles = client.get("/api/styles")
    applied = client.post(
        "/api/styles/apply",
        json={"style_id": learned.json()["style_profile"]["id"], "idea_id": "report-1-idea-1"},
    )

    assert learned.status_code == 200
    assert learned.json()["style_profile"]["name"] == "系统返现爽文风格"
    assert learned.json()["style_profile"]["avoid_copying"]
    assert styles.status_code == 200
    assert len(styles.json()["style_profiles"]) == 1
    assert applied.status_code == 200
    draft = applied.json()["copy_draft"]
    assert draft["title"] == "校花买咖啡触发商业大厦返现"
    assert draft["provider"] == "openai"
    assert draft["model"] == "test-model"
    assert "前 60 秒口播脚本" in draft["copy"]


def test_style_copywriting_empty_llm_output_uses_fallback(tmp_path, monkeypatch):
    def fake_post(url, headers, json, timeout):
        return FakeResponse({"output": [{"content": []}]})

    monkeypatch.setattr("creator_agent.services.style_service.httpx.post", fake_post)
    client = _client(tmp_path, monkeypatch)

    learned = client.post("/api/styles/learn-latest", json={})
    applied = client.post(
        "/api/styles/apply",
        json={"style_id": learned.json()["style_profile"]["id"], "idea_id": "report-1-idea-1"},
    )

    assert applied.status_code == 200
    draft = applied.json()["copy_draft"]
    assert draft["provider"] == "local"
    assert draft["model"] == "fallback"
    assert "标题备选" in draft["copy"]
    assert "本草稿为本地兜底生成" in draft["copy"]


def test_style_copywriting_network_failure_uses_fallback(tmp_path, monkeypatch):
    def fake_post(url, headers, json, timeout):
        raise httpx.ConnectError("local LLM unavailable")

    monkeypatch.setattr("creator_agent.services.style_service.httpx.post", fake_post)
    client = _client(tmp_path, monkeypatch)

    learned = client.post("/api/styles/learn-latest", json={})
    applied = client.post(
        "/api/styles/apply",
        json={"style_id": learned.json()["style_profile"]["id"], "idea_id": "report-1-idea-1"},
    )

    assert applied.status_code == 200
    draft = applied.json()["copy_draft"]
    assert draft["provider"] == "local"
    assert "避抄提醒" in draft["copy"]


def test_style_learning_requires_successful_llm_report(tmp_path, monkeypatch):
    data = _workspace_data()
    data["reports"][0]["collection_evidence"] = {"analysis_source": "rule_fallback", "analysis_status": "failed"}
    client = _client(tmp_path, monkeypatch, data=data)

    response = client.post("/api/styles/learn-latest", json={})

    assert response.status_code == 422


def test_style_apply_requires_existing_style_and_idea(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    missing_style = client.post("/api/styles/apply", json={"style_id": "missing", "idea_id": "report-1-idea-1"})
    learned = client.post("/api/styles/learn-latest", json={})
    missing_idea = client.post(
        "/api/styles/apply",
        json={"style_id": learned.json()["style_profile"]["id"], "idea_id": "missing"},
    )

    assert missing_style.status_code == 422
    assert missing_idea.status_code == 422
