import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from creator_agent.config import Settings
from creator_agent.collectors.video_content import VideoContentUnavailable, collect_video_content
from creator_agent.services.transcript_store import TranscriptStore

OPENING_SECONDS = 300
FRAME_INTERVAL_SECONDS = 5
MAX_FRAMES = OPENING_SECONDS // FRAME_INTERVAL_SECONDS
FALLBACK_OPENING_CHARS = 6500


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class SampleAnalysisService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.cache_dir = Path(self.settings.sample_cache_dir)

    def analyze_video_opening(self, video_url: str, video_title: str = "", video_id: str = "") -> dict[str, Any]:
        if not video_url.strip():
            raise ValueError("Video URL is required.")

        resolved_id = video_id or self._video_id_from_url(video_url)
        sample_id = f"sample-{resolved_id or self._safe_id(video_url)}"
        content = self._opening_script_content(video_url=video_url, video_id=resolved_id)
        resolved_id = str(content.get("video_id") or resolved_id)
        video_title = str(content.get("title") or video_title or "Untitled video")
        opening_script = self._first_five_minute_script(
            raw_text=str(content.get("raw_text") or ""),
            duration_seconds=self._as_int(content.get("duration_seconds")),
        )
        analysis = self._build_story_script_analysis(
            video_title=video_title,
            opening_script=opening_script,
            transcript_source=str(content.get("transcript_source") or "unavailable"),
        )

        return {
            "id": sample_id,
            "video_id": resolved_id,
            "video_url": video_url,
            "video_title": video_title,
            "status": "complete",
            "analyzed_seconds": OPENING_SECONDS,
            "analysis_basis": "first_five_minute_script",
            "transcript_source": content.get("transcript_source") or "unavailable",
            "transcript_language": content.get("language") or "",
            "opening_transcript": opening_script,
            "opening_transcript_length": len(opening_script),
            "frame_interval_seconds": FRAME_INTERVAL_SECONDS,
            "frame_count": 0,
            "frames": [],
            **analysis,
            "created_at": utc_now_iso(),
        }

    def _opening_script_content(self, video_url: str, video_id: str) -> dict[str, Any]:
        cached = TranscriptStore(self.settings).get_transcript(video_id) if video_id else None
        if cached and str(cached.get("raw_text") or "").strip():
            return {
                "video_id": cached.get("video_id") or video_id,
                "title": cached.get("title") or "",
                "raw_text": cached.get("raw_text") or "",
                "transcript_source": cached.get("transcript_source") or "cache",
                "language": cached.get("language") or "",
                "duration_seconds": None,
            }

        try:
            content = collect_video_content(video_url=video_url, video_id=video_id)
        except (RuntimeError, VideoContentUnavailable) as exc:
            return {
                "video_id": video_id,
                "title": "",
                "raw_text": "",
                "transcript_source": "unavailable",
                "language": "",
                "duration_seconds": None,
                "error_message": str(exc),
            }

        raw_text = str(content.get("transcript_text") or "")
        resolved_id = str(content.get("video_id") or video_id)
        title = str(content.get("title") or "")
        if raw_text.strip() and resolved_id:
            TranscriptStore(self.settings).save_transcript(
                video_id=resolved_id,
                video_url=video_url,
                title=title,
                source=str(content.get("transcript_source") or "yt-dlp"),
                language=str(content.get("language") or ""),
                raw_text=raw_text,
            )
        return {
            "video_id": resolved_id,
            "title": title,
            "raw_text": raw_text,
            "transcript_source": content.get("transcript_source") or "unavailable",
            "language": content.get("language") or "",
            "duration_seconds": content.get("duration_seconds"),
        }

    def _first_five_minute_script(self, raw_text: str, duration_seconds: int | None = None) -> str:
        text = self._normalize_script_text(raw_text)
        if not text:
            return ""
        if duration_seconds and duration_seconds > OPENING_SECONDS:
            ratio = min(1.0, OPENING_SECONDS / duration_seconds)
            target_chars = max(FALLBACK_OPENING_CHARS, int(len(text) * ratio))
        else:
            target_chars = min(len(text), FALLBACK_OPENING_CHARS)
        target_chars = min(len(text), target_chars)
        if target_chars == len(text):
            return text
        boundary = text.rfind("\n", 0, target_chars)
        if boundary < target_chars * 0.65:
            boundary = text.rfind(". ", 0, target_chars)
        if boundary < target_chars * 0.65:
            boundary = target_chars
        return text[:boundary].strip()

    def _normalize_script_text(self, raw_text: str) -> str:
        lines = [re.sub(r"\s+", " ", line).strip() for line in raw_text.splitlines()]
        return "\n".join(line for line in lines if line)

    def _build_story_script_analysis(
        self,
        *,
        video_title: str,
        opening_script: str,
        transcript_source: str,
    ) -> dict[str, Any]:
        if not opening_script:
            return {
                "visual_summary": "No transcript was available for the first five minutes, so this sample needs a rerun after transcript collection succeeds.",
                "opening_hook": f"Use '{video_title}' as the title promise, then rerun sample analysis once captions are available.",
                "story_setup": "",
                "protagonist_position": "",
                "first_conflict": "",
                "first_turning_point": "",
                "retention_drivers": [],
                "hook_sequence": [],
                "pacing_notes": ["Transcript unavailable; avoid judging story structure from frames alone."],
                "reuse_template": ["Start from the first 5 minutes of script before extracting a reusable story pattern."],
                "risk_notes": ["Do not infer detailed plot mechanics from visual frames without script evidence."],
            }

        sentences = self._script_sentences(opening_script)
        first_lines = sentences[:8]
        conflict = self._first_matching_sentence(
            sentences,
            [
                "but",
                "however",
                "suddenly",
                "until",
                "betrayed",
                "humiliated",
                "refused",
                "sealed",
                "die",
                "killed",
                "villain",
                "system",
                "truth",
                "regret",
            ],
        )
        turning_point = self._first_matching_sentence(
            sentences[2:],
            ["suddenly", "then", "that was when", "but", "until", "system", "truth", "realized", "revealed"],
        )
        setup = " ".join(first_lines[:3]).strip()
        protagonist_position = self._first_person_position(sentences) or (first_lines[0] if first_lines else "")
        hook_sequence = [item for item in [*first_lines[:4], conflict, turning_point] if item]
        hook_sequence = self._unique_text(hook_sequence)[:6]

        return {
            "visual_summary": (
                f"Script-first sample from the first 5 minutes ({len(opening_script)} chars, source: {transcript_source}). "
                "Use this to judge the opening promise, first conflict, information gap, and early retention turns."
            ),
            "opening_hook": self._opening_hook_from_script(video_title, setup, conflict),
            "story_setup": setup,
            "protagonist_position": protagonist_position,
            "first_conflict": conflict,
            "first_turning_point": turning_point,
            "retention_drivers": self._retention_drivers(opening_script, conflict, turning_point),
            "hook_sequence": hook_sequence,
            "pacing_notes": self._story_pacing_notes(sentences, conflict, turning_point),
            "reuse_template": self._story_reuse_template(conflict, turning_point),
            "risk_notes": [
                "Reuse the opening mechanism, not the original names, exact plot events, dialogue, or scene order.",
                "For story recap channels, keep the first 5 minutes focused on setup, conflict, first payoff, and an unresolved question.",
                "Validate the template against the transcript before using frames as evidence.",
            ],
        }

    def _script_sentences(self, text: str) -> list[str]:
        collapsed = re.sub(r"\s+", " ", text).strip()
        parts = re.split(r"(?<=[.!?。！？])\s+", collapsed)
        sentences = [part.strip(" -") for part in parts if len(part.strip(" -")) > 20]
        if len(sentences) <= 1:
            sentences = [line.strip() for line in text.splitlines() if len(line.strip()) > 20]
        return sentences

    def _first_matching_sentence(self, sentences: list[str], keywords: list[str]) -> str:
        lowered_keywords = [keyword.lower() for keyword in keywords]
        for sentence in sentences:
            normalized = sentence.lower()
            if any(keyword in normalized for keyword in lowered_keywords):
                return sentence
        return sentences[0] if sentences else ""

    def _first_person_position(self, sentences: list[str]) -> str:
        for sentence in sentences[:12]:
            normalized = sentence.lower()
            if any(marker in normalized for marker in [" i ", " my ", " me ", " he ", " she ", "kai", "protagonist"]):
                return sentence
        return ""

    def _opening_hook_from_script(self, video_title: str, setup: str, conflict: str) -> str:
        if conflict:
            return (
                f"The title promises '{video_title}'. The opening first establishes the situation, then quickly creates a conflict: "
                f"{conflict}"
            )
        return f"The title promises '{video_title}'. The opening establishes the situation first: {setup}"

    def _retention_drivers(self, script: str, conflict: str, turning_point: str) -> list[str]:
        drivers: list[str] = []
        lowered = script.lower()
        if any(word in lowered for word in ["system", "reborn", "regression", "transmigrated", "villainess"]):
            drivers.append("Fantasy mechanism or identity twist appears early.")
        if any(word in lowered for word in ["truth", "secret", "hidden", "revealed", "realized"]):
            drivers.append("Information gap is used to make viewers wait for the truth reveal.")
        if any(word in lowered for word in ["betrayed", "humiliated", "refused", "sealed", "die", "killed"]):
            drivers.append("A strong injustice or danger creates immediate emotional stakes.")
        if conflict:
            drivers.append("The first conflict arrives inside the opening sample instead of waiting for later context.")
        if turning_point and turning_point != conflict:
            drivers.append("A second turn upgrades the promise before the five-minute mark.")
        return drivers or ["The opening needs a clearer conflict, information gap, or first payoff to strengthen retention."]

    def _story_pacing_notes(self, sentences: list[str], conflict: str, turning_point: str) -> list[str]:
        notes = [
            f"Opening sample contains about {len(sentences)} story beats/sentences after caption cleanup.",
            "Check whether the first 30-60 seconds state the premise before moving into backstory.",
        ]
        if conflict:
            notes.append("First conflict signal: " + conflict)
        if turning_point and turning_point != conflict:
            notes.append("Early turning point: " + turning_point)
        notes.append("For story channels, judge pacing by setup -> conflict -> information gap -> first payoff, not by frame count.")
        return notes

    def _story_reuse_template(self, conflict: str, turning_point: str) -> list[str]:
        template = [
            "Open with the title promise and the protagonist's vulnerable position.",
            "Introduce the first conflict or injustice before explaining too much backstory.",
            "Create an information gap: what does the protagonist know, hide, or misunderstand?",
        ]
        if conflict:
            template.append("Use a concrete first conflict as the first retention anchor.")
        if turning_point:
            template.append("Add a second turn before minute five so the premise feels like it is escalating.")
        template.append("End the sample with an unresolved question, stronger enemy, or upgraded mission.")
        return template

    def _unique_text(self, values: list[str]) -> list[str]:
        items: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = re.sub(r"\s+", " ", value).strip()
            key = normalized.lower()
            if normalized and key not in seen:
                items.append(normalized)
                seen.add(key)
        return items

    def _as_int(self, value: Any) -> int | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def _download_opening_clip(self, video_url: str, sample_dir: Path) -> dict[str, Any]:
        try:
            from yt_dlp import YoutubeDL
            from yt_dlp.utils import download_range_func
        except ImportError as exc:
            raise RuntimeError("yt-dlp is required for sample video analysis.") from exc

        output_template = str(sample_dir / "opening.%(ext)s")
        options = {
            "format": "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
            "outtmpl": output_template,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "force_keyframes_at_cuts": True,
            "download_ranges": download_range_func(None, [(0, OPENING_SECONDS)]),
        }

        try:
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(video_url, download=True)
        except Exception as exc:
            raise RuntimeError(f"Unable to download the first five minutes: {exc}") from exc

        media_path = self._find_downloaded_media(sample_dir)
        if media_path is None:
            raise RuntimeError("The opening clip was not created.")

        return {
            "video_id": str(info.get("id") or ""),
            "video_title": str(info.get("title") or ""),
            "media_path": media_path,
            "duration_seconds": info.get("duration"),
        }

    def _download_low_res_video(self, video_url: str, sample_dir: Path) -> dict[str, Any]:
        try:
            from yt_dlp import YoutubeDL
        except ImportError as exc:
            raise RuntimeError("yt-dlp is required for sample video analysis.") from exc

        output_template = str(sample_dir / "low-res.%(ext)s")
        options = {
            "format": "best[height<=240]/worst[height<=360]/worst",
            "format_sort": ["res:240", "ext:mp4:m4a"],
            "outtmpl": output_template,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "http_chunk_size": 1_048_576,
            "retries": 5,
            "fragment_retries": 5,
            "socket_timeout": 30,
        }

        try:
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(video_url, download=True)
        except Exception as exc:
            raise RuntimeError(f"Unable to download a temporary low-res sample video: {exc}") from exc

        media_path = self._find_downloaded_media(sample_dir)
        if media_path is None:
            raise RuntimeError("The temporary low-res sample video was not created.")

        return {
            "video_id": str(info.get("id") or ""),
            "video_title": str(info.get("title") or ""),
            "media_path": media_path,
            "duration_seconds": info.get("duration"),
        }

    def _extract_stream_info(self, video_url: str) -> dict[str, Any]:
        try:
            from yt_dlp import YoutubeDL
        except ImportError as exc:
            raise RuntimeError("yt-dlp is required for sample video analysis.") from exc

        try:
            with YoutubeDL({"quiet": True, "no_warnings": True, "noplaylist": True}) as ydl:
                info = ydl.extract_info(video_url, download=False)
        except Exception as exc:
            raise RuntimeError(f"Unable to inspect video stream for frame extraction: {exc}") from exc

        if not isinstance(info, dict):
            raise RuntimeError("yt-dlp returned empty stream information.")

        stream = self._select_video_stream(info)
        if not stream:
            raise RuntimeError("No playable video stream is available for frame extraction.")

        return {
            "video_id": str(info.get("id") or ""),
            "video_title": str(info.get("title") or ""),
            "stream_url": stream["url"],
            "http_headers": stream.get("http_headers") or info.get("http_headers") or {},
        }

    def _select_video_stream(self, info: dict[str, Any]) -> dict[str, Any] | None:
        formats = info.get("formats") if isinstance(info.get("formats"), list) else []
        candidates: list[dict[str, Any]] = []
        for item in formats:
            if not isinstance(item, dict):
                continue
            if not item.get("url") or item.get("vcodec") in {None, "none"}:
                continue
            height = item.get("height")
            try:
                height_value = int(height or 0)
            except (TypeError, ValueError):
                height_value = 0
            candidates.append({**item, "_height_value": height_value})

        if not candidates and isinstance(info.get("url"), str):
            return {"url": info["url"], "http_headers": info.get("http_headers") or {}}

        under_limit = [item for item in candidates if 0 < item["_height_value"] <= 480]
        pool = under_limit or candidates
        if not pool:
            return None
        return max(pool, key=lambda item: (int(item.get("_height_value") or 0), int(item.get("tbr") or 0)))

    def _extract_frames(self, media_path: Path, frames_dir: Path) -> list[dict[str, Any]]:
        frames_dir.mkdir(parents=True, exist_ok=True)
        for old_frame in frames_dir.glob("frame-*.jpg"):
            old_frame.unlink()

        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(media_path),
            "-t",
            str(OPENING_SECONDS),
            "-vf",
            f"fps=1/{FRAME_INTERVAL_SECONDS}",
            "-frames:v",
            str(MAX_FRAMES),
            str(frames_dir / "frame-%04d.jpg"),
        ]
        try:
            result = subprocess.run(command, capture_output=True, check=False, text=True, timeout=180)
        except FileNotFoundError as exc:
            raise RuntimeError("ffmpeg is required for sample frame extraction.") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("ffmpeg timed out while extracting sample frames.") from exc

        if result.returncode != 0:
            message = (result.stderr or result.stdout or "unknown ffmpeg error").strip()
            raise RuntimeError(f"Unable to extract sample frames: {message}")

        frames: list[dict[str, Any]] = []
        for index, frame_path in enumerate(sorted(frames_dir.glob("frame-*.jpg"))):
            frames.append(
                {
                    "timestamp_seconds": index * FRAME_INTERVAL_SECONDS,
                    "path": str(frame_path),
                }
            )
        if not frames:
            raise RuntimeError("No frames were extracted from the opening clip.")
        return frames

    def _extract_frames_from_stream(
        self,
        stream_url: str,
        frames_dir: Path,
        http_headers: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        frames_dir.mkdir(parents=True, exist_ok=True)
        for old_frame in frames_dir.glob("frame-*.jpg"):
            old_frame.unlink()

        command = ["ffmpeg", "-y", "-loglevel", "error"]
        headers = self._ffmpeg_headers(http_headers or {})
        if headers:
            command.extend(["-headers", headers])
        command.extend(
            [
                "-ss",
                "0",
                "-t",
                str(OPENING_SECONDS),
                "-i",
                stream_url,
                "-vf",
                f"fps=1/{FRAME_INTERVAL_SECONDS}",
                "-frames:v",
                str(MAX_FRAMES),
                str(frames_dir / "frame-%04d.jpg"),
            ]
        )
        try:
            result = subprocess.run(command, capture_output=True, check=False, text=True, timeout=240)
        except FileNotFoundError as exc:
            raise RuntimeError("ffmpeg is required for sample frame extraction.") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("ffmpeg timed out while extracting sample frames from the stream.") from exc

        if result.returncode != 0:
            message = (result.stderr or result.stdout or "unknown ffmpeg error").strip()
            raise RuntimeError(f"Unable to extract sample frames from stream: {message}")

        frames: list[dict[str, Any]] = []
        for index, frame_path in enumerate(sorted(frames_dir.glob("frame-*.jpg"))):
            frames.append({"timestamp_seconds": index * FRAME_INTERVAL_SECONDS, "path": str(frame_path)})
        if not frames:
            raise RuntimeError("No frames were extracted from the video stream.")
        return frames

    def _ffmpeg_headers(self, headers: dict[str, str]) -> str:
        if not headers:
            return ""
        return "".join(f"{key}: {value}\r\n" for key, value in headers.items() if value)

    def _build_rule_analysis(self, video_title: str, frame_count: int) -> dict[str, Any]:
        cut_density = "high" if frame_count >= 45 else "medium" if frame_count >= 20 else "low"
        return {
            "visual_summary": (
                f"Captured {frame_count} frames from the first 5 minutes. "
                f"The visible pacing signal is {cut_density}; use these frames to review scene changes, subtitle density, and promise delivery."
            ),
            "opening_hook": (
                f"Use the first 5 minutes of '{video_title}' to identify how the video pays off the title promise, "
                "where the first conflict appears, and whether visual proof arrives before explanation."
            ),
            "pacing_notes": [
                "Review frame-to-frame changes to estimate cut rhythm and visual novelty.",
                "Check whether large captions or highlighted keywords carry the core promise.",
                "Look for the first escalation point before minute five.",
            ],
            "reuse_template": [
                "Open with the consequence or strongest contrast before explaining context.",
                "Show visual proof early so the title promise feels real.",
                "Escalate the conflict every 30-60 seconds with a new reveal or higher stake.",
                "End the first 5 minutes with an unresolved question or upgraded promise.",
            ],
            "risk_notes": [
                "Use the structure and pacing pattern, not the exact frames, subtitles, characters, or scene order.",
                "Keep this as a local research asset and avoid batch downloading many videos.",
            ],
        }

    def _find_downloaded_media(self, sample_dir: Path) -> Path | None:
        candidates = [
            path
            for path in sample_dir.iterdir()
            if path.is_file() and path.suffix.lower() not in {".part", ".ytdl", ".json", ".jpg", ".webp"}
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda path: path.stat().st_mtime)

    def _video_id_from_url(self, video_url: str) -> str:
        match = re.search(r"[?&]v=([^&]+)", video_url)
        if match:
            return self._safe_id(match.group(1))
        return self._safe_id(video_url.rstrip("/").split("/")[-1])

    def _safe_id(self, value: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")
        return safe[:80] or "manual-video"

    def clear_media_cache(self, sample_id: str) -> None:
        sample_dir = self.cache_dir / self._safe_id(sample_id)
        if sample_dir.exists():
            shutil.rmtree(sample_dir)
