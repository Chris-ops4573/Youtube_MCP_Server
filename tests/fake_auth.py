"""Fakes for the login tests: an in-memory keyring and a pretend Google (TQ-5).

Nothing here touches the real keyring, the network or a browser.
"""

from urllib.parse import parse_qs, urlparse

from keyring.errors import KeyringError, PasswordDeleteError

from ytmcp.auth.oauth import OAuthClient, OAuthConfig
from ytmcp.auth.tokens import Token


class MemoryKeyring:
    def __init__(self):
        self.items: dict[tuple[str, str], str] = {}

    def get_password(self, service, username):
        return self.items.get((service, username))

    def set_password(self, service, username, password):
        self.items[(service, username)] = password

    def delete_password(self, service, username):
        if (service, username) not in self.items:
            raise PasswordDeleteError("not found")
        del self.items[(service, username)]


class BrokenKeyring:
    """Like a machine with no keyring service."""

    def get_password(self, *args):
        raise KeyringError("no backend")

    set_password = delete_password = get_password


class FakeGoogle:
    """Use as OAuthClient's `post`. Queue (status, body) pairs to answer in order."""

    def __init__(self, queue=None):
        self.queue = list(queue or [])
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __call__(self, url, data):
        self.calls.append((url, data))
        if self.queue:
            item = self.queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        return 200, {}


class FakeReceiver:
    """Stands in for the browser redirect. Set `respond` to build the redirect parameters
    from the sign-in URL (so it can echo back the real `state`)."""

    redirect_uri = "http://127.0.0.1:5555/callback"

    def __init__(self, respond=None):
        self.respond = respond or (lambda url_params: {"code": "the-code", "state": url_params["state"]})
        self.url_params: dict[str, str] = {}
        self.timeout_seen = None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return None

    def remember_url(self, url):
        self.url_params = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}

    def wait(self, timeout=120):
        self.timeout_seen = timeout
        return self.respond(self.url_params)


GOOD_TOKEN_BODY = {
    "access_token": "ACCESS-1",
    "refresh_token": "REFRESH-1",
    "expires_in": 3600,
    "scope": "https://www.googleapis.com/auth/youtube.readonly",
    "token_type": "Bearer",
}


def make_client(queue=None, secret="client-secret", now=lambda: 1000.0):
    google = FakeGoogle(queue)
    return OAuthClient(OAuthConfig("client-id", secret), post=google, now=now), google


def make_token(expires_at=5000.0, refresh="REFRESH-1", scopes=("https://www.googleapis.com/auth/youtube.readonly",)):
    return Token("ACCESS-1", refresh, expires_at, scopes)
