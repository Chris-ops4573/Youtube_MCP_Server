"""Google OAuth 2.0 for installed apps, with PKCE (FR-6.1).

Talks to Google's OAuth endpoints with the standard library. Error messages
only ever contain Google's short error code (e.g. "invalid_grant"), never
tokens, codes or secrets.
"""

import json
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ytmcp.auth.tokens import Token
from ytmcp.errors import AuthFailedError, AuthRequiredError, OAuthConfigError

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
TIMEOUT_SECONDS = 10

# Read-only is the default (FR-6.1). Write access is requested only at the
# first confirmed playlist creation (FR-5).
SCOPE_READONLY = "https://www.googleapis.com/auth/youtube.readonly"
SCOPE_WRITE = "https://www.googleapis.com/auth/youtube"

# Takes (url, form fields), returns (HTTP status, parsed JSON body). Tests pass a fake.
Post = Callable[[str, dict[str, str]], tuple[int, dict[str, Any]]]


def urllib_post(url: str, data: dict[str, str]) -> tuple[int, dict[str, Any]]:
    request = Request(url, data=urlencode(data).encode(), method="POST")
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read() or b"{}")
    except HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read())
        except ValueError:
            return exc.code, {}


@dataclass(frozen=True)
class OAuthConfig:
    client_id: str
    client_secret: str | None = None  # Google still asks for it for desktop apps; it is not truly secret

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "OAuthConfig":
        client_id = env.get("YTMCP_OAUTH_CLIENT_ID", "").strip()
        if not client_id:
            raise OAuthConfigError("No Google OAuth client ID is configured.")
        return cls(client_id, env.get("YTMCP_OAUTH_CLIENT_SECRET", "").strip() or None)

    def __repr__(self) -> str:
        return "OAuthConfig(client_id=..., client_secret=...)"


class OAuthClient:
    def __init__(
        self,
        config: OAuthConfig,
        post: Post = urllib_post,
        now: Callable[[], float] = time.time,
    ):
        self._config = config
        self._post = post
        self._now = now

    def build_auth_url(
        self, redirect_uri: str, scopes: tuple[str, ...], state: str, challenge: str
    ) -> str:
        params = {
            "client_id": self._config.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "access_type": "offline",  # so Google gives a refresh token
            "prompt": "consent",  # ...every time, even on a repeat login
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    def _client_fields(self) -> dict[str, str]:
        fields = {"client_id": self._config.client_id}
        if self._config.client_secret:
            fields["client_secret"] = self._config.client_secret
        return fields

    def _to_token(
        self, body: dict[str, Any], old_refresh: str | None, old_scopes: tuple[str, ...]
    ) -> Token:
        try:
            return Token(
                access_token=body["access_token"],
                refresh_token=body.get("refresh_token") or old_refresh,  # refreshes omit it
                expires_at=self._now() + float(body.get("expires_in", 3600)),
                scopes=tuple(body["scope"].split()) if body.get("scope") else old_scopes,
            )
        except (KeyError, TypeError, ValueError):
            raise AuthFailedError("Google sent an unexpected sign-in response.") from None

    def exchange_code(self, code: str, verifier: str, redirect_uri: str) -> Token:
        status, body = self._post(
            TOKEN_URL,
            {
                **self._client_fields(),
                "code": code,
                "code_verifier": verifier,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        if status != 200:
            raise AuthFailedError(f"Google rejected the sign-in ({_reason(body, status)}).")
        return self._to_token(body, None, ())

    def refresh(self, token: Token) -> Token:
        """Get a new access token. Raises AuthRequiredError if the login can no longer be refreshed."""
        if not token.refresh_token:
            raise AuthRequiredError("Your Google login has expired and cannot be renewed.")
        status, body = self._post(
            TOKEN_URL,
            {
                **self._client_fields(),
                "refresh_token": token.refresh_token,
                "grant_type": "refresh_token",
            },
        )
        if status == 200:
            return self._to_token(body, token.refresh_token, token.scopes)
        if body.get("error") == "invalid_grant":  # expired, revoked or 7-day Testing-mode limit
            raise AuthRequiredError("Your Google login has expired. Please sign in again.")
        raise AuthFailedError(f"Google could not renew the login ({_reason(body, status)}).")

    def revoke(self, token: Token) -> bool:
        """Tell Google to invalidate the login. Returns False if that did not work."""
        try:
            status, _ = self._post(REVOKE_URL, {"token": token.refresh_token or token.access_token})
        except OSError:
            return False
        return status == 200


def _reason(body: dict[str, Any], status: int) -> str:
    """Only Google's short error code, e.g. 'invalid_client'. Never the full body."""
    error = body.get("error")
    return error if isinstance(error, str) and error.isidentifier() else f"HTTP {status}"
