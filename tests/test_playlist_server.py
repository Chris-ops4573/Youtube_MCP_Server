"""The playlist tools over the REAL MCP protocol (in memory), and the question to the user.

These prove the safety rule from the SRS (FR-5.5): nothing is written to YouTube unless a person
approved, whatever the AI client does.
"""

import asyncio
import json
from types import SimpleNamespace

import pytest
from fake_playlists import FakeWriter, ListProvider
from fake_playlists import make_video as v
from mcp import Client, types
from mcp.server.elicitation import (
    AcceptedElicitation,
    CancelledElicitation,
    DeclinedElicitation,
)
from mcp.shared.exceptions import MCPError

from ytmcp import server as server_module
from ytmcp.cache import Cache
from ytmcp.proposals import ProposalStore
from ytmcp.providers.fixture import FixtureProvider
from ytmcp.providers.playlists import YouTubePlaylistWriter
from ytmcp.server import ConfirmPlaylist, ask_user, build_services, create_server

IDS = ["aaaaaaaaaaa", "bbbbbbbbbbb"]


def make(writer=None):
    store = ProposalStore(Cache(":memory:"))
    provider = ListProvider([v(IDS[0], 30, "Rust A"), v(IDS[1], 30, "Rust B")])
    writer = writer if writer is not None else FakeWriter()
    return create_server(provider, store, writer), store, writer


async def run_scenario(callback, mode="legacy", writer=None, before_create=None):
    server, store, writer = make(writer)
    async with Client(server, elicitation_callback=callback, mode=mode) as client:
        r = await client.call_tool("propose_playlist", {"topic": "rust", "total_minutes": 60})
        p = json.loads(r.content[0].text)["proposal"]
        if before_create:
            before_create(store, p)
        r = await client.call_tool("create_playlist", {"proposal_id": p["proposal_id"], "content_hash": p["content_hash"]})
        return json.loads(r.content[0].text), writer, store, p


def answer(**kwargs):
    async def callback(context, params):
        return types.ElicitResult(**kwargs)

    return callback


# --- the real protocol: only a person saying yes creates anything ---------------------------------------------


def test_user_accepts_and_ticks_confirm_so_the_playlist_is_created():
    out, writer, store, p = asyncio.run(run_scenario(answer(action="accept", content={"confirm": True})))
    assert out["created"]["status"] == "created"
    assert writer.names() == ["budget", "access", "create", "add", "add"]
    assert store.get(p["proposal_id"]).status == "created"


def test_the_question_the_user_sees_is_plain_and_says_private():
    seen = []

    async def callback(context, params):
        seen.append(params)
        return types.ElicitResult(action="accept", content={"confirm": True})

    asyncio.run(run_scenario(callback))
    assert "PRIVATE" in seen[0].message and "2 videos" in seen[0].message


@pytest.mark.parametrize(
    "reply",
    [
        {"action": "accept", "content": {"confirm": False}},  # accepted the form but left it unticked
        {"action": "decline"},
        {"action": "cancel"},
    ],
)
def test_anything_other_than_a_clear_yes_creates_nothing(reply):
    out, writer, store, p = asyncio.run(run_scenario(answer(**reply)))
    assert out["cancelled"] is True
    assert writer.events == []
    assert store.get(p["proposal_id"]).status == "declined"


def test_a_client_without_elicitation_cannot_make_a_playlist_by_itself():
    out, writer, store, p = asyncio.run(run_scenario(None))
    assert out["error"]["code"] == "CONFIRMATION_REQUIRED"
    assert f"python -m ytmcp playlist confirm {p['proposal_id']}" in out["error"]["remediation"]
    assert writer.events == []
    assert store.get(p["proposal_id"]).status == "proposed"


def test_the_newer_protocol_cannot_ask_mid_call_so_it_falls_back_to_the_terminal():
    out, writer, _, _ = asyncio.run(run_scenario(answer(action="accept", content={"confirm": True}), mode="auto"))
    assert out["error"]["code"] == "CONFIRMATION_REQUIRED"
    assert writer.events == []


def test_after_a_terminal_confirmation_a_client_without_elicitation_can_create():
    out, writer, _, _ = asyncio.run(run_scenario(None, before_create=lambda store, p: store.confirm(p["proposal_id"], _now())))
    assert out["created"]["status"] == "created"
    assert writer.added() == IDS


def _now():
    import time

    return time.time()


def test_the_ai_cannot_replay_a_proposal_into_a_second_playlist():
    async def scenario():
        server, _, writer = make()
        async with Client(server, elicitation_callback=answer(action="accept", content={"confirm": True}), mode="legacy") as client:
            r = await client.call_tool("propose_playlist", {"topic": "rust", "total_minutes": 60})
            p = json.loads(r.content[0].text)["proposal"]
            args = {"proposal_id": p["proposal_id"], "content_hash": p["content_hash"]}
            first = json.loads((await client.call_tool("create_playlist", args)).content[0].text)
            second = json.loads((await client.call_tool("create_playlist", args)).content[0].text)
        return first, second, writer

    first, second, writer = asyncio.run(scenario())
    assert "created" in first and second["error"]["code"] == "PROPOSAL_ALREADY_USED"
    assert writer.names().count("create") == 1


def test_a_made_up_proposal_or_hash_creates_nothing_and_asks_nothing():
    asked = []

    async def callback(context, params):
        asked.append(params)
        return types.ElicitResult(action="accept", content={"confirm": True})

    async def scenario():
        server, _, writer = make()
        async with Client(server, elicitation_callback=callback, mode="legacy") as client:
            r = await client.call_tool("create_playlist", {"proposal_id": "made-up", "content_hash": "0" * 16})
            made_up = json.loads(r.content[0].text)
            r = await client.call_tool("propose_playlist", {"topic": "rust", "total_minutes": 60})
            p = json.loads(r.content[0].text)["proposal"]
            r = await client.call_tool("create_playlist", {"proposal_id": p["proposal_id"], "content_hash": "f" * 16})
            wrong_hash = json.loads(r.content[0].text)
        return made_up, wrong_hash, writer

    made_up, wrong_hash, writer = asyncio.run(scenario())
    assert made_up["error"]["code"] == "PROPOSAL_NOT_FOUND"
    assert wrong_hash["error"]["code"] == "PROPOSAL_MISMATCH"
    assert writer.events == [] and asked == []


def test_there_is_no_tool_to_edit_or_delete_anything():
    async def names():
        server, _, _ = make()
        async with Client(server, mode="legacy") as client:
            return [t.name for t in (await client.list_tools()).tools]

    tools = asyncio.run(names())
    assert tools == ["find_similar_videos", "find_similar_channels", "propose_playlist", "create_playlist"]


def test_tool_hints_tell_clients_which_tool_changes_things():
    async def annotations():
        server, _, _ = make()
        async with Client(server, mode="legacy") as client:
            return {t.name: t.annotations for t in (await client.list_tools()).tools}

    hints = asyncio.run(annotations())
    assert hints["propose_playlist"].read_only_hint is True
    assert hints["create_playlist"].read_only_hint is False
    assert hints["create_playlist"].destructive_hint is False  # creates only


def test_propose_over_the_protocol_has_the_documented_arguments():
    async def schema():
        server, _, _ = make()
        async with Client(server, mode="legacy") as client:
            tool = next(t for t in (await client.list_tools()).tools if t.name == "propose_playlist")
            return tool.input_schema

    schema = asyncio.run(schema())
    assert set(schema["properties"]) == {
        "topic", "total_minutes", "max_video_minutes", "min_video_minutes", "language", "title",
    }
    assert set(schema["required"]) == {"topic", "total_minutes"}


def test_in_process_calls_without_a_client_fall_back_safely(provider):
    """Like the older tests: call_tool on the server directly, with no client at all."""
    server = create_server(provider)
    out = asyncio.run(server.call_tool("propose_playlist", {"topic": "rust", "total_minutes": 25}))
    p = json.loads(out.content[0].text)["proposal"]
    out = asyncio.run(server.call_tool("create_playlist", {"proposal_id": p["proposal_id"], "content_hash": p["content_hash"]}))
    assert "PLAYLIST_WRITES_DISABLED" in out.content[0].text  # no writer in this setup


# --- ask_user: every way the question can go ---------------------------------------------------------------------


class FakeCtx:
    def __init__(self, supported=True, result=None, raises=None, no_request=False):
        self.supported = supported
        self.result = result
        self.raises = raises
        self.no_request = no_request
        self.probes = []
        self.asked = []

    @property
    def request_context(self):
        if self.no_request:
            raise ValueError("Context is not available outside of a request")
        probes = self.probes

        class Session:
            def __init__(self, supported):
                self.supported = supported

            def check_client_capability(self, capability):
                probes.append(capability)
                return self.supported

        return SimpleNamespace(session=Session(self.supported))

    async def elicit(self, message, schema):
        self.asked.append((message, schema))
        if self.raises:
            raise self.raises
        return self.result


def ask(ctx):
    return asyncio.run(ask_user(ctx, "Create it?"))


def test_ask_user_accepts_only_an_accepted_and_ticked_form():
    assert ask(FakeCtx(result=AcceptedElicitation(data=ConfirmPlaylist(confirm=True)))) == "accept"


@pytest.mark.parametrize(
    "result",
    [AcceptedElicitation(data=ConfirmPlaylist(confirm=False)), AcceptedElicitation(data=ConfirmPlaylist()), DeclinedElicitation(), CancelledElicitation()],
)
def test_ask_user_treats_everything_else_as_no(result):
    assert ask(FakeCtx(result=result)) == "decline"


def test_ask_user_checks_the_client_declared_form_elicitation_before_asking():
    ctx = FakeCtx(supported=False)
    assert ask(ctx) == "unsupported"
    assert ctx.asked == []  # never even sent the question
    assert ctx.probes[0].elicitation.form is not None


def test_ask_user_without_a_client_request_is_unsupported():
    assert ask(FakeCtx(no_request=True)) == "unsupported"


def test_ask_user_when_the_client_errors_on_the_question_is_unsupported():
    assert ask(FakeCtx(raises=MCPError(-32601, "Method not found"))) == "unsupported"


def test_ask_user_with_an_unusable_answer_is_no():
    assert ask(FakeCtx(raises=ValueError("bad content"))) == "decline"


def test_the_form_has_one_unticked_yes_no_field():
    assert ConfirmPlaylist().confirm is False
    assert list(ConfirmPlaylist.model_fields) == ["confirm"]


# --- build_services ----------------------------------------------------------------------------------------------------


def test_fixture_mode_has_no_writer_so_no_real_playlists(monkeypatch, tmp_path):
    monkeypatch.setenv("YTMCP_PROVIDER", "fixture")
    monkeypatch.setenv("YTMCP_CACHE_PATH", str(tmp_path / "c.db"))
    services = build_services()
    assert isinstance(services.provider, FixtureProvider)
    assert services.writer is None
    assert isinstance(services.store, ProposalStore)


@pytest.mark.parametrize("cache_setting", ["on", "off"])
def test_live_mode_shares_one_quota_between_reading_and_writing(monkeypatch, tmp_path, cache_setting):
    monkeypatch.setenv("YTMCP_PROVIDER", "youtube")
    monkeypatch.setenv("YOUTUBE_API_KEY", "k")
    monkeypatch.setenv("YTMCP_CACHE", cache_setting)
    monkeypatch.setenv("YTMCP_CACHE_PATH", str(tmp_path / "c.db"))
    services = build_services()
    assert isinstance(services.writer, YouTubePlaylistWriter)
    inner = getattr(services.provider, "_inner", services.provider)
    assert services.writer._quota is inner._quota  # one daily count, not two
    assert (tmp_path / "c.db").exists()  # proposals live in the file even with the cache off


def test_the_token_comes_from_the_login_service_for_the_requested_scope(monkeypatch):
    calls = []

    class FakeAuth:
        def get_access_token(self, scope):
            calls.append(scope)
            return "tok"

    import ytmcp.cli

    monkeypatch.setattr(ytmcp.cli, "build_auth_service", lambda: FakeAuth())
    assert server_module._access_token("scope-x") == "tok"
    assert calls == ["scope-x"]
