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
