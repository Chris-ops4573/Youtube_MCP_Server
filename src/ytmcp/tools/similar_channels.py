"""The `find_similar_channels` tool logic, independent of the MCP SDK.

Same output rules as the videos tool: concise structured results (UI-1) and
errors with a stable code, plain message and remediation (UI-3).
"""

from typing import Any

from ytmcp.channel_similarity import ScoredChannel
from ytmcp.errors import YtmcpError
from ytmcp.providers.base import VideoProvider
from ytmcp.services import find_similar_channels
from ytmcp.tools.similar_videos import MAX_TOP_N, error_response


def channel_url(channel_id: str) -> str:
    return f"https://www.youtube.com/channel/{channel_id}"


def format_channel_results(results: list[ScoredChannel]) -> list[dict[str, Any]]:
    formatted = []
    for rank, item in enumerate(results, start=1):
        channel = item.profile.channel
        formatted.append(
            {
                "rank": rank,
                "title": channel.title,
                "handle": channel.handle,
                "subscribers": "hidden" if channel.subscriber_count is None else channel.subscriber_count,
                "score": round(item.score, 3),
                "url": channel_url(channel.id),
                "score_breakdown": {k: round(v, 3) for k, v in vars(item.breakdown).items()},
                "low_confidence": item.low_confidence,
            }
        )
    return formatted


def similar_channels_tool(provider: VideoProvider, channel: str, top_n: int = 10) -> dict[str, Any]:
    """Run FR-2 and return either {"results": [...]} or {"error": {...}}."""
    if not 1 <= top_n <= MAX_TOP_N:
        return error_response(
            "INVALID_ARGUMENT",
            f"top_n must be between 1 and {MAX_TOP_N}.",
            f"Ask for between 1 and {MAX_TOP_N} results.",
        )
    try:
        results = find_similar_channels(provider, channel, top_n=top_n)
    except ValueError:
        return error_response(
            "INVALID_CHANNEL_REFERENCE",
            "That is not a valid YouTube channel ID, @handle or URL.",
            "Use a channel ID starting with UC, an @handle, or a youtube.com/channel/... "
            "or youtube.com/@... URL.",
        )
    except YtmcpError as exc:
        return error_response(exc.code, str(exc), exc.remediation)
    return {"results": format_channel_results(results)}
