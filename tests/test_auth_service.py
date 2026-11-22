import pytest
from fake_auth import (
    GOOD_TOKEN_BODY,
    FakeReceiver,
    MemoryKeyring,
    make_client,
    make_token,
)

from ytmcp.auth import AuthService, TokenStore
from ytmcp.auth.oauth import SCOPE_READONLY, SCOPE_WRITE
from ytmcp.errors import AuthFailedError, AuthRequiredError

NOW = 1000.0


def make(queue=None, respond=None, token=None, now=NOW):
    receiver = FakeReceiver(respond)
    keyring = MemoryKeyring()
    store = TokenStore(keyring)
    if token:
        store.save(token)
    client, google = make_client(queue, now=lambda: now)
    service = AuthService(
        client, store,
        receiver_factory=lambda: receiver,
        open_browser=receiver.remember_url,
        now=lambda: now,
    )
    return service, store, google, receiver


# --- login ------------------------------------------------------------------


def test_login_saves_token_and_uses_pkce():
    service, store, google, receiver = make([(200, GOOD_TOKEN_BODY)])
    token = service.login()
    assert store.load() == token
    assert receiver.url_params["code_challenge_method"] == "S256"
    assert receiver.url_params["scope"] == SCOPE_READONLY
    _, data = google.calls[0]
    assert data["code"] == "the-code"
    assert data["redirect_uri"] == receiver.redirect_uri
    from ytmcp.auth.pkce import challenge_for
    assert challenge_for(data["code_verifier"]) == receiver.url_params["code_challenge"]


def test_login_announces_the_url_and_passes_the_timeout():
    service, _, _, receiver = make([(200, GOOD_TOKEN_BODY)])
    seen = []
    service.login(timeout=30, announce=seen.append)
    assert seen and seen[0].startswith("https://accounts.google.com/")
    assert receiver.timeout_seen == 30


def test_login_can_ask_for_write_scope():
    service, _, _, receiver = make([(200, GOOD_TOKEN_BODY)])
    service.login(scopes=(SCOPE_READONLY, SCOPE_WRITE))
    assert SCOPE_WRITE in receiver.url_params["scope"]


def test_wrong_state_is_rejected_before_anything_is_sent_or_saved():
    service, store, google, _ = make(respond=lambda p: {"code": "c", "state": "FORGED"})
    with pytest.raises(AuthFailedError) as exc:
        service.login()
    assert "did not match" in str(exc.value)
    assert google.calls == []
    assert store.load() is None


def test_missing_state_is_rejected():
    service, _, google, _ = make(respond=lambda p: {"code": "c"})
    with pytest.raises(AuthFailedError):
        service.login()
    assert google.calls == []


def test_denied_login():
    service, store, google, _ = make(respond=lambda p: {"error": "access_denied", "state": p["state"]})
    with pytest.raises(AuthFailedError) as exc:
        service.login()
    assert "access_denied" in str(exc.value)
    assert google.calls == [] and store.load() is None


def test_odd_error_text_is_not_echoed():
    service, _, _, _ = make(respond=lambda p: {"error": "<script>x</script>", "state": p["state"]})
    with pytest.raises(AuthFailedError) as exc:
        service.login()
    assert "<script>" not in str(exc.value)


def test_missing_code_is_rejected():
    service, _, google, _ = make(respond=lambda p: {"state": p["state"]})
    with pytest.raises(AuthFailedError):
        service.login()
    assert google.calls == []


def test_failed_exchange_saves_nothing():
    service, store, _, _ = make([(400, {"error": "invalid_grant"})])
    with pytest.raises(AuthFailedError):
        service.login()
    assert store.load() is None


def test_timeout_is_passed_up():
    def never(params):
        raise AuthFailedError("Timed out waiting for you to finish signing in.")
    service, _, _, _ = make(respond=never)
    with pytest.raises(AuthFailedError):
        service.login()


# --- get_access_token ---------------------------------------------------------


def test_not_signed_in_requires_auth():
    service, _, _, _ = make()
    with pytest.raises(AuthRequiredError) as exc:
        service.get_access_token()
    assert exc.value.code == "AUTH_REQUIRED"
    assert "auth login" in exc.value.remediation


def test_valid_token_is_returned_without_calling_google():
    service, _, google, _ = make(token=make_token(expires_at=NOW + 3600))
    assert service.get_access_token() == "ACCESS-1"
    assert google.calls == []


def test_expired_token_is_refreshed_and_saved():
    service, store, google, _ = make(
        [(200, {"access_token": "ACCESS-2", "expires_in": 3600})],
        token=make_token(expires_at=NOW - 1),
    )
    assert service.get_access_token() == "ACCESS-2"
    assert store.load().access_token == "ACCESS-2"
    assert store.load().refresh_token == "REFRESH-1"
    assert len(google.calls) == 1


def test_failed_refresh_signs_the_user_out():
    service, store, _, _ = make([(400, {"error": "invalid_grant"})], token=make_token(expires_at=NOW - 1))
    with pytest.raises(AuthRequiredError):
        service.get_access_token()
    assert store.load() is None
    assert service.status() == {"signed_in": False}


def test_other_refresh_errors_keep_the_login():
    service, store, _, _ = make([(500, {})], token=make_token(expires_at=NOW - 1))
    with pytest.raises(AuthFailedError):
        service.get_access_token()
    assert store.load() is not None  # might work on the next try


def test_missing_permission_requires_auth():
    service, _, _, _ = make(token=make_token(expires_at=NOW + 3600))
    with pytest.raises(AuthRequiredError) as exc:
        service.get_access_token(SCOPE_WRITE)
    assert "permission" in str(exc.value)


def test_write_login_also_covers_read():
    token = make_token(expires_at=NOW + 3600, scopes=(SCOPE_WRITE,))
    service, _, _, _ = make(token=token)
    assert service.get_access_token(SCOPE_READONLY) == "ACCESS-1"
    assert service.get_access_token(SCOPE_WRITE) == "ACCESS-1"


# --- status and logout ---------------------------------------------------------


def test_status_signed_out():
    service, _, _, _ = make()
    assert service.status() == {"signed_in": False}


def test_status_signed_in_has_no_tokens():
    service, _, _, _ = make(token=make_token(expires_at=NOW + 600))
    info = service.status()
    assert info == {
        "signed_in": True, "can_write": False, "has_refresh_token": True,
        "access_token_valid_seconds": 600,
    }
    assert "ACCESS-1" not in str(info) and "REFRESH-1" not in str(info)


def test_status_for_expired_access_token_is_zero_seconds():
    service, _, _, _ = make(token=make_token(expires_at=NOW - 50))
    assert service.status()["access_token_valid_seconds"] == 0


def test_logout_revokes_and_deletes():
    service, store, google, _ = make([(200, {})], token=make_token())
    assert service.logout() == {"was_signed_in": True, "revoked": True}
    assert store.load() is None
    assert google.calls[0][1] == {"token": "REFRESH-1"}


def test_logout_deletes_even_if_google_cannot_be_reached():
    service, store, _, _ = make([OSError("offline")], token=make_token())
    assert service.logout() == {"was_signed_in": True, "revoked": False}
    assert store.load() is None


def test_logout_when_not_signed_in():
    service, _, google, _ = make()
    assert service.logout() == {"was_signed_in": False, "revoked": False}
    assert google.calls == []
