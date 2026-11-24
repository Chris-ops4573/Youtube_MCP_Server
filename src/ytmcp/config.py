"""Settings and wiring: reads the settings and builds the objects for server.py and cli.py.

This file imports neither of them, so the two entry points never need each other.

Settings (environment variables, or a .env file):
- YTMCP_PROVIDER: "youtube" (default, live YouTube Data API, needs YOUTUBE_API_KEY) or
  "fixture" (sample data from tests/fixtures: no API calls, no quota)
- YTMCP_CACHE_PATH: the SQLite file (default .cache/ytmcp.db in the project)
- YTMCP_CACHE: "off" turns the data cache off. Playlist proposals are always kept in the
  same database file, so a person can confirm one from a terminal.
- YTMCP_FIXTURES_DIR: where the sample data is (fixture mode)
"""

import os
from dataclasses import dataclass
from pathlib import Path

from ytmcp.auth import AuthService, OAuthClient, OAuthConfig, TokenStore
from ytmcp.database import Database
from ytmcp.proposals import ProposalStore
from ytmcp.providers.base import PlaylistWriter, VideoProvider
from ytmcp.providers.caching import CachingProvider
from ytmcp.providers.fixture import FixtureProvider
from ytmcp.providers.youtube import YouTubePlaylistWriter, YouTubeProvider
from ytmcp.quota import QuotaTracker


def default_cache_path() -> Path:
    """Where the database lives: YTMCP_CACHE_PATH, or .cache/ytmcp.db in the project."""
    env = os.environ.get("YTMCP_CACHE_PATH")
    return Path(env) if env else Path(__file__).resolve().parents[2] / ".cache" / "ytmcp.db"


def default_fixtures_dir() -> Path:
    env = os.environ.get("YTMCP_FIXTURES_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "tests" / "fixtures"


def build_auth_service() -> AuthService:
    return AuthService(OAuthClient(OAuthConfig.from_env()), TokenStore())


def build_store() -> ProposalStore:
    return ProposalStore(Database(default_cache_path()))


def build_provider(cache: Database | None = None, quota: QuotaTracker | None = None) -> VideoProvider:
    """Pick the provider from YTMCP_PROVIDER. A missing API key is not fatal:
    the server still starts and tools return an API_KEY_MISSING error."""
    if os.environ.get("YTMCP_PROVIDER", "youtube").lower() == "fixture":
        return FixtureProvider(default_fixtures_dir())
    api_key = os.environ.get("YOUTUBE_API_KEY") or None
    if os.environ.get("YTMCP_CACHE", "on").lower() == "off":
        return YouTubeProvider(api_key, quota=quota)
    cache = cache or Database(default_cache_path())
    return CachingProvider(YouTubeProvider(api_key, quota=quota or QuotaTracker(cache=cache)), cache)


def access_token(scope: str) -> str:
    """A valid Google login token for `scope`, built when needed so a missing OAuth setup
    only affects playlist creation."""
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
    cache = Database(default_cache_path())
    store = ProposalStore(cache)
    if os.environ.get("YTMCP_PROVIDER", "youtube").lower() == "fixture":
        return Services(build_provider(), store, None)
    cache_on = os.environ.get("YTMCP_CACHE", "on").lower() != "off"
    quota = QuotaTracker(cache=cache) if cache_on else QuotaTracker()
    provider = build_provider(cache, quota)
    return Services(provider, store, YouTubePlaylistWriter(access_token, quota))
