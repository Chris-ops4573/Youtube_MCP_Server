import pytest
from fake_auth import (
    GOOD_TOKEN_BODY,
    FakeReceiver,
    MemoryKeyring,
    make_client,
    make_token,
)

from ytmcp.auth import AuthService, TokenStore
from ytmcp.cli import main
from ytmcp.errors import OAuthConfigError


def run(argv, queue=None, token=None, respond=None):
    lines: list[str] = []
    receiver = FakeReceiver(respond)
    store = TokenStore(MemoryKeyring())
    if token:
        store.save(token)
    client, _ = make_client(queue, now=lambda: 1000.0)
    service = AuthService(client, store, receiver_factory=lambda: receiver,
                          open_browser=receiver.remember_url, now=lambda: 1000.0)
    code = main(argv, service_factory=lambda: service, out=lines.append)
    return code, "\n".join(lines), store


def test_login_prints_the_link_and_success_without_tokens():
    code, output, store = run(["auth", "login"], [(200, GOOD_TOKEN_BODY)])
    assert code == 0
    assert "https://accounts.google.com/" in output
    assert "Signed in. Access: read-only." in output
    assert "ACCESS-1" not in output and "REFRESH-1" not in output
    assert store.load() is not None


def test_login_failure_shows_code_message_and_fix():
    code, output, _ = run(["auth", "login"], respond=lambda p: {"error": "access_denied", "state": p["state"]})
    assert code == 1
    assert "Error [AUTH_FAILED]" in output
    assert "Fix:" in output and "auth login" in output


def test_status_signed_out():
    code, output, _ = run(["auth", "status"])
    assert code == 0
    assert "Not signed in" in output


def test_status_signed_in():
    code, output, _ = run(["auth", "status"], token=make_token(expires_at=1000.0 + 600))
    assert code == 0
    assert "Signed in. Access: read-only. Can renew: yes" in output
    assert "~10 min" in output
    assert "ACCESS-1" not in output


def test_logout():
    code, output, store = run(["auth", "logout"], [(200, {})], token=make_token())
    assert code == 0
    assert "Signed out. Google has been told" in output
    assert store.load() is None


def test_logout_when_google_unreachable_explains_how_to_remove_access():
    _, output, store = run(["auth", "logout"], [OSError("offline")], token=make_token())
    assert "myaccount.google.com/permissions" in output
    assert store.load() is None


def test_logout_when_not_signed_in():
    code, output, _ = run(["auth", "logout"])
    assert code == 0 and "not signed in" in output


def test_missing_oauth_config_is_a_clean_error():
    lines: list[str] = []

    def factory():
        raise OAuthConfigError("No Google OAuth client ID is configured.")

    assert main(["auth", "status"], service_factory=factory, out=lines.append) == 1
    assert "OAUTH_NOT_CONFIGURED" in lines[0] and "Traceback" not in lines[0]


@pytest.mark.parametrize("argv", [[], ["auth"], ["auth", "nope"], ["nope"]])
def test_bad_arguments_exit_with_usage(argv):
    with pytest.raises(SystemExit) as exc:
        main(argv, service_factory=lambda: None, out=lambda s: None)
    assert exc.value.code == 2


# --- auth login --write (FR-6.1) ------------------------------------------------------------------------


def test_login_is_read_only_by_default():
    code, output, _ = run(["auth", "login"], [(200, GOOD_TOKEN_BODY)])
    assert code == 0 and "read-only" in output


def test_login_with_write_asks_for_write_access_and_says_so():
    from ytmcp.auth.oauth import SCOPE_READONLY, SCOPE_WRITE

    receiver = FakeReceiver()
    client, _ = make_client([(200, GOOD_TOKEN_BODY)], now=lambda: 1000.0)
    service = AuthService(client, TokenStore(MemoryKeyring()), receiver_factory=lambda: receiver,
                          open_browser=receiver.remember_url, now=lambda: 1000.0)
    lines: list[str] = []
    assert main(["auth", "login", "--write"], service_factory=lambda: service, out=lines.append) == 0
    assert receiver.url_params["scope"] == SCOPE_WRITE
    assert SCOPE_READONLY not in receiver.url_params["scope"]
    assert "read and write" in "\n".join(lines)


# --- playlist confirm (FR-5.5) ---------------------------------------------------------------------------


import pytest

from ytmcp import proposals
from ytmcp.database import Database
from ytmcp.proposals import Proposal, ProposalStore, ProposedVideo, content_hash

NOW = 1_000_000.0


def saved_store(status=proposals.PROPOSED, ttl=900):
    store = ProposalStore(Database(":memory:"))
    ids = ["aaaaaaaaaaa", "bbbbbbbbbbb"]
    store.save(Proposal(
        id="prop1", content_hash=content_hash("My list", "d", ids), title="My list", description="d",
        videos=(ProposedVideo(ids[0], "Rust A", "Chan", 1500), ProposedVideo(ids[1], "Rust B", "Chan", 1200)),
        constraints={}, created_at=NOW, expires_at=NOW + ttl, status=status,
    ))
    return store


def confirm(store, answer="yes", terminal=True, proposal_id="prop1", now=NOW + 60):
    lines: list[str] = []
    asked: list[str] = []

    def ask(prompt):
        asked.append(prompt)
        return answer

    def no_auth():
        raise AssertionError("the login service must not be needed to confirm a playlist")

    code = main(["playlist", "confirm", proposal_id], service_factory=no_auth, out=lines.append,
                store_factory=lambda: store, ask=ask, is_terminal=lambda: terminal, now=lambda: now)
    return code, "\n".join(lines), asked


def test_confirm_shows_the_playlist_then_confirms_on_yes():
    store = saved_store()
    code, output, asked = confirm(store)
    assert code == 0
    assert "My list" in output and "PRIVATE" in output and "2 videos" in output
    assert "Rust A" in output and "25 min" in output and "Rust B" in output
    assert "about 45 min" in output and "expires in about 14 min" in output
    assert "create_playlist" in output
    assert len(asked) == 1 and "yes" in asked[0]
    assert store.get("prop1").status == proposals.CONFIRMED


@pytest.mark.parametrize("answer", ["YES", " yes  ", "Yes"])
def test_yes_is_accepted_in_any_case(answer):
    store = saved_store()
    assert confirm(store, answer)[0] == 0
    assert store.get("prop1").status == proposals.CONFIRMED


@pytest.mark.parametrize("answer", ["", "y", "no", "yes please", "ok", "true"])
def test_anything_but_yes_does_not_confirm(answer):
    store = saved_store()
    code, output, _ = confirm(store, answer)
    assert code == 1 and "Not confirmed" in output
    assert store.get("prop1").status == proposals.PROPOSED


def test_it_refuses_to_run_without_a_real_terminal_and_never_asks():
    store = saved_store()
    code, output, asked = confirm(store, terminal=False)
    assert code == 1 and "interactive terminal" in output
    assert asked == []
    assert store.get("prop1").status == proposals.PROPOSED


def test_a_refused_run_does_not_even_open_the_database():
    lines: list[str] = []

    def store_factory():
        raise AssertionError("the database must not be opened")

    code = main(["playlist", "confirm", "x"], out=lines.append, store_factory=store_factory,
                is_terminal=lambda: False, service_factory=lambda: None)
    assert code == 1


def test_unknown_expired_and_used_proposals_are_clean_errors():
    code, output, _ = confirm(saved_store(), proposal_id="nope")
    assert code == 1 and "PROPOSAL_NOT_FOUND" in output and "Traceback" not in output
    code, output, asked = confirm(saved_store(), now=NOW + 900)
    assert code == 1 and "PROPOSAL_EXPIRED" in output and asked == []
    code, output, asked = confirm(saved_store(status=proposals.CREATED))
    assert code == 1 and "PROPOSAL_ALREADY_USED" in output and asked == []


def test_confirming_twice_just_says_it_is_already_confirmed_and_does_not_ask_again():
    store = saved_store()
    assert confirm(store)[0] == 0
    code, output, asked = confirm(store)
    assert code == 0 and "Already confirmed" in output
    assert asked == []
    assert store.get("prop1").status == proposals.CONFIRMED


def test_losing_a_race_to_use_the_proposal_is_reported(monkeypatch):
    store = saved_store()
    monkeypatch.setattr(store, "confirm", lambda *a, **k: False)
    code, output, _ = confirm(store)
    assert code == 1 and "PROPOSAL_ALREADY_USED" in output


def test_the_real_terminal_check_needs_both_input_and_output_to_be_a_terminal(monkeypatch):
    import sys

    from ytmcp import cli

    lines: list[str] = []
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    store = saved_store()
    code = cli.main(["playlist", "confirm", "prop1"], out=lines.append, store_factory=lambda: store,
                    now=lambda: NOW + 60, service_factory=lambda: None)
    assert code == 1 and "interactive terminal" in lines[0]
