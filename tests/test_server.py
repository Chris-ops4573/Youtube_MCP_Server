import asyncio

from ytmcp.providers.fixture import FixtureProvider
from ytmcp.providers.youtube import YouTubeProvider
from ytmcp.server import build_provider, create_server


def _call(server, name, arguments):
    return asyncio.run(server.call_tool(name, arguments))


def test_server_registers_the_tool(provider):
    server = create_server(provider)
    tools = asyncio.run(server.list_tools())
    assert [t.name for t in tools] == ["find_similar_videos"]


def test_tool_call_returns_results(provider):
    result = _call(create_server(provider), "find_similar_videos", {"video": "aaaaaaaaaaa"})
    assert "Rust lifetimes tutorial" in str(result)
    assert "bbbbbbbbbbb" in str(result)


def test_tool_call_reports_errors(provider):
    result = _call(create_server(provider), "find_similar_videos", {"video": "nope"})
    assert "INVALID_VIDEO_REFERENCE" in str(result)

def test_build_provider_fixture(monkeypatch):
    monkeypatch.setenv("YTMCP_PROVIDER", "fixture")
    assert isinstance(build_provider(), FixtureProvider)


def test_build_provider_defaults_to_youtube(monkeypatch):
    monkeypatch.delenv("YTMCP_PROVIDER", raising=False)
    monkeypatch.setenv("YOUTUBE_API_KEY", "k")
    assert isinstance(build_provider(), YouTubeProvider)
