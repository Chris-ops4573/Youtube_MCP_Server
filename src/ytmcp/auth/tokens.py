"""OAuth tokens and where they are kept (FR-6.2).

Tokens are stored only in the OS keyring (Secret Service, macOS Keychain or
Windows Credential Manager), never in files, the database, logs or errors.
"""

import json
from dataclasses import dataclass
from typing import Any

import keyring
from keyring.errors import KeyringError

from ytmcp.errors import AuthFailedError

SERVICE = "ytmcp"
USERNAME = "google-oauth-token"
EXPIRY_SKEW_SECONDS = 60  # treat a token as expired a little early


@dataclass(frozen=True)
class Token:
    access_token: str
    refresh_token: str | None
    expires_at: float  # unix time when the access token stops working
    scopes: tuple[str, ...]

    def expired(self, now: float) -> bool:
        return now >= self.expires_at - EXPIRY_SKEW_SECONDS

    def to_json(self) -> str:
        return json.dumps(
            {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "expires_at": self.expires_at,
                "scopes": list(self.scopes),
            }
        )

    @classmethod
    def from_json(cls, raw: str) -> "Token":
        data: dict[str, Any] = json.loads(raw)
        return cls(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=float(data["expires_at"]),
            scopes=tuple(data.get("scopes", [])),
        )

    def __repr__(self) -> str:  # never show secrets, even by accident in a log or traceback
        return f"Token(scopes={self.scopes}, has_refresh_token={self.refresh_token is not None})"


class TokenStore:
    """Saves one token in the OS keyring. `backend` is replaced by a fake in tests."""

    def __init__(self, backend: Any = None):
        self._keyring = backend or keyring

    def _guard(self, action: str, call):
        try:
            return call()
        except KeyringError as exc:
            raise AuthFailedError(
                f"Could not {action} the login in the OS keyring: {type(exc).__name__}. "
                "Make sure a keyring service is available."
            ) from None

    def load(self) -> Token | None:
        raw = self._guard("read", lambda: self._keyring.get_password(SERVICE, USERNAME))
        if not raw:
            return None
        try:
            return Token.from_json(raw)
        except (ValueError, KeyError, TypeError):  # damaged entry: treat as signed out
            return None

    def save(self, token: Token) -> None:
        self._guard("save", lambda: self._keyring.set_password(SERVICE, USERNAME, token.to_json()))

    def delete(self) -> bool:
        """Remove the token. Returns False if there was none."""
        if not self._guard("read", lambda: self._keyring.get_password(SERVICE, USERNAME)):
            return False
        try:
            self._keyring.delete_password(SERVICE, USERNAME)
        except keyring.errors.PasswordDeleteError:
            return False
        except KeyringError as exc:
            raise AuthFailedError(
                f"Could not remove the login from the OS keyring: {type(exc).__name__}."
            ) from None
        return True
