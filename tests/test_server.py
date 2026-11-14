import asyncio

from ytmcp.server import create_server


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