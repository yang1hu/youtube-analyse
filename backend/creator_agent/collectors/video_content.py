import json
import re
from html import unescape
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

YOUTUBE_BASE_URL = "https://www.youtube.com"
DEFAULT_TRANSCRIPT_LANGUAGES = ("en", "en-US", "zh-Hans", "zh-CN", "zh")


class VideoContentUnavailable(RuntimeError):
    """Raised when metadata or transcript collection cannot complete."""


def collect_video_content(
    video_url: str | None = None,
    video_id: str | None = None,
    languages: tuple[str, ...] = DEFAULT_TRANSCRIPT_LANGUAGES,
) -> dict[str, Any]:
    resolved_video_id = _resolve_video_id(video_url=video_url, video_id=video_id)
    resolved_url = video_url or f"{YOUTUBE_BASE_URL}/watch?v={resolved_video_id}"
    info = _extract_info_with_ytdlp(resolved_url)

    transcript = _transcript_from_ytdlp_info(info, languages=languages)
    transcript_source = transcript.get("source", "")
    transcript_text = str(transcript.get("text") or "").strip()
    transcript_language = str(transcript.get("language") or "")

    if not transcript_text:
        fallback = _transcript_from_api(resolved_video_id, languages=languages)
        transcript_source = fallback.get("source", "")
        transcript_text = str(fallback.get("text") or "").strip()
        transcript_language = str(fallback.get("language") or "")

    return {
        "status": "ready" if transcript_text else "unavailable",
        "video_id": resolved_video_id,
        "video_url": resolved_url,
        "title": str(info.get("title") or ""),
        "description": str(info.get("description") or ""),
        "duration_seconds": info.get("duration"),
        "view_count": int(info.get("view_count") or 0),
        "channel": {
            "id": str(info.get("channel_id") or ""),
            "title": str(info.get("channel") or info.get("uploader") or ""),
            "url": str(info.get("channel_url") or ""),
        },
        "transcript_text": transcript_text,
        "transcript_source": transcript_source or "unavailable",
        "language": transcript_language,
        "collection_source": "yt-dlp",
    }


def _extract_info_with_ytdlp(video_url: str) -> dict[str, Any]:
    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise VideoContentUnavailable("yt-dlp is not installed.") from exc

    options = {
        "extract_flat": False,
        "noplaylist": True,
        "quiet": True,
        "skip_download": True,
        "writesubtitles": False,
        "writeautomaticsub": False,
        "no_warnings": True,
    }

    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(video_url, download=False)
    except Exception as exc:
        raise VideoContentUnavailable(str(exc)) from exc

    if not isinstance(info, dict):
        raise VideoContentUnavailable("yt-dlp returned empty video info.")
    return info


def _transcript_from_ytdlp_info(info: dict[str, Any], languages: tuple[str, ...]) -> dict[str, str]:
    manual = _select_caption_track(info.get("subtitles"), languages=languages)
    if manual:
        text = _download_caption_text(manual["url"])
        if text:
            return {"text": text, "source": "yt-dlp_subtitle", "language": manual["language"]}

    automatic = _select_caption_track(info.get("automatic_captions"), languages=languages)
    if automatic:
        text = _download_caption_text(automatic["url"])
        if text:
            return {"text": text, "source": "yt-dlp_auto_subtitle", "language": automatic["language"]}

    return {"text": "", "source": "", "language": ""}


def _select_caption_track(captions: Any, languages: tuple[str, ...]) -> dict[str, str] | None:
    if not isinstance(captions, dict):
        return None

    language_keys = list(languages) + [key for key in captions if key not in languages]
    for language in language_keys:
        tracks = captions.get(language)
        if not isinstance(tracks, list):
            continue
        for extension in ("vtt", "srv3", "json3", "ttml"):
            for track in tracks:
                if not isinstance(track, dict):
                    continue
                url = str(track.get("url") or "")
                if url and str(track.get("ext") or "").lower() == extension:
                    return {"url": url, "language": language}
        for track in tracks:
            if isinstance(track, dict) and track.get("url"):
                return {"url": str(track["url"]), "language": language}

    return None


def _download_caption_text(url: str) -> str:
    try:
        response = httpx.get(url, timeout=20.0, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError:
        return ""

    content_type = response.headers.get("content-type", "")
    body = response.text
    if "json" in content_type or body.lstrip().startswith("{"):
        return _text_from_json_caption(body)
    return _text_from_text_caption(body)


def _text_from_json_caption(body: str) -> str:
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return ""

    events = data.get("events") if isinstance(data, dict) else []
    lines: list[str] = []
    if not isinstance(events, list):
        return ""

    for event in events:
        segments = event.get("segs") if isinstance(event, dict) else []
        if not isinstance(segments, list):
            continue
        line = "".join(str(segment.get("utf8") or "") for segment in segments if isinstance(segment, dict)).strip()
        if line:
            lines.append(line)

    return _normalize_caption_text("\n".join(lines))


def _text_from_text_caption(body: str) -> str:
    lines: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line.upper() == "WEBVTT" or "-->" in line:
            continue
        if line.startswith(("Kind:", "Language:")):
            continue
        if re.fullmatch(r"\d+", line):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if line:
            lines.append(unescape(line))

    return _normalize_caption_text("\n".join(lines))


def _normalize_caption_text(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    deduped: list[str] = []
    for line in lines:
        if line and (not deduped or deduped[-1] != line):
            deduped.append(line)
    return "\n".join(deduped)


def _transcript_from_api(video_id: str, languages: tuple[str, ...]) -> dict[str, str]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return {"text": "", "source": "", "language": ""}

    try:
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=list(languages))
        else:
            transcript_result = YouTubeTranscriptApi().fetch(video_id, languages=list(languages))
            transcript = transcript_result.to_raw_data()
    except Exception:
        return {"text": "", "source": "", "language": ""}

    if not isinstance(transcript, list):
        return {"text": "", "source": "", "language": ""}

    text = "\n".join(str(item.get("text") or "").strip() for item in transcript if isinstance(item, dict))
    return {
        "text": _normalize_caption_text(text),
        "source": "youtube_transcript_api",
        "language": languages[0] if languages else "",
    }


def _resolve_video_id(video_url: str | None, video_id: str | None) -> str:
    if video_id:
        return video_id
    if not video_url:
        return "manual-video"

    parsed_url = urlparse(video_url)
    query_video_id = parse_qs(parsed_url.query).get("v", [None])[0]
    if query_video_id:
        return query_video_id

    return parsed_url.path.rstrip("/").split("/")[-1] or "manual-video"
