from urllib.parse import parse_qs, urlparse

import pytest
from fake_auth import GOOD_TOKEN_BODY, make_client, make_token

from ytmcp.auth.oauth import (
    AUTH_URL,
    REVOKE_URL,
    SCOPE_READONLY,
    SCOPE_WRITE,
    TOKEN_URL,
    OAuthConfig,
)
from ytmcp.errors import AuthFailedError, AuthRequiredError, OAuthConfigError

SECRETS = ["client-secret", "ACCESS-1", "REFRESH-1", "the-code", "the-verifier"]


def test_config_from_env():
    config = OAuthConfig.from_env({"YTMCP_OAUTH_CLIENT_ID": " id ", "YTMCP_OAUTH_CLIENT_SECRET": "s"})
    assert (config.client_id, config.client_secret) == ("id", "s")


def test_config_secret_is_optional():
    assert OAuthConfig.from_env({"YTMCP_OAUTH_CLIENT_ID": "id"}).client_secret is None


@pytest.mark.parametrize("env", [{}, {"YTMCP_OAUTH_CLIENT_ID": "  "}])
def test_config_missing_client_id(env):
    with pytest.raises(OAuthConfigError) as exc:
        OAuthConfig.from_env(env)
    assert exc.value.code == "OAUTH_NOT_CONFIGURED"
    assert ".env" in exc.value.remediation


def test_config_repr_hides_values():
    assert "client-secret" not in repr(OAuthConfig("id", "client-secret"))


def test_auth_url_has_everything_needed():
    client, _ = make_client()
    url = client.build_auth_url("http://127.0.0.1:1/callback", (SCOPE_READONLY,), "STATE", "CHALLENGE")
    parsed = urlparse(url)
    params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == AUTH_URL
    assert params["client_id"] == "client-id"
    assert params["redirect_uri"] == "http://127.0.0.1:1/callback"
    assert params["response_type"] == "code"
    assert params["scope"] == SCOPE_READONLY
    assert params["state"] == "STATE"
    assert params["code_challenge"] == "CHALLENGE"
    assert params["code_challenge_method"] == "S256"
    assert params["access_type"] == "offline"
    assert params["prompt"] == "consent"
    assert "client_secret" not in params and "code_verifier" not in params


def test_default_scope_is_read_only_not_write():
    assert SCOPE_READONLY.endswith("youtube.readonly")
    assert SCOPE_READONLY != SCOPE_WRITE


def test_auth_url_joins_several_scopes():
    client, _ = make_client()
    url = client.build_auth_url("http://x", (SCOPE_READONLY, SCOPE_WRITE), "s", "c")
    assert parse_qs(urlparse(url).query)["scope"] == [f"{SCOPE_READONLY} {SCOPE_WRITE}"]


def test_exchange_code_sends_pkce_fields_and_builds_token():
    client, google = make_client([(200, GOOD_TOKEN_BODY)])
    token = client.exchange_code("the-code", "the-verifier", "http://127.0.0.1:1/callback")
    url, data = google.calls[0]
    assert url == TOKEN_URL
    assert data == {
        "client_id": "client-id",
        "client_secret": "client-secret",
        "code": "the-code",
        "code_verifier": "the-verifier",
        "grant_type": "authorization_code",
        "redirect_uri": "http://127.0.0.1:1/callback",
    }
    assert token.access_token == "ACCESS-1"
    assert token.refresh_token == "REFRESH-1"
    assert token.expires_at == 1000.0 + 3600
    assert token.scopes == (SCOPE_READONLY,)


def test_client_secret_is_left_out_when_not_set():
    client, google = make_client([(200, GOOD_TOKEN_BODY)], secret=None)
    client.exchange_code("c", "v", "http://x")
    assert "client_secret" not in google.calls[0][1]


@pytest.mark.parametrize("body", [{}, {"access_token": "x", "expires_in": "soon"}])
def test_exchange_with_unexpected_body_fails_cleanly(body):
    status = 200
    client, _ = make_client([(status, body)])
    with pytest.raises(AuthFailedError):
        client.exchange_code("c", "v", "http://x")


def test_exchange_rejected_shows_only_the_short_reason():
    body = {"error": "invalid_client", "error_description": "secret detail the-code"}
    client, _ = make_client([(401, body)])
    with pytest.raises(AuthFailedError) as exc:
        client.exchange_code("the-code", "the-verifier", "http://x")
    assert "invalid_client" in str(exc.value)
    assert not any(s in str(exc.value) for s in SECRETS + ["secret detail"])


def test_refresh_keeps_old_refresh_token_and_scopes():
    new_body = {"access_token": "ACCESS-2", "expires_in": 3600}  # Google omits refresh_token and scope
    client, google = make_client([(200, new_body)])
    token = client.refresh(make_token())
    assert token.access_token == "ACCESS-2"
    assert token.refresh_token == "REFRESH-1"
    assert token.scopes == (SCOPE_READONLY,)
    assert google.calls[0][1]["grant_type"] == "refresh_token"
    assert google.calls[0][1]["refresh_token"] == "REFRESH-1"


def test_refresh_invalid_grant_asks_to_sign_in_again():
    client, _ = make_client([(400, {"error": "invalid_grant"})])
    with pytest.raises(AuthRequiredError) as exc:
        client.refresh(make_token())
    assert exc.value.code == "AUTH_REQUIRED"
    assert "sign in again" in str(exc.value)


def test_refresh_without_refresh_token_asks_to_sign_in_again():
    client, google = make_client()
    with pytest.raises(AuthRequiredError):
        client.refresh(make_token(refresh=None))
    assert google.calls == []


def test_refresh_other_errors_are_auth_failed():
    client, _ = make_client([(500, {})])
    with pytest.raises(AuthFailedError) as exc:
        client.refresh(make_token())
    assert "HTTP 500" in str(exc.value)
    assert "REFRESH-1" not in str(exc.value)


def test_revoke_uses_the_refresh_token():
    client, google = make_client([(200, {})])
    assert client.revoke(make_token()) is True
    assert google.calls[0] == (REVOKE_URL, {"token": "REFRESH-1"})


def test_revoke_falls_back_to_access_token():
    client, google = make_client([(200, {})])
    client.revoke(make_token(refresh=None))
    assert google.calls[0][1] == {"token": "ACCESS-1"}


@pytest.mark.parametrize("answer", [(400, {}), OSError("offline")])
def test_revoke_failure_returns_false(answer):
    client, _ = make_client([answer])
    assert client.revoke(make_token()) is False
