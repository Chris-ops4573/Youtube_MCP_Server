"""MCP server entry point.

Run with:  python -m ytmcp.server

Provider is picked with YTMCP_PROVIDER (read from the environment or .env):
- "youtube" (default): live YouTube Data API, needs YOUTUBE_API_KEY
- "fixture": sample data from tests/fixtures (no API calls, no quota)

The live provider is wrapped in a SQLite cache (YTMCP_CACHE_PATH, default
.cache/ytmcp.db). Set YTMCP_CACHE=off to turn the cache off.
"""

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as MCPServer

from ytmcp.cache import Cache
from ytmcp.providers.base import VideoProvider
from ytmcp.providers.caching import CachingProvider
from ytmcp.providers.fixture import FixtureProvider
from ytmcp.providers.youtube import YouTubeProvider
from ytmcp.quota import QuotaTracker
from ytmcp.tools import similar_videos_tool


def create_server(provider: VideoProvider) -> Any:
    mcp = MCPServer("youtube-video-intelligence")

    @mcp.tool(name="find_similar_videos")
    def find_similar_videos_tool(video: str, top_n: int = 10) -> dict[str, Any]:
        """Find videos similar to a given YouTube video.

        Args:
            video: An 11-character video ID or a YouTube URL
                (watch, youtu.be, shorts or embed).
            top_n: How many results to return (1 to 50, default 10).

        Returns ranked results with title, channel, duration, score and URL,
        or an error with a code, message and remediation.
        """
        return similar_videos_tool(provider, video, top_n)

    return mcp


def _default_fixtures_dir() -> Path:
    env = os.environ.get("YTMCP_FIXTURES_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "tests" / "fixtures"


def _default_cache_path() -> Path:
    env = os.environ.get("YTMCP_CACHE_PATH")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / ".cache" / "ytmcp.db"


def build_provider() -> VideoProvider:
    """Pick the provider from YTMCP_PROVIDER. A missing API key is not fatal:
    the server still starts and tools return an API_KEY_MISSING error."""
    if os.environ.get("YTMCP_PROVIDER", "youtube").lower() == "fixture":
        return FixtureProvider(_default_fixtures_dir())
    api_key = os.environ.get("YOUTUBE_API_KEY") or None
    if os.environ.get("YTMCP_CACHE", "on").lower() == "off":
        return YouTubeProvider(api_key)
    cache = Cache(_default_cache_path())
    return CachingProvider(YouTubeProvider(api_key, quota=QuotaTracker(cache=cache)), cache)


def main() -> None:
    load_dotenv()  # reads .env if present; real environment variables win
    create_server(build_provider()).run()


if __name__ == "__main__":
    main()
