import httpx

from creator_agent.agent.llm_report_analyzer import LLMReportAnalyzer
from creator_agent.config import Settings


def _settings() -> Settings:
    return Settings.model_construct(
        openai_api_key="test-key",
        openai_base_url="http://localhost:53881/v1",
        openai_translation_model="gpt-5.5",
        openai_analysis_model="gpt-5.5",
    )


def test_llm_report_analyzer_builds_report_from_model_json(monkeypatch):
    def fake_call_model(self, payload):
        return {
            "summary": "这条视频的核心是低位男主借系统听到隐藏真相，揭穿未婚夫骗局，并被冰山女总裁锁定。",
            "topic_type": "story_recap",
            "title_hook": "听到心声 + 冰山亿万女总裁 + 不许离开",
            "opening_hook": "开场用订婚宴高阶场景和服务生低位身份制造阶层落差。",
            "structure": ["低位男主进入高阶宴会", "系统揭露 Luke 是骗子", "女主听到男主心声", "男主被迫成为顾问"],
            "emotional_curve": ["阶层压迫", "秘密揭露", "关系锁定", "危机升级"],
            "growth_score": 82,
            "growth_reasons": ["标题承诺清晰", "前几分钟连续抛出信息差和反转"],
            "idea_cards": [
                {
                    "title": "我能听见女总裁未婚夫的秘密",
                    "angle": "心声信息差爽文",
                    "why_it_works": "观众会等着看骗子如何被拆穿，以及女主如何重新选择男主。",
                    "outline": ["低位男主进场", "系统爆料", "女主听见心声", "反派翻车"],
                    "risk_notes": "不要照抄角色名和具体桥段。",
                    "score": 84,
                }
            ],
            "comment_insights": {"status": "not_configured"},
        }

    monkeypatch.setattr(LLMReportAnalyzer, "_call_model", fake_call_model)
    analyzer = LLMReportAnalyzer(settings=_settings())

    report = analyzer.analyze(
        metadata={"title": "After HEARING My Thoughts...", "view_count": 80000},
        transcript={"text": "At the banquet, the hidden truth was revealed.", "source": "yt-dlp_auto_subtitle"},
        comments={"status": "not_configured"},
        channel_profile={"description": "Manhwa recap stories"},
        metrics={"performance_band": "high"},
    )

    assert report.creative_breakdown.topic_type == "story_recap"
    assert report.creative_breakdown.opening_hook.startswith("开场用订婚宴")
    assert report.growth_judgement.score == 82
    assert report.idea_cards[0].title == "我能听见女总裁未婚夫的秘密"


def test_llm_report_analyzer_flattens_nested_model_output(monkeypatch):
    def fake_call_model(self, payload):
        return {
            "summary": "核心卖点是女神消费返现。",
            "topic_type": "story_recap",
            "title_hook": {
                "hook_core": "女神每花 1 美元，男主返现 100 万倍。",
                "click_drivers": ["数字夸张", "一夜暴富"],
                "weakness": "标题偏长。",
            },
            "opening_hook": {
                "first_30_60_seconds": "穷学生进入富人场景。",
                "retention_mechanisms": ["阶层差", "系统觉醒"],
            },
            "structure": [{"beat": 1, "name": "破车被撞", "function": "制造强制靠近"}],
            "emotional_curve": [{"stage": "开局", "emotion": "卑微", "viewer_feeling": "期待翻身"}],
            "growth_score": 86,
            "growth_reasons": [{"reason": "高概念", "detail": "一句话能懂"}],
            "idea_cards": [],
            "comment_insights": {"status": "not_configured"},
        }

    monkeypatch.setattr(LLMReportAnalyzer, "_call_model", fake_call_model)
    report = LLMReportAnalyzer(settings=_settings()).analyze(
        metadata={"title": "x"},
        transcript={"text": "script"},
        comments={"status": "not_configured"},
        channel_profile={},
        metrics={},
    )

    assert "核心钩子：女神每花 1 美元" in report.creative_breakdown.title_hook
    assert "{'" not in report.creative_breakdown.title_hook
    assert report.creative_breakdown.structure == ["节拍：1；名称：破车被撞；作用：制造强制靠近"]
    assert report.growth_judgement.reasons == ["原因：高概念；细节：一句话能懂"]


def test_llm_report_analyzer_allows_local_base_url_without_real_key(tmp_path):
    settings = Settings.model_construct(
        openai_api_key=None,
        openai_base_url="http://localhost:53881/v1",
        openai_translation_model="gpt-5.5",
        openai_analysis_model=None,
        browser_engine="playwright",
        browser_headless=True,
        browser_path=None,
        browser_debug_port=None,
        browser_cdp_url="http://127.0.0.1:9222",
        workspace_settings_path=str(tmp_path / "workspace-settings.json"),
    )

    assert LLMReportAnalyzer(settings=settings)._api_key() == "local-dev-key"


def test_llm_report_analyzer_payload_avoids_strict_response_format_for_local_gateways():
    payload = LLMReportAnalyzer(settings=_settings())._build_payload(
        metadata={"title": "x"},
        transcript={"text": "script"},
        comments={"status": "not_configured"},
        channel_profile={},
        metrics={},
    )

    assert "text" not in payload
    assert "资深内容分析智能体" in payload["instructions"]
    assert "outline 必须输出 6-8 步" in payload["instructions"]
    assert "前 15 秒开场钩子" in payload["instructions"]


def test_llm_report_analyzer_expands_short_idea_outline(monkeypatch):
    def fake_call_model(self, payload):
        return {
            "summary": "核心卖点是低位主角被误解后靠隐藏机制翻身。",
            "topic_type": "story_recap",
            "title_hook": "低位误解 + 隐藏机制 + 公开反转",
            "opening_hook": "先把主角放进公开受压的位置。",
            "structure": ["公开受压", "隐藏机制触发", "误解升级", "第一次反转", "更大危机"],
            "emotional_curve": ["委屈", "期待", "反转", "悬念"],
            "growth_score": 80,
            "growth_reasons": ["身份差清晰", "兑现路径直接"],
            "idea_cards": [
                {
                    "title": "所有人都以为他输了，直到隐藏奖励开始兑现",
                    "angle": "身份差反转爽文",
                    "why_it_works": "观众会等着看低位主角怎样把公开羞辱变成反打。",
                    "outline": ["公开羞辱", "隐藏奖励触发"],
                    "risk_notes": "不要复用原视频角色名和具体桥段。",
                    "score": 80,
                }
            ],
            "comment_insights": {"status": "not_configured"},
        }

    monkeypatch.setattr(LLMReportAnalyzer, "_call_model", fake_call_model)

    report = LLMReportAnalyzer(settings=_settings()).analyze(
        metadata={"title": "x"},
        transcript={"text": "script"},
        comments={"status": "not_configured"},
        channel_profile={},
        metrics={},
    )

    outline = report.idea_cards[0].outline
    assert len(outline) >= 6
    assert outline[0].startswith("标题承诺")
    assert any("前 15 秒" in item for item in outline)
    assert any("结尾悬念" in item for item in outline)


def test_llm_report_analyzer_extracts_json_from_markdown_block():
    analyzer = LLMReportAnalyzer(settings=Settings.model_construct())

    assert analyzer._extract_json_text('```json\n{"summary":"ok"}\n```') == '{"summary":"ok"}'


def test_llm_report_analyzer_repairs_trailing_commas_in_model_json():
    analyzer = LLMReportAnalyzer(settings=Settings.model_construct())

    data = analyzer._loads_model_json('{"summary":"ok","idea_cards":[{"title":"x",},],}')

    assert data == {"summary": "ok", "idea_cards": [{"title": "x"}]}


def test_llm_report_analyzer_retries_transient_response_errors(monkeypatch):
    calls = []

    def fake_post(*args, **kwargs):
        calls.append(1)
        request = httpx.Request("POST", "http://localhost:53881/v1/responses")
        if len(calls) < 3:
            return httpx.Response(500, request=request, json={"error": "temporary"})
        return httpx.Response(200, request=request, json={"output_text": '{"summary":"ok","growth_score":70}'})

    monkeypatch.setattr("creator_agent.agent.llm_report_analyzer.httpx.post", fake_post)
    monkeypatch.setattr("creator_agent.agent.llm_report_analyzer.time.sleep", lambda seconds: None)

    data = LLMReportAnalyzer(settings=_settings())._call_model({"model": "gpt-5.5", "input": "x"})

    assert data["summary"] == "ok"
    assert len(calls) == 3


def test_llm_report_analyzer_writes_audit_request_and_response(tmp_path, monkeypatch):
    log_path = tmp_path / "analysis.jsonl"
    settings = Settings.model_construct(
        openai_api_key="test-key",
        openai_base_url="http://localhost:53881/v1",
        openai_translation_model="gpt-5.5",
        openai_analysis_model="gpt-5.5",
        analysis_log_path=str(log_path),
        workspace_settings_path=str(tmp_path / "workspace-settings.json"),
    )

    def fake_post(*args, **kwargs):
        request = httpx.Request("POST", "http://localhost:53881/v1/responses")
        return httpx.Response(
            200,
            request=request,
            json={
                "id": "resp-test",
                "status": "completed",
                "model": "gpt-5.5",
                "output_text": '{"summary":"ok","growth_score":70}',
            },
        )

    monkeypatch.setattr("creator_agent.agent.llm_report_analyzer.httpx.post", fake_post)

    from creator_agent.services.analysis_audit_logger import AnalysisAuditLogger

    analyzer = LLMReportAnalyzer(settings=settings, audit_logger=AnalysisAuditLogger(settings=settings, run_id="run-test"))
    analyzer._call_model(
        analyzer._build_payload(
            metadata={"title": "Audit title", "youtube_video_id": "abc123"},
            transcript={"text": "script", "source": "manual", "language": "en"},
            comments={"status": "not_configured"},
            channel_profile={},
            metrics={},
        )
    )

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert any('"event": "llm_request"' in line and '"model": "gpt-5.5"' in line for line in lines)
    assert any('"event": "llm_response"' in line and '"response_id": "resp-test"' in line for line in lines)
    assert "test-key" not in log_path.read_text(encoding="utf-8")
