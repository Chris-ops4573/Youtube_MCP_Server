"""Command line: python -m ytmcp auth login | status | logout  (UI-4).

Prints plain messages. Never prints tokens, codes or secrets, and errors
show a code, a message and what to do about it (UI-3).
"""

import argparse
from collections.abc import Callable, Sequence
from typing import Any

from dotenv import load_dotenv

from ytmcp.auth import AuthService, OAuthClient, OAuthConfig, TokenStore
from ytmcp.errors import YtmcpError


def build_auth_service() -> AuthService:
    return AuthService(OAuthClient(OAuthConfig.from_env()), TokenStore())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m ytmcp")
    commands = parser.add_subparsers(dest="command", required=True)
    auth = commands.add_parser("auth", help="sign in to Google")
    actions = auth.add_subparsers(dest="action", required=True)
    actions.add_parser("login", help="sign in with Google (read-only access)")
    actions.add_parser("status", help="show whether you are signed in")
    actions.add_parser("logout", help="sign out and remove the saved login")
    return parser


def _run_auth(action: str, service: AuthService, out: Callable[[str], Any]) -> None:
    if action == "login":
        service.login(
            announce=lambda url: out(
                f"Opening your browser to sign in. If it does not open, visit:\n{url}"
            )
        )
        out("Signed in. Access: read-only.")
    elif action == "status":
        info = service.status()
        if not info["signed_in"]:
            out("Not signed in. Run: python -m ytmcp auth login")
            return
        access = "read and write" if info["can_write"] else "read-only"
        refresh = "yes" if info["has_refresh_token"] else "no"
        minutes = info["access_token_valid_seconds"] // 60
        out(f"Signed in. Access: {access}. Can renew: {refresh}. Current access valid for ~{minutes} min.")
    else:
        result = service.logout()
        if not result["was_signed_in"]:
            out("You were not signed in.")
        elif result["revoked"]:
            out("Signed out. Google has been told to cancel the login.")
        else:
            out("Signed out here. Google could not be reached to cancel it; "
                "you can remove access at https://myaccount.google.com/permissions")


def main(
    argv: Sequence[str] | None = None,
    service_factory: Callable[[], AuthService] = build_auth_service,
    out: Callable[[str], Any] = print,
) -> int:
    load_dotenv()
    args = _parser().parse_args(argv)
    try:
        _run_auth(args.action, service_factory(), out)
    except YtmcpError as exc:
        out(f"Error [{exc.code}]: {exc}\nFix: {exc.remediation}")
        return 1
    return 0
