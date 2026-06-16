import json

from fastapi.testclient import TestClient

from creator_agent.main import create_app


def _workspace_data() -> dict:
    return {
        "channels": [],
        "recent_videos": [],
        "jobs": [],
        "reports": [],
        "copy_drafts": [],
        "script_drafts": [],
        "sample_analyses": [],
        "style_profiles": [
            {
                "id": "style-1",
                "name": "Fast system opening",
                "opening_formula": "Start with a public humiliation and reveal the hidden rule.",
                "title_formula": "Tiny spend triggers huge return.",
                "reusable_rules": ["Open with consequence", "Escalate every reward"],
                "avoid_copying": ["Do not reuse original names."],
            }
        ],
        "idea_cards": [
            {
                "id": "idea-1",
                "title": "Coffee purchase triggers a tower ownership reward",
                "angle": "Small consumption turns into public status reversal.",
                "why_it_works": "The money gap is immediate and visible.",
                "outline": ["Cashier conflict", "Tiny purchase", "Reward triggers", "Manager reversal"],
                "risk_notes": "Avoid copying the source plot.",
                "score": 92,
            }
        ],
    }


def _client(tmp_path, monkeypatch) -> TestClient:
    data_path = tmp_path / "workspace-data.json"
    data_path.write_text(json.dumps(_workspace_data(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(data_path))
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))
    return TestClient(create_app())


def test_script_studio_generates_script_with_title_opening_full_script_and_history(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    generated = client.post("/api/scripts/generate", json={"idea_id": "idea-1", "style_id": "style-1"})
    listed = client.get("/api/scripts")

    assert generated.status_code == 200
    script = generated.json()["script_draft"]
    assert script["version"] == 1
    assert len(script["title_options"]) == 3
    assert script["opening_30s"]
    assert script["full_script"]
    assert script["markdown"].startswith("# ")
    assert listed.status_code == 200
    assert listed.json()["script_drafts"][0]["id"] == script["id"]


def test_script_studio_rewrites_existing_script_as_new_version(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    original = client.post("/api/scripts/generate", json={"idea_id": "idea-1", "style_id": "style-1"}).json()["script_draft"]

    rewritten = client.post(f"/api/scripts/{original['id']}/rewrite", json={"style_id": "style-1"})
    listed = client.get("/api/scripts")

    assert rewritten.status_code == 200
    new_version = rewritten.json()["script_draft"]
    assert new_version["parent_id"] == original["id"]
    assert new_version["version"] == 2
    assert "Version 2" in new_version["markdown"]
    assert [item["id"] for item in listed.json()["script_drafts"]][:2] == [new_version["id"], original["id"]]


def test_script_studio_exports_markdown(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    script = client.post("/api/scripts/generate", json={"idea_id": "idea-1", "style_id": "style-1"}).json()["script_draft"]

    exported = client.get(f"/api/scripts/{script['id']}/markdown")

    assert exported.status_code == 200
    assert exported.json()["filename"].endswith(".md")
    assert exported.json()["markdown"] == script["markdown"]


def test_script_studio_selects_title_as_new_version_and_exports_that_title(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    original = client.post("/api/scripts/generate", json={"idea_id": "idea-1", "style_id": "style-1"}).json()["script_draft"]
    selected_title = original["title_options"][1]

    selected = client.patch(f"/api/scripts/{original['id']}", json={"selected_title": selected_title})
    listed = client.get("/api/scripts")
    exported = client.get(f"/api/scripts/{selected.json()['script_draft']['id']}/markdown")

    assert selected.status_code == 200
    new_version = selected.json()["script_draft"]
    assert new_version["parent_id"] == original["id"]
    assert new_version["version"] == 2
    assert new_version["selected_title"] == selected_title
    assert new_version["markdown"].startswith(f"# {selected_title}")
    assert listed.json()["script_drafts"][0]["id"] == new_version["id"]
    assert exported.json()["filename"].endswith(".md")
    assert "small-consumption-turns-into-public-status-reversal" in exported.json()["filename"]


def test_script_studio_requires_existing_idea(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post("/api/scripts/generate", json={"idea_id": "missing", "style_id": "style-1"})

    assert response.status_code == 422
