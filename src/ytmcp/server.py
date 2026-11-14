"""MCP server entry point.

Run with:  python -m ytmcp.server
Currently serves sample data from the FixtureProvider; this switches to
the live provider once it exists.
"""

import os
from pathlib import Path
from typing import Any

try:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as MCPServer

from ytmcp.providers.base import VideoProvider
from ytmcp.providers.fixture import FixtureProvider
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


def main() -> None:
    create_server(FixtureProvider(_default_fixtures_dir())).run()


if __name__ == "__main__":
    main()