import json
import os
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from creator_agent.config import Settings
from creator_agent.services.settings_service import WorkspaceSettingsService


YOUTUBE_BASE_URL = "https://www.youtube.com"


class BrowserCollectionUnavailable(RuntimeError):
    """Raised when browser collection cannot run in the current environment."""


def extract_yt_initial_data(html: str) -> dict[str, Any]:
    marker = "ytInitialData"
    marker_index = html.find(marker)
    if marker_index < 0:
        raise ValueError("ytInitialData not found in page HTML.")

    brace_index = html.find("{", marker_index)
    if brace_index < 0:
        raise ValueError("ytInitialData JSON object not found in page HTML.")

    decoder = json.JSONDecoder()
    data, _ = decoder.raw_decode(html[brace_index:])
    if not isinstance(data, dict):
        raise ValueError("ytInitialData is not a JSON object.")
    return data


def parse_video_metadata(
    initial_data: dict[str, Any],
    video_url: str | None,
    fallback_video_id: str,
) -> dict[str, Any]:
    primary = _first_value_for_key(initial_data, "videoPrimaryInfoRenderer") or {}
    secondary = _first_value_for_key(initial_data, "videoSecondaryInfoRenderer") or {}
    owner = _first_value_for_key(secondary, "videoOwnerRenderer") or {}
    owner_title = owner.get("title") if isinstance(owner, dict) else {}
    owner_run = _first_run(owner_title)
    browse_endpoint = _first_value_for_key(owner_run, "browseEndpoint") or {}

    title = _text_from(primary.get("title")) or "Untitled video"
    view_count_node = primary.get("viewCount") if isinstance(primary, dict) else {}
    view_count = _parse_count(_text_from(_first_value_for_key(view_count_node, "viewCount")))
    published_text = _text_from(primary.get("dateText"))

    channel_id = str(browse_endpoint.get("browseId") or "")
    canonical_path = str(browse_endpoint.get("canonicalBaseUrl") or "")
    channel_url = _absolute_youtube_url(canonical_path) if canonical_path else ""
    channel_title = _text_from(owner_title) or ""

    return {
        "youtube_video_id": fallback_video_id,
        "title": title,
        "url": video_url,
        "channel": {
            "id": channel_id,
            "title": channel_title,
            "url": channel_url,
        },
        "duration_seconds": None,
        "view_count": view_count,
        "like_count": 0,
        "comment_count": 0,
        "published_text": published_text,
        "collection_status": "ok",
        "collection_source": "browser",
    }


def parse_channel_recent_videos(initial_data: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    videos: list[dict[str, Any]] = []
    for renderer in _values_for_key(initial_data, "videoRenderer"):
        if not isinstance(renderer, dict):
            continue

        video_id = str(renderer.get("videoId") or "")
        if not video_id:
            continue

        videos.append(
            {
                "youtube_video_id": video_id,
                "title": _text_from(renderer.get("title")) or "Untitled video",
                "url": f"{YOUTUBE_BASE_URL}/watch?v={video_id}",
                "published_text": _text_from(renderer.get("publishedTimeText")),
                "view_count": _parse_count(_text_from(renderer.get("viewCountText"))),
            }
        )

        if len(videos) >= limit:
            break

    if len(videos) < limit:
        seen_video_ids = {video["youtube_video_id"] for video in videos}
        for lockup in _values_for_key(initial_data, "lockupViewModel"):
            if not isinstance(lockup, dict):
                continue

            video = _video_from_lockup_view_model(lockup)
            if not video or video["youtube_video_id"] in seen_video_ids:
                continue

            videos.append(video)
            seen_video_ids.add(video["youtube_video_id"])

            if len(videos) >= limit:
                break

    return videos


def _video_from_lockup_view_model(lockup: dict[str, Any]) -> dict[str, Any] | None:
    video_id = str(lockup.get("contentId") or "")
    if not video_id:
        watch_endpoint = _first_value_for_key(lockup, "watchEndpoint") or {}
        if isinstance(watch_endpoint, dict):
            video_id = str(watch_endpoint.get("videoId") or "")

    if not video_id:
        return None

    metadata = lockup.get("metadata") if isinstance(lockup.get("metadata"), dict) else {}
    lockup_metadata = metadata.get("lockupMetadataViewModel") if isinstance(metadata, dict) else {}
    if not isinstance(lockup_metadata, dict):
        lockup_metadata = {}

    title = _content_text(lockup_metadata.get("title")) or "Untitled video"
    metadata_parts = _lockup_metadata_parts(lockup_metadata)
    view_text = next((part for part in metadata_parts if "view" in part.lower()), "")
    published_text = next((part for part in metadata_parts if "ago" in part.lower()), "")

    return {
        "youtube_video_id": video_id,
        "title": title,
        "url": f"{YOUTUBE_BASE_URL}/watch?v={video_id}",
        "published_text": published_text,
        "view_count": _parse_count(view_text),
    }


def _lockup_metadata_parts(lockup_metadata: dict[str, Any]) -> list[str]:
    content_metadata = _first_value_for_key(lockup_metadata, "contentMetadataViewModel") or {}
    rows = content_metadata.get("metadataRows") if isinstance(content_metadata, dict) else []
    parts: list[str] = []

    if not isinstance(rows, list):
        return parts

    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("metadataParts"), list):
            continue
        for part in row["metadataParts"]:
            if isinstance(part, dict):
                text = _content_text(part.get("text")) or str(part.get("accessibilityLabel") or "")
                if text:
                    parts.append(text)

    return parts


def collect_video_metadata(video_url: str | None = None, video_id: str | None = None) -> dict[str, Any]:
    resolved_video_id = _resolve_video_id(video_url=video_url, video_id=video_id)
    resolved_url = video_url or f"{YOUTUBE_BASE_URL}/watch?v={resolved_video_id}"
    engine = _selected_browser_engine()
    html = collect_page_html(resolved_url)
    initial_data = extract_yt_initial_data(html)
    metadata = parse_video_metadata(
        initial_data=initial_data,
        video_url=resolved_url,
        fallback_video_id=resolved_video_id,
    )
    metadata["collection_source"] = f"browser:{engine}"
    return metadata


def collect_channel_recent_videos(channel_url: str, limit: int = 10) -> dict[str, Any]:
    engine = _selected_browser_engine()
    html = collect_page_html(_channel_videos_url(channel_url))
    initial_data = extract_yt_initial_data(html)
    videos = parse_channel_recent_videos(initial_data, limit=limit)
    return {
        "channel_url": channel_url,
        "limit": limit,
        "videos": videos,
        "collection_status": "ok" if videos else "empty",
        "collection_source": f"browser:{engine}",
        "collection_error": "" if videos else "No videos were parsed from the channel page. YouTube may have changed the page format or the channel may have no public videos.",
    }


def collect_channel_profile(channel_url: str) -> dict[str, Any]:
    engine = _selected_browser_engine()
    html = collect_page_html(channel_url)
    initial_data = extract_yt_initial_data(html)
    metadata = _first_value_for_key(initial_data, "metadata") or {}
    channel_metadata = metadata.get("channelMetadataRenderer") if isinstance(metadata, dict) else {}
    if not isinstance(channel_metadata, dict):
        channel_metadata = {}

    return {
        "channel_id": str(channel_metadata.get("externalId") or ""),
        "title": str(channel_metadata.get("title") or ""),
        "description": str(channel_metadata.get("description") or ""),
        "url": channel_url,
        "subscriber_count": 0,
        "avg_view_count": 0,
        "collection_status": "ok",
        "collection_source": f"browser:{engine}",
    }


def collect_page_html(url: str, engine: str | None = None) -> str:
    selected_engine = _selected_browser_engine(engine)
    if selected_engine == "playwright":
        return collect_page_html_with_playwright(url)
    if selected_engine in {"drission", "drissionpage"}:
        return collect_page_html_with_drission(url)
    if selected_engine == "cdp":
        return collect_page_html_with_cdp(url)
    raise BrowserCollectionUnavailable(f"Unsupported browser engine: {selected_engine}")


def _selected_browser_engine(engine: str | None = None) -> str:
    env_engine = os.getenv("YCA_BROWSER_ENGINE")
    selected_engine = (engine or env_engine or _browser_setting("browser_engine") or Settings().browser_engine).strip().lower()
    if selected_engine == "drissionpage":
        return "drission"
    return selected_engine


def _browser_setting(name: str) -> Any:
    try:
        return getattr(WorkspaceSettingsService().get(), name)
    except Exception:
        return getattr(Settings(), name, None)


def collect_page_html_with_playwright(url: str) -> str:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserCollectionUnavailable(
            "Playwright is not installed. Install the backend with browser dependencies first."
        ) from exc

    try:
        settings = WorkspaceSettingsService().get()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=settings.browser_headless)
            page = browser.new_page(locale="en-US")
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(1500)
            html = page.content()
            browser.close()
            return html
    except PlaywrightTimeoutError as exc:
        raise BrowserCollectionUnavailable(f"Timed out while loading {url}.") from exc
    except Exception as exc:
        raise BrowserCollectionUnavailable(str(exc)) from exc


def collect_page_html_with_cdp(url: str) -> str:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserCollectionUnavailable(
            "Playwright is not installed. Install the backend with browser dependencies first."
        ) from exc

    settings = WorkspaceSettingsService().get()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(settings.browser_cdp_url)
            context = browser.contexts[0] if browser.contexts else browser.new_context(locale="en-US")
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(1500)
            html = page.content()
            page.close()
            browser.close()
            return html
    except PlaywrightTimeoutError as exc:
        raise BrowserCollectionUnavailable(f"Timed out while loading {url}.") from exc
    except Exception as exc:
        raise BrowserCollectionUnavailable(str(exc)) from exc


def collect_page_html_with_drission(url: str) -> str:
    try:
        from DrissionPage import ChromiumOptions, ChromiumPage
    except ImportError as exc:
        raise BrowserCollectionUnavailable(
            "DrissionPage is not installed. Install the backend with browser dependencies first."
        ) from exc

    settings = WorkspaceSettingsService().get()
    try:
        options = ChromiumOptions()
        if settings.browser_path:
            options.set_browser_path(settings.browser_path)
        if settings.browser_debug_port:
            options.set_local_port(settings.browser_debug_port)
        if settings.browser_headless and hasattr(options, "headless"):
            options.headless(True)

        page = ChromiumPage(options)
        page.get(url)
        _wait_for_drission_page(page)
        html = str(page.html)
        _close_drission_page(page)
        return html
    except Exception as exc:
        raise BrowserCollectionUnavailable(str(exc)) from exc


def _wait_for_drission_page(page: Any) -> None:
    wait = getattr(page, "wait", None)
    if wait is not None:
        load_start = getattr(wait, "load_start", None)
        if callable(load_start):
            load_start(timeout=10)
        doc_loaded = getattr(wait, "doc_loaded", None)
        if callable(doc_loaded):
            doc_loaded(timeout=20)


def _close_drission_page(page: Any) -> None:
    close = getattr(page, "close", None)
    if callable(close):
        close()


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


def _channel_videos_url(channel_url: str) -> str:
    normalized = channel_url.rstrip("/")
    if normalized.endswith("/videos"):
        return normalized
    return f"{normalized}/videos"


def _absolute_youtube_url(path_or_url: str) -> str:
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    if path_or_url.startswith("/"):
        return f"{YOUTUBE_BASE_URL}{path_or_url}"
    return f"{YOUTUBE_BASE_URL}/{path_or_url}"


def _text_from(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""
    content = _content_text(value)
    if content:
        return content
    if isinstance(value.get("simpleText"), str):
        return value["simpleText"]
    runs = value.get("runs")
    if isinstance(runs, list):
        return "".join(str(run.get("text") or "") for run in runs if isinstance(run, dict))
    return ""


def _content_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and isinstance(value.get("content"), str):
        return value["content"]
    return ""


def _first_run(value: Any) -> dict[str, Any]:
    if isinstance(value, dict) and isinstance(value.get("runs"), list):
        for run in value["runs"]:
            if isinstance(run, dict):
                return run
    return {}


def _parse_count(text: str) -> int:
    cleaned = text.lower().replace(",", "").strip()
    if not cleaned or "no views" in cleaned:
        return 0
    compact_match = re.search(r"(\d+(?:\.\d+)?)\s*([kmb]|万|億|亿)?", cleaned)
    if not compact_match:
        return 0

    number = float(compact_match.group(1))
    suffix = compact_match.group(2)
    if suffix == "k":
        number *= 1_000
    elif suffix == "m":
        number *= 1_000_000
    elif suffix == "b":
        number *= 1_000_000_000
    elif suffix == "万":
        number *= 10_000
    elif suffix in {"億", "亿"}:
        number *= 100_000_000
    return int(number)


def _first_value_for_key(value: Any, key: str) -> Any:
    for found in _values_for_key(value, key):
        return found
    return None


def _values_for_key(value: Any, key: str) -> list[Any]:
    found: list[Any] = []
    queue = [value]

    while queue:
        current = queue.pop(0)
        if isinstance(current, dict):
            for item_key, item_value in current.items():
                if item_key == key:
                    found.append(item_value)
                if isinstance(item_value, dict | list):
                    queue.append(item_value)
        elif isinstance(current, list):
            queue.extend(current)

    return found
