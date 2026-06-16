import hashlib
import os
import threading
import time
from typing import Any

import httpx

from creator_agent.config import Settings
from creator_agent.services.settings_service import WorkspaceSettingsService
from creator_agent.services.transcript_store import TranscriptStore


class TranslationService:
    def __init__(self, settings: Settings | None = None, store: TranscriptStore | None = None) -> None:
        self.settings = settings or Settings()
        self.workspace_settings = WorkspaceSettingsService(self.settings).get_private()
        self.store = store or TranscriptStore(self.settings)

    def get_or_translate(self, video_id: str, target_language: str = "zh-CN", force: bool = False) -> dict[str, Any]:
        transcript = self.store.get_transcript(video_id)
        if not transcript:
            raise ValueError("Transcript is not available for this video yet.")

        raw_text = str(transcript.get("raw_text") or "")
        source_hash = self._text_hash(raw_text)
        cached = self.store.get_translation(video_id, target_language=target_language)
        if cached and not force and cached.get("source_text_hash") == source_hash:
            return cached

        translated_text = self._translate_text(raw_text, target_language=target_language)
        return self.store.save_translation(
            video_id=video_id,
            target_language=target_language,
            source_language=str(transcript.get("language") or ""),
            source_text_hash=source_hash,
            translated_text=translated_text,
            provider="openai",
            model=self._model(),
        )

    def start_background_translation(self, video_id: str, target_language: str = "zh-CN", force: bool = False) -> dict[str, Any]:
        transcript = self.store.get_transcript(video_id)
        if not transcript:
            raise ValueError("Transcript is not available for this video yet.")

        raw_text = str(transcript.get("raw_text") or "")
        source_hash = self._text_hash(raw_text)
        cached = self.store.get_translation(video_id, target_language=target_language)
        if cached and not force and cached.get("source_text_hash") == source_hash:
            return {"status": "complete", "translation": cached}

        current_status = self.store.get_translation_status(video_id, target_language=target_language)
        if current_status and current_status.get("status") == "running" and not force:
            return {"status": "running", "translation_status": current_status}

        chunks = self._chunk_text(raw_text, max_chars=3500)
        status = self.store.save_translation_status(
            video_id=video_id,
            target_language=target_language,
            status="running",
            source_text_hash=source_hash,
            translated_chunks=[],
            total_chunks=len(chunks),
            provider="openai",
            model=self._model(),
        )

        worker = threading.Thread(
            target=self._run_background_translation,
            args=(video_id, target_language, str(transcript.get("language") or ""), source_hash, chunks),
            daemon=True,
        )
        worker.start()
        return {"status": "running", "translation_status": status}

    def _run_background_translation(
        self,
        video_id: str,
        target_language: str,
        source_language: str,
        source_hash: str,
        chunks: list[str],
    ) -> None:
        translated_chunks: list[str] = []
        try:
            for index, chunk in enumerate(chunks, start=1):
                translated_chunks.append(
                    self._translate_chunk(
                        chunk=chunk,
                        target_language=target_language,
                        index=index,
                        total=len(chunks),
                    )
                )
                self.store.save_translation_status(
                    video_id=video_id,
                    target_language=target_language,
                    status="running",
                    source_text_hash=source_hash,
                    translated_chunks=translated_chunks,
                    total_chunks=len(chunks),
                        provider="openai",
                        model=self._model(),
                )

            translated_text = "\n\n".join(translated_chunks).strip()
            self.store.save_translation(
                video_id=video_id,
                target_language=target_language,
                source_language=source_language,
                source_text_hash=source_hash,
                translated_text=translated_text,
                provider="openai",
                model=self._model(),
            )
            self.store.save_translation_status(
                video_id=video_id,
                target_language=target_language,
                status="complete",
                source_text_hash=source_hash,
                translated_chunks=translated_chunks,
                total_chunks=len(chunks),
                provider="openai",
                model=self._model(),
            )
        except Exception as exc:
            self.store.save_translation_status(
                video_id=video_id,
                target_language=target_language,
                status="failed",
                source_text_hash=source_hash,
                translated_chunks=translated_chunks,
                total_chunks=len(chunks),
                provider="openai",
                model=self._model(),
                error_message=str(exc),
            )

    def _translate_text(self, text: str, target_language: str) -> str:
        chunks = self._chunk_text(text, max_chars=5500)
        translated_chunks = [
            self._translate_chunk(chunk=chunk, target_language=target_language, index=index + 1, total=len(chunks))
            for index, chunk in enumerate(chunks)
        ]
        return "\n\n".join(translated_chunks).strip()

    def _translate_chunk(self, chunk: str, target_language: str, index: int, total: int) -> str:
        api_key = self._api_key()
        if not api_key:
            raise ValueError("OPENAI_API_KEY or YCA_OPENAI_API_KEY is required for translation.")

        base_url = self._base_url().rstrip("/")
        payload = {
            "model": self._model(),
            "instructions": (
                "You are a professional subtitle translator. Translate YouTube recap subtitles into natural, "
                "readable Simplified Chinese. Preserve story meaning, names, plot beats, and paragraph breaks. "
                "Do not summarize. Do not add commentary."
            ),
            "input": f"Translate part {index}/{total} to {target_language}:\n\n{chunk}",
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        try:
            response = self._post_with_retries(f"{base_url}/responses", headers=headers, payload=payload)
        except httpx.HTTPError as exc:
            raise RuntimeError(f"OpenAI translation request failed: {exc}") from exc

        data = response.json()
        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        parsed = self._text_from_response_output(data)
        if parsed:
            return parsed
        raise RuntimeError("OpenAI translation response did not contain text output.")

    def _api_key(self) -> str:
        key = (
            self.workspace_settings.openai_api_key
            or self.settings.openai_api_key
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("YCA_OPENAI_API_KEY")
            or ""
        )
        if key:
            return key
        base_url = self._base_url().lower()
        if "localhost" in base_url or "127.0.0.1" in base_url:
            return "local-dev-key"
        return ""

    def _model(self) -> str:
        return self.workspace_settings.openai_translation_model or self.settings.openai_translation_model

    def _base_url(self) -> str:
        return self.workspace_settings.openai_base_url or self.settings.openai_base_url

    def _post_with_retries(self, url: str, headers: dict[str, str], payload: dict[str, Any]) -> httpx.Response:
        max_attempts = 3
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = httpx.post(url, headers=headers, json=payload, timeout=120.0)
                if response.status_code in {408, 409, 425, 429} or 500 <= response.status_code < 600:
                    if attempt < max_attempts:
                        time.sleep(1.5 * attempt)
                        continue
                response.raise_for_status()
                return response
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
                last_error = exc
                if attempt < max_attempts:
                    time.sleep(1.5 * attempt)
                    continue
                raise
        if last_error:
            raise last_error
        raise RuntimeError("OpenAI translation request failed after retries.")

    def _chunk_text(self, text: str, max_chars: int) -> list[str]:
        paragraphs = [paragraph.strip() for paragraph in text.splitlines() if paragraph.strip()]
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0

        for paragraph in paragraphs:
            paragraph_len = len(paragraph) + 1
            if current and current_len + paragraph_len > max_chars:
                chunks.append("\n".join(current))
                current = []
                current_len = 0
            if paragraph_len > max_chars:
                chunks.extend(paragraph[i : i + max_chars] for i in range(0, len(paragraph), max_chars))
                continue
            current.append(paragraph)
            current_len += paragraph_len

        if current:
            chunks.append("\n".join(current))
        return chunks or [text]

    def _text_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _text_from_response_output(self, data: dict[str, Any]) -> str:
        parts: list[str] = []
        output = data.get("output")
        if not isinstance(output, list):
            return ""
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for content_item in content:
                if isinstance(content_item, dict) and isinstance(content_item.get("text"), str):
                    parts.append(content_item["text"])
        return "\n".join(parts).strip()
