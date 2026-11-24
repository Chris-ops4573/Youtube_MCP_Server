"""MCP server entry point.

Run with:  python -m ytmcp.server

Provider is picked with YTMCP_PROVIDER (read from the environment or .env):
- "youtube" (default): live YouTube Data API, needs YOUTUBE_API_KEY
- "fixture": sample data from tests/fixtures (no API calls, no quota)

The live provider is wrapped in a SQLite cache (YTMCP_CACHE_PATH, default
.cache/ytmcp.db). Set YTMCP_CACHE=off to turn the cache off. Playlist proposals
are always kept in that same database file, so a person can confirm one from a terminal.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as MCPServer

from mcp import types
from mcp.shared.exceptions import MCPError
from pydantic import BaseModel, Field

try:  # mcp 2.x
    from mcp.server.mcpserver import Context
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import Context

from ytmcp.cache import Cache, default_cache_path
from ytmcp.proposals import ProposalStore
from ytmcp.providers.base import PlaylistWriter, VideoProvider
from ytmcp.providers.caching import CachingProvider
from ytmcp.providers.fixture import FixtureProvider
from ytmcp.providers.playlists import YouTubePlaylistWriter
from ytmcp.providers.youtube import YouTubeProvider
from ytmcp.quota import QuotaTracker
from ytmcp.tools import (
    create_playlist_tool,
    propose_playlist_tool,
    similar_channels_tool,
    similar_videos_tool,
)
from ytmcp.tools.playlists import Answer


class ConfirmPlaylist(BaseModel):
    """The question shown to the user before a playlist is created."""

    confirm: bool = Field(default=False, description="Create this private playlist?")


async def ask_user(ctx: Any, message: str) -> Answer:
    """Ask the person directly through the client (elicitation). The answer comes from the
    client, not from the AI's own words. "unsupported" means we could not ask."""
    wanted = types.ClientCapabilities(
        elicitation=types.ElicitationCapability(form=types.FormElicitationCapability())
    )
    try:
        if not ctx.request_context.session.check_client_capability(wanted):
            return "unsupported"
    except ValueError:  # no client request is active, so there is nobody to ask
        return "unsupported"
    try:
        result = await ctx.elicit(message=message, schema=ConfirmPlaylist)
    except MCPError:  # the client does not really support it
        return "unsupported"
    except ValueError:  # the client sent an unusable answer: treat as "no"
        return "decline"
    return "accept" if result.action == "accept" and result.data.confirm else "decline"


def create_server(
    provider: VideoProvider,
    store: ProposalStore | None = None,
    writer: PlaylistWriter | None = None,
) -> Any:
    store = store or ProposalStore(Cache(":memory:"))
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

    @mcp.tool(name="find_similar_channels")
    def find_similar_channels_tool(channel: str, top_n: int = 10) -> dict[str, Any]:
        """Find YouTube channels similar to a given channel.

        Args:
            channel: A channel ID (starts with UC), an @handle, or a
                youtube.com/channel/... or youtube.com/@... URL.
            top_n: How many results to return (1 to 50, default 10).

        Returns ranked channels with title, handle, subscribers ("hidden" when
        the channel hides its count), score and URL, or an error with a code,
        message and remediation.
        """
        return similar_channels_tool(provider, channel, top_n)

    @mcp.tool(
        name="propose_playlist",
        annotations=types.ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=True
        ),
    )
    def propose_playlist_fn(
        topic: str,
        total_minutes: int,
        max_video_minutes: int | None = None,
        language: str | None = None,
        title: str | None = None,
        min_video_minutes: int | None = None,
    ) -> dict[str, Any]:
        """Plan a playlist of videos on a topic. Nothing is created on YouTube.

        Args:
            topic: What the playlist is about, for example "rust programming".
            total_minutes: Wanted total length in minutes (5 to 1440). The result will
                be within 10 percent of it when enough videos exist.
            max_video_minutes: Leave out videos longer than this (optional).
            min_video_minutes: Leave out videos shorter than this (optional). Use 3 or
                more to skip YouTube Shorts and other very short clips.
            language: Only videos in this language, for example "en" (optional).
            title: Playlist title (optional).

        Returns a proposal with proposal_id, content_hash, the videos, the total
        against the requested length, the longest video and notes about anything
        unmet. Show it to the user and ask before calling create_playlist.
        """
        return propose_playlist_tool(
            provider, store, topic, total_minutes, max_video_minutes, language, title,
            min_video_minutes,
        )

    @mcp.tool(
        name="create_playlist",
        annotations=types.ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,  # only ever creates a new private playlist
            idempotent_hint=False,
            open_world_hint=True,
        ),
    )
    async def create_playlist_fn(proposal_id: str, content_hash: str, ctx: Context) -> dict[str, Any]:
        """Create the private YouTube playlist from a proposal. Only call this after the
        user has agreed. The server asks the user itself before creating anything, and
        refuses if it cannot.

        Args:
            proposal_id: The proposal_id returned by propose_playlist.
            content_hash: The content_hash returned by propose_playlist, unchanged.

        Creates a new private playlist and adds the proposed videos. It never edits or
        deletes anything. Returns the playlist URL, or an error with a remediation.
        """

        async def ask(message: str) -> Answer:
            return await ask_user(ctx, message)

        return await create_playlist_tool(writer, store, proposal_id, content_hash, ask)

    return mcp


def _default_fixtures_dir() -> Path:
    env = os.environ.get("YTMCP_FIXTURES_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "tests" / "fixtures"


def build_provider(cache: Cache | None = None, quota: QuotaTracker | None = None) -> VideoProvider:
    """Pick the provider from YTMCP_PROVIDER. A missing API key is not fatal:
    the server still starts and tools return an API_KEY_MISSING error."""
    if os.environ.get("YTMCP_PROVIDER", "youtube").lower() == "fixture":
        return FixtureProvider(_default_fixtures_dir())
    api_key = os.environ.get("YOUTUBE_API_KEY") or None
    if os.environ.get("YTMCP_CACHE", "on").lower() == "off":
        return YouTubeProvider(api_key, quota=quota)
    cache = cache or Cache(default_cache_path())
    return CachingProvider(YouTubeProvider(api_key, quota=quota or QuotaTracker(cache=cache)), cache)


def _access_token(scope: str) -> str:
    """A valid Google login token for `scope`, built when needed so a missing OAuth setup
    only affects playlist creation."""
    from ytmcp.cli import build_auth_service  # imported here: cli imports a lot

    return build_auth_service().get_access_token(scope)


@dataclass
class Services:
    provider: VideoProvider
    store: ProposalStore
    writer: PlaylistWriter | None  # None in fixture mode: no real playlists


def build_services() -> Services:
    """Everything the server needs. Reads and writes share ONE quota counter, so the daily
    count is right. Proposals always go in the database file, even with the cache off,
    so a person can confirm one from a terminal."""
    cache = Cache(default_cache_path())
    store = ProposalStore(cache)
    if os.environ.get("YTMCP_PROVIDER", "youtube").lower() == "fixture":
        return Services(build_provider(), store, None)
    cache_on = os.environ.get("YTMCP_CACHE", "on").lower() != "off"
    quota = QuotaTracker(cache=cache) if cache_on else QuotaTracker()
    provider = build_provider(cache, quota)
    return Services(provider, store, YouTubePlaylistWriter(_access_token, quota))


def main() -> None:
    load_dotenv()  # reads .env if present; real environment variables win
    services = build_services()
    create_server(services.provider, services.store, services.writer).run()


if __name__ == "__main__":
    main()
