"""Command line (UI-4):

    python -m ytmcp auth login [--write] | status | logout
    python -m ytmcp playlist confirm <proposal_id>

Prints plain messages. Never prints tokens, codes or secrets, and errors
show a code, a message and what to do about it (UI-3).
"""

import argparse
import sys
import time
from collections.abc import Callable, Sequence
from typing import Any

from dotenv import load_dotenv

from ytmcp.auth import (
    SCOPE_READONLY,
    SCOPE_WRITE,
    AuthService,
    OAuthClient,
    OAuthConfig,
    TokenStore,
)
from ytmcp.cache import Cache, default_cache_path
from ytmcp.errors import ProposalUsedError, YtmcpError
from ytmcp.proposals import CONFIRMED, ProposalStore
from ytmcp.services.playlists import load_open_proposal


def build_auth_service() -> AuthService:
    return AuthService(OAuthClient(OAuthConfig.from_env()), TokenStore())


def build_store() -> ProposalStore:
    return ProposalStore(Cache(default_cache_path()))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m ytmcp")
    commands = parser.add_subparsers(dest="command", required=True)
    auth = commands.add_parser("auth", help="sign in to Google")
    actions = auth.add_subparsers(dest="action", required=True)
    login = actions.add_parser("login", help="sign in with Google (read-only access by default)")
    login.add_argument(
        "--write",
        action="store_true",
        help="also allow creating playlists (needed once, before the first create_playlist)",
    )
    actions.add_parser("status", help="show whether you are signed in")
    actions.add_parser("logout", help="sign out and remove the saved login")
    playlist = commands.add_parser("playlist", help="playlist proposals")
    steps = playlist.add_subparsers(dest="action", required=True)
    confirm = steps.add_parser("confirm", help="confirm a proposal so create_playlist can use it")
    confirm.add_argument("proposal_id")
    return parser


def _run_auth(
    action: str, service: AuthService, out: Callable[[str], Any], write: bool = False
) -> None:
    if action == "login":
        service.login(
            scopes=(SCOPE_WRITE,) if write else (SCOPE_READONLY,),
            announce=lambda url: out(
                f"Opening your browser to sign in. If it does not open, visit:\n{url}"
            ),
        )
        out("Signed in. Access: read and write (can create playlists)." if write else "Signed in. Access: read-only.")
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


def _minutes(seconds: int) -> int:
    return round(seconds / 60)


def _run_playlist_confirm(
    proposal_id: str,
    store_factory: Callable[[], ProposalStore],
    out: Callable[[str], Any],
    ask: Callable[[str], str],
    is_terminal: Callable[[], bool],
    now: Callable[[], float],
) -> int:
    """A person looks at the proposal and types yes. It refuses to run without a real terminal,
    so a program (or an AI running shell commands for you) cannot confirm on your behalf."""
    if not is_terminal():
        out("This command must be run by a person in an interactive terminal. It cannot be scripted.")
        return 1
    store = store_factory()  # only now: a refused run must not even open the database
    proposal = load_open_proposal(store, proposal_id, now())
    if proposal.status == CONFIRMED:
        out("Already confirmed. Ask the AI to call create_playlist with the same proposal_id and content_hash.")
        return 0
    out(f"Playlist: {proposal.title}  (PRIVATE, {len(proposal.videos)} videos)")
    for number, video in enumerate(proposal.videos, start=1):
        out(f"  {number:>2}. {video.title}  [{_minutes(video.duration_seconds)} min]")
    total = sum(v.duration_seconds for v in proposal.videos)
    left = max(int(proposal.expires_at - now()) // 60, 0)
    out(f"Total: about {_minutes(total)} min. This proposal expires in about {left} min.")
    if ask("Type yes to allow creating this playlist on your YouTube account: ").strip().lower() != "yes":
        out("Not confirmed. Nothing was created.")
        return 1
    if not store.confirm(proposal.id, now()):
        raise ProposalUsedError("That proposal was already used or has just expired.")
    out("Confirmed. Now ask the AI to call create_playlist again with the same proposal_id and content_hash.")
    return 0


def main(
    argv: Sequence[str] | None = None,
    service_factory: Callable[[], AuthService] = build_auth_service,
    out: Callable[[str], Any] = print,
    store_factory: Callable[[], ProposalStore] = build_store,
    ask: Callable[[str], str] = input,
    is_terminal: Callable[[], bool] = lambda: sys.stdin.isatty() and sys.stdout.isatty(),
    now: Callable[[], float] = time.time,
) -> int:
    load_dotenv()
    args = _parser().parse_args(argv)
    try:
        if args.command == "playlist":
            return _run_playlist_confirm(args.proposal_id, store_factory, out, ask, is_terminal, now)
        _run_auth(args.action, service_factory(), out, write=getattr(args, "write", False))
    except YtmcpError as exc:
        out(f"Error [{exc.code}]: {exc}\nFix: {exc.remediation}")
        return 1
    return 0
