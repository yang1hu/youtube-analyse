from creator_agent.config import Settings
from creator_agent.services.workspace_store import WorkspaceStore


def test_create_video_sample_analysis_saves_first_five_minute_result(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    monkeypatch.setenv("YCA_SAMPLE_CACHE_DIR", str(tmp_path / "samples"))
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))

    def fake_analyze(self, video_url, video_title="", video_id=""):
        return {
            "id": "sample-1",
            "video_id": video_id or "abc123",
            "video_url": video_url,
            "video_title": video_title or "Five minute opening",
            "status": "complete",
            "analyzed_seconds": 300,
            "frame_count": 3,
            "frames": [
                {"timestamp_seconds": 0, "path": "samples/abc123/frames/frame-0001.jpg"},
                {"timestamp_seconds": 5, "path": "samples/abc123/frames/frame-0002.jpg"},
                {"timestamp_seconds": 10, "path": "samples/abc123/frames/frame-0003.jpg"},
            ],
            "visual_summary": "The opening uses fast cuts and large subtitles.",
            "opening_hook": "A problem is shown before the narrator explains the setup.",
            "pacing_notes": ["Cut every few seconds", "Key claims appear as on-screen text"],
            "reuse_template": ["Open with consequence", "Show proof", "Escalate the promise"],
            "risk_notes": ["Do not copy exact frames or subtitles."],
            "created_at": "2026-06-09T00:00:00+00:00",
        }

    monkeypatch.setattr(
        "creator_agent.services.sample_analysis_service.SampleAnalysisService.analyze_video_opening",
        fake_analyze,
    )

    result = WorkspaceStore(Settings()).create_sample_analysis(
        video_url="https://www.youtube.com/watch?v=abc123",
        video_title="Five minute opening",
        video_id="abc123",
    )
    samples = WorkspaceStore(Settings()).sample_analyses()

    assert result["status"] == "complete"
    assert result["analyzed_seconds"] == 300
    assert samples[0]["video_url"] == "https://www.youtube.com/watch?v=abc123"
    assert samples[0]["reuse_template"] == ["Open with consequence", "Show proof", "Escalate the promise"]


def test_sample_analysis_service_uses_transcript_without_downloading_video(tmp_path, monkeypatch):
    from creator_agent.services.sample_analysis_service import SampleAnalysisService

    def fail_download(*args, **kwargs):
        raise AssertionError("script-first sample analysis should not download video frames")

    monkeypatch.setattr(SampleAnalysisService, "_download_opening_clip", fail_download)
    monkeypatch.setattr(
        "creator_agent.services.sample_analysis_service.collect_video_content",
        lambda video_url=None, video_id=None: {
            "status": "ready",
            "video_id": "abc123",
            "title": "Opening sample",
            "transcript_text": "I was trapped in a doomed novel.\nBut the villainess did not know I remembered the ending.",
            "transcript_source": "yt-dlp_auto_subtitle",
            "language": "en",
            "duration_seconds": 900,
        },
    )

    service = SampleAnalysisService(
        Settings(
            sample_cache_dir=str(tmp_path / "samples"),
            transcript_cache_dir=str(tmp_path / "transcripts"),
        )
    )
    result = service.analyze_video_opening("https://www.youtube.com/watch?v=abc123")

    assert result["status"] == "complete"
    assert result["analyzed_seconds"] == 300
    assert result["analysis_basis"] == "first_five_minute_script"
    assert result["frame_count"] == 0
    assert result["opening_hook"]
    assert result["opening_transcript"]


def test_sample_analysis_service_uses_cached_transcript_before_collecting(tmp_path, monkeypatch):
    from creator_agent.services.sample_analysis_service import SampleAnalysisService
    from creator_agent.services.transcript_store import TranscriptStore

    settings = Settings(
        sample_cache_dir=str(tmp_path / "samples"),
        transcript_cache_dir=str(tmp_path / "transcripts"),
    )
    TranscriptStore(settings).save_transcript(
        video_id="abc123",
        video_url="https://www.youtube.com/watch?v=abc123",
        title="Opening sample",
        source="cache",
        language="en",
        raw_text="The prince sealed me away.\nBut I had already prepared the final reversal.",
    )
    monkeypatch.setattr(
        "creator_agent.services.sample_analysis_service.collect_video_content",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cached transcript should be used first")),
    )

    service = SampleAnalysisService(settings)
    result = service.analyze_video_opening("https://www.youtube.com/watch?v=abc123")

    assert result["status"] == "complete"
    assert result["video_title"] == "Opening sample"
    assert result["transcript_source"] == "cache"
    assert "sealed me away" in result["opening_transcript"]


def test_sample_analysis_service_handles_missing_transcript_without_frame_guessing(tmp_path, monkeypatch):
    from creator_agent.services.sample_analysis_service import SampleAnalysisService

    monkeypatch.setattr(
        "creator_agent.services.sample_analysis_service.collect_video_content",
        lambda video_url=None, video_id=None: {
            "status": "unavailable",
            "video_id": "abc123",
            "title": "Opening sample",
            "transcript_text": "",
            "transcript_source": "unavailable",
            "language": "",
            "duration_seconds": 900,
        },
    )

    service = SampleAnalysisService(
        Settings(
            sample_cache_dir=str(tmp_path / "samples"),
            transcript_cache_dir=str(tmp_path / "transcripts"),
        )
    )
    result = service.analyze_video_opening("https://www.youtube.com/watch?v=abc123")

    assert result["status"] == "complete"
    assert result["video_title"] == "Opening sample"
    assert result["frame_count"] == 0
    assert result["opening_transcript"] == ""
    assert "Transcript unavailable" in result["pacing_notes"][0]


def test_sample_analysis_service_uses_first_five_minute_script_for_story_analysis(tmp_path, monkeypatch):
    from creator_agent.services.sample_analysis_service import SampleAnalysisService

    monkeypatch.setattr(
        "creator_agent.services.sample_analysis_service.collect_video_content",
        lambda video_url=None, video_id=None: {
            "status": "ready",
            "video_id": "abc123",
            "title": "Story opening",
            "transcript_text": "I was a nobody until the system woke up.\nThen the villain forced me into the banquet.\nBut I already knew the ending.\n",
            "transcript_source": "yt-dlp_auto_subtitle",
            "language": "en",
            "duration_seconds": 900,
        },
    )

    service = SampleAnalysisService(Settings(sample_cache_dir=str(tmp_path / "samples")))
    result = service.analyze_video_opening("https://www.youtube.com/watch?v=abc123")

    assert result["analysis_basis"] == "first_five_minute_script"
    assert result["frame_count"] == 0
    assert result["opening_transcript"]
    assert result["story_setup"]
    assert result["first_conflict"]
    assert result["reuse_template"]
