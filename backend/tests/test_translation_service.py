from creator_agent.config import Settings
from creator_agent.services.transcript_store import TranscriptStore
from creator_agent.services.translation_service import TranslationService
import httpx


def test_translation_service_uses_cached_translation(tmp_path, monkeypatch):
    settings = Settings.model_construct(
        transcript_cache_dir=str(tmp_path / "transcripts"),
        translation_cache_dir=str(tmp_path / "translations"),
        openai_api_key="test-key",
        openai_base_url="https://api.openai.com/v1",
        openai_translation_model="gpt-4.1-mini",
    )
    store = TranscriptStore(settings)
    store.save_transcript(
        video_id="abc123",
        video_url="https://www.youtube.com/watch?v=abc123",
        title="Test",
        source="test",
        language="en",
        raw_text="First line.\nSecond line.",
    )
    calls = []

    def fake_translate_chunk(self, chunk, target_language, index, total):
        calls.append(chunk)
        return "第一行。\n第二行。"

    monkeypatch.setattr(TranslationService, "_translate_chunk", fake_translate_chunk)
    service = TranslationService(settings=settings, store=store)

    first = service.get_or_translate("abc123")
    second = service.get_or_translate("abc123")

    assert first["translated_text"] == "第一行。\n第二行。"
    assert second["translated_text"] == "第一行。\n第二行。"
    assert len(calls) == 1


def test_translation_service_splits_long_text(tmp_path, monkeypatch):
    settings = Settings.model_construct(
        transcript_cache_dir=str(tmp_path / "transcripts"),
        translation_cache_dir=str(tmp_path / "translations"),
        openai_api_key="test-key",
        openai_base_url="https://api.openai.com/v1",
        openai_translation_model="gpt-4.1-mini",
    )
    service = TranslationService(settings=settings)

    chunks = service._chunk_text("\n".join(f"line {index}" for index in range(2000)), max_chars=1000)

    assert len(chunks) > 1
    assert all(len(chunk) <= 1000 for chunk in chunks)


def test_translation_service_retries_transient_response_errors(monkeypatch):
    settings = Settings.model_construct(
        transcript_cache_dir=".runtime/transcripts",
        translation_cache_dir=".runtime/translations",
        openai_api_key="test-key",
        openai_base_url="http://localhost:53881/v1",
        openai_translation_model="gpt-5.5",
    )
    service = TranslationService(settings=settings)
    calls = []

    def fake_post(*args, **kwargs):
        calls.append(1)
        request = httpx.Request("POST", "http://localhost:53881/v1/responses")
        if len(calls) == 1:
            return httpx.Response(429, request=request, json={"error": "rate limit"})
        return httpx.Response(200, request=request, json={"output_text": "翻译成功"})

    monkeypatch.setattr("creator_agent.services.translation_service.httpx.post", fake_post)
    monkeypatch.setattr("creator_agent.services.translation_service.time.sleep", lambda seconds: None)

    result = service._translate_chunk("hello", target_language="zh-CN", index=1, total=1)

    assert result == "翻译成功"
    assert len(calls) == 2
