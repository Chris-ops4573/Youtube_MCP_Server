"""Command line (UI-4):

    python -m ytmcp auth login [--write] | status | logout
    python -m ytmcp playlist confirm <proposal_id>
    python -m ytmcp quota status
    python -m ytmcp serve
    python -m ytmcp local-check

Prints plain messages. Never prints tokens, codes or secrets, and errors
show a code, a message and what to do about it (UI-3).
"""

import argparse
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from datetime import time as day_time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from ytmcp.auth import SCOPE_READONLY, SCOPE_WRITE, AuthService
from ytmcp.config import build_auth_service, build_quota_tracker, build_store
from ytmcp.errors import ProposalUsedError, YtmcpError
from ytmcp.proposals import CONFIRMED, ProposalStore
from ytmcp.quota import DAILY_LIMIT, RESERVE, QuotaTracker
from ytmcp.services.playlists import load_open_proposal

ROOT = Path(__file__).resolve().parents[2]
PACIFIC = ZoneInfo("America/Los_Angeles")  # YouTube resets quota at midnight Pacific time


def _pacific_now() -> datetime:
    return datetime.now(PACIFIC)


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
    quota = commands.add_parser("quota", help="how much of today's YouTube quota is used")
    quota_actions = quota.add_subparsers(dest="action", required=True)
    quota_actions.add_parser("status", help="show units used, left and when the quota resets")
    commands.add_parser("serve", help="start the MCP server (same as python -m ytmcp.server)")
    commands.add_parser("local-check", help="build, lint, tests and a server check (SK-2)")
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


def _run_quota_status(
    quota_factory: Callable[[Callable[[], Any]], QuotaTracker],
    clock: Callable[[], datetime],
    out: Callable[[str], Any],
) -> int:
    """Today's count (Pacific time). It only counts calls made by this server."""
    now = clock()
    tracker = quota_factory(lambda: clock().date())
    midnight = datetime.combine(now.date() + timedelta(days=1), day_time(0), tzinfo=PACIFIC)
    left = midnight.astimezone(UTC) - now.astimezone(UTC)  # in UTC, so a clock change cannot skew it
    hours, minutes = divmod(int(left.total_seconds()) // 60, 60)
    out(f"Quota for {now.date().isoformat()} (Pacific time)")
    out(f"  Used: {tracker.spent} of {DAILY_LIMIT} units")
    out(f"  Reserve kept back: {RESERVE} units")
    out(f"  Left to use: {tracker.remaining} units")
    out(f"  Resets in {hours} h {minutes} min (midnight Pacific time)")
    out("  Only calls made by this server are counted, not other apps using the same API key.")
    return 0


def _run_local_check(run: Callable[[Sequence[str]], int], out: Callable[[str], Any], root: Path) -> int:
    script = root / "scripts" / "local_check.py"
    if not script.is_file():
        out(f"Cannot find {script}. Run this from a copy of the project.")
        return 1
    return run([sys.executable, str(script)])


def _run_serve() -> int:
    from ytmcp import (
        server,  # only here: the server is not needed for the other commands
    )

    server.main()
    return 0


def _run_subprocess(command: Sequence[str]) -> int:
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def main(
    argv: Sequence[str] | None = None,
    service_factory: Callable[[], AuthService] = build_auth_service,
    out: Callable[[str], Any] = print,
    store_factory: Callable[[], ProposalStore] = build_store,
    ask: Callable[[str], str] = input,
    is_terminal: Callable[[], bool] = lambda: sys.stdin.isatty() and sys.stdout.isatty(),
    now: Callable[[], float] = time.time,
    quota_factory: Callable[[Callable[[], Any]], QuotaTracker] = build_quota_tracker,
    clock: Callable[[], datetime] = _pacific_now,
    serve: Callable[[], int] = _run_serve,
    run_command: Callable[[Sequence[str]], int] = _run_subprocess,
) -> int:
    load_dotenv()
    args = _parser().parse_args(argv)
    try:
        if args.command == "quota":
            return _run_quota_status(quota_factory, clock, out)
        if args.command == "serve":
            return serve()
        if args.command == "local-check":
            return _run_local_check(run_command, out, ROOT)
        if args.command == "playlist":
            return _run_playlist_confirm(args.proposal_id, store_factory, out, ask, is_terminal, now)
        _run_auth(args.action, service_factory(), out, write=getattr(args, "write", False))
    except YtmcpError as exc:
        out(f"Error [{exc.code}]: {exc}\nFix: {exc.remediation}")
        return 1
    return 0
