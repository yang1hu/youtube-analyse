from creator_agent.tools.channel_history import get_channel_profile, get_channel_recent_videos
from creator_agent.tools.comments import collect_comments
from creator_agent.tools.metrics import compute_video_metrics
from creator_agent.tools.registry import ToolDefinition, ToolRegistry
from creator_agent.tools.transcript import get_transcript
from creator_agent.tools.youtube_metadata import get_video_metadata


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register("get_video_metadata", "Fetch or stub YouTube video metadata.", get_video_metadata)
    registry.register("get_channel_recent_videos", "Fetch or stub recent channel videos.", get_channel_recent_videos)
    registry.register("get_transcript", "Fetch or stub a video transcript.", get_transcript)
    registry.register("get_comments", "Fetch or stub video comments.", collect_comments)
    registry.register("get_channel_profile", "Fetch or stub a channel profile.", get_channel_profile)
    registry.register("compute_video_metrics", "Compute deterministic video metrics.", compute_video_metrics)
    return registry


__all__ = [
    "ToolDefinition",
    "ToolRegistry",
    "build_default_registry",
]
