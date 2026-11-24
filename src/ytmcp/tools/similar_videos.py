"""The `find_similar_videos` tool logic, independent of the MCP SDK.

Kept as plain functions so it can be tested without a running server.
Output follows UI-1 (concise structured results) and UI-3 (stable error
code, plain message, remediation; never a stack trace).
"""

from typing import Any

from ytmcp.errors import YtmcpError
from ytmcp.providers.base import VideoProvider
from ytmcp.services import find_similar_videos
from ytmcp.similarity import ScoredVideo

MAX_TOP_N = 50


def video_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def format_duration(seconds: int) -> str:
    """Format seconds as M:SS, or H:MM:SS for an hour or more."""
    hours, rest = divmod(max(seconds, 0), 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_results(results: list[ScoredVideo]) -> list[dict[str, Any]]:
    return [
        {
            "rank": rank,
            "title": item.video.title,
            "channel": item.video.channel_title,
            "duration": format_duration(item.video.duration_seconds),
            "score": round(item.score, 3),
            "url": video_url(item.video.id),
            "score_breakdown": {k: round(v, 3) for k, v in vars(item.breakdown).items()},
            "low_confidence": item.low_confidence,
        }
        for rank, item in enumerate(results, start=1)
    ]


def error_response(
    code: str, message: str, remediation: str, fields: dict[str, str] | None = None
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message, "remediation": remediation}
    if fields:
        error["fields"] = fields
    return {"error": error}


def similar_videos_tool(provider: VideoProvider, video: str, top_n: int = 10) -> dict[str, Any]:
    """Run FR-1 and return either {"results": [...]} or {"error": {...}}."""
    if not 1 <= top_n <= MAX_TOP_N:
        return error_response(
            "INVALID_ARGUMENT",
            f"top_n must be between 1 and {MAX_TOP_N}.",
            f"Ask for between 1 and {MAX_TOP_N} results.",
        )
    try:
        results = find_similar_videos(provider, video, top_n=top_n)
    except ValueError:
        return error_response(
            "INVALID_VIDEO_REFERENCE",
            "That is not a valid YouTube video ID or URL.",
            "Use an 11-character video ID or a watch, youtu.be, shorts or embed URL.",
        )
    except YtmcpError as exc:
        return error_response(exc.code, str(exc), exc.remediation)
    return {"results": format_results(results)}