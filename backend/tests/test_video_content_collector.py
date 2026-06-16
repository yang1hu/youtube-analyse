from creator_agent.collectors.video_content import (
    _select_caption_track,
    _text_from_json_caption,
    _text_from_text_caption,
    _transcript_from_ytdlp_info,
)


def test_text_from_vtt_caption_removes_timing_and_markup():
    body = """WEBVTT

Kind: captions
Language: en

00:00:00.000 --> 00:00:02.000
<c>Hello</c> creator

00:00:02.000 --> 00:00:04.000
Hello creator

00:00:04.000 --> 00:00:06.000
Build the loop
"""

    assert _text_from_text_caption(body) == "Hello creator\nBuild the loop"


def test_text_from_json_caption_reads_youtube_events():
    body = """
    {
      "events": [
        {"segs": [{"utf8": "Start "}, {"utf8": "strong"}]},
        {"segs": [{"utf8": "Explain the mechanism"}]}
      ]
    }
    """

    assert _text_from_json_caption(body) == "Start strong\nExplain the mechanism"


def test_select_caption_track_prefers_manual_language_and_vtt():
    captions = {
        "zh": [{"ext": "json3", "url": "https://example.test/zh.json3"}],
        "en": [
            {"ext": "srv3", "url": "https://example.test/en.srv3"},
            {"ext": "vtt", "url": "https://example.test/en.vtt"},
        ],
    }

    track = _select_caption_track(captions, languages=("en", "zh"))

    assert track == {"url": "https://example.test/en.vtt", "language": "en"}


def test_transcript_from_ytdlp_info_prefers_manual_subtitles(monkeypatch):
    info = {
        "subtitles": {"en": [{"ext": "vtt", "url": "https://example.test/manual.vtt"}]},
        "automatic_captions": {"en": [{"ext": "vtt", "url": "https://example.test/auto.vtt"}]},
    }
    monkeypatch.setattr(
        "creator_agent.collectors.video_content._download_caption_text",
        lambda url: "Manual caption" if "manual" in url else "Auto caption",
    )

    transcript = _transcript_from_ytdlp_info(info, languages=("en",))

    assert transcript == {"text": "Manual caption", "source": "yt-dlp_subtitle", "language": "en"}
