"""PKCE helpers (RFC 7636): proof that the app that starts a login is the one that finishes it."""

import base64
import hashlib
import secrets


def new_verifier() -> str:
    """A random secret kept in memory for one login (86 characters, allowed: 43 to 128)."""
    return secrets.token_urlsafe(64)


def challenge_for(verifier: str) -> str:
    """S256 challenge: base64url(sha256(verifier)) without padding."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def new_state() -> str:
    """Random value that must come back unchanged, so a forged redirect is rejected."""
    return secrets.token_urlsafe(32)
