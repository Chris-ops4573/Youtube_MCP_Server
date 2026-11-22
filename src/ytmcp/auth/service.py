"""Sign in, stay signed in, sign out (FR-6.1, FR-6.2).

`get_access_token` is what later features (FR-3, FR-4, FR-5) call: it
returns a valid access token, renewing it when needed, or raises
AuthRequiredError so the user is asked to sign in again.
"""

import hmac
import time
import webbrowser
from collections.abc import Callable
from typing import Any

from ytmcp.auth import pkce
from ytmcp.auth.loopback import LoopbackReceiver
from ytmcp.auth.oauth import SCOPE_READONLY, SCOPE_WRITE, OAuthClient
from ytmcp.auth.tokens import Token, TokenStore
from ytmcp.errors import AuthFailedError, AuthRequiredError


def _has_scope(token: Token, scope: str) -> bool:
    if scope in token.scopes:
        return True
    # the full YouTube scope also allows everything the read-only one does
    return scope == SCOPE_READONLY and SCOPE_WRITE in token.scopes


class AuthService:
    def __init__(
        self,
        client: OAuthClient,
        store: TokenStore,
        receiver_factory: Callable[[], LoopbackReceiver] = LoopbackReceiver,
        open_browser: Callable[[str], Any] = webbrowser.open,
        now: Callable[[], float] = time.time,
    ):
        self._client = client
        self._store = store
        self._receiver_factory = receiver_factory
        self._open_browser = open_browser
        self._now = now

    def login(
        self,
        scopes: tuple[str, ...] = (SCOPE_READONLY,),
        timeout: float = 120,
        announce: Callable[[str], None] = lambda url: None,
    ) -> Token:
        """Open the browser, wait for Google to send the user back, save the token."""
        verifier = pkce.new_verifier()
        state = pkce.new_state()
        with self._receiver_factory() as receiver:
            url = self._client.build_auth_url(
                receiver.redirect_uri, scopes, state, pkce.challenge_for(verifier)
            )
            announce(url)  # lets the CLI show the link in case the browser does not open
            self._open_browser(url)
            params = receiver.wait(timeout)
            redirect_uri = receiver.redirect_uri

        if "error" in params:
            reason = params["error"] if params["error"].isidentifier() else "unknown"
            raise AuthFailedError(f"Google sign-in was not completed ({reason}).")
        if not hmac.compare_digest(params.get("state", ""), state):
            raise AuthFailedError("The sign-in response did not match this login attempt.")
        if not params.get("code"):
            raise AuthFailedError("Google did not send a sign-in code.")

        token = self._client.exchange_code(params["code"], verifier, redirect_uri)
        self._store.save(token)
        return token

    def get_access_token(self, scope: str = SCOPE_READONLY) -> str:
        token = self._store.load()
        if token is None:
            raise AuthRequiredError("You are not signed in.")
        if not _has_scope(token, scope):
            raise AuthRequiredError("Your login does not include the permission this needs.")
        if token.expired(self._now()):
            try:
                token = self._client.refresh(token)
            except AuthRequiredError:
                self._store.delete()  # useless now; keep `status` honest
                raise
            self._store.save(token)
        return token.access_token

    def status(self) -> dict[str, Any]:
        """Facts about the login. Never includes the tokens themselves."""
        token = self._store.load()
        if token is None:
            return {"signed_in": False}
        return {
            "signed_in": True,
            "can_write": SCOPE_WRITE in token.scopes,
            "has_refresh_token": token.refresh_token is not None,
            "access_token_valid_seconds": max(int(token.expires_at - self._now()), 0),
        }

    def logout(self) -> dict[str, bool]:
        token = self._store.load()
        if token is None:
            return {"was_signed_in": False, "revoked": False}
        revoked = self._client.revoke(token)  # best effort; we delete locally either way
        self._store.delete()
        return {"was_signed_in": True, "revoked": revoked}
