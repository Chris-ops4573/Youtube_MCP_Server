"""Propose and create playlists (FR-5).

`propose_playlist` only reads and saves a plan. `create_playlist` is the only
code that writes to YouTube, and it refuses unless every check passes:
a live, unused proposal made by this server; a matching content hash; a person's
confirmation; enough quota; and a login with write permission.
"""

import hmac
import math
from dataclasses import dataclass

from ytmcp.errors import (
    ConfirmationRequiredError,
    ProposalExpiredError,
    ProposalMismatchError,
    ProposalNotFoundError,
    ProposalUsedError,
    YouTubeApiError,
    YtmcpError,
)
from ytmcp.playlist_planner import (
    MAX_TITLE_CHARS,
    SEARCH_SIZE,
    Constraints,
    Selection,
    clean_text,
    select_videos,
)
from ytmcp.proposals import (
    CONFIRMED,
    CREATED,
    FAILED,
    PARTIAL,
    PROPOSAL_TTL_SECONDS,
    PROPOSED,
    USED_STATUSES,
    Proposal,
    ProposalStore,
    ProposedVideo,
    content_hash,
    new_proposal_id,
)
from ytmcp.providers.base import AccountProvider, VideoProvider
from ytmcp.quota import COSTS, MAX_IDS_PER_CALL


@dataclass(frozen=True)
class CreateResult:
    playlist_id: str
    status: str  # "created" or "partial"
    added: list[str]
    failed: list[tuple[str, str]]  # (video ID, reason)
    not_attempted: list[str]
    stopped_because: str | None  # error code that stopped the loop early, if any


def estimate_propose_cost() -> int:
    """Quota units to build a proposal: one search plus the video details."""
    return COSTS["search.list"] + math.ceil(SEARCH_SIZE / MAX_IDS_PER_CALL) * COSTS["videos.list"]


def estimate_create_cost(video_count: int) -> int:
    """Quota units to create a playlist: 50 for the playlist and 50 per video (FR-5.6)."""
    return COSTS["playlists.insert"] + video_count * COSTS["playlistItems.insert"]


def propose_playlist(
    provider: VideoProvider, store: ProposalStore, constraints: Constraints, now: float
) -> tuple[Proposal, Selection]:
    """Find videos and save a proposal. Writes nothing to YouTube."""
    provider.ensure_budget(estimate_propose_cost())  # before any API call (FR-7.1)
    candidates = provider.search_videos(constraints.topic, SEARCH_SIZE)
    selection = select_videos(candidates, constraints)

    videos = tuple(
        ProposedVideo(
            v.id, clean_text(v.title, 100), clean_text(v.channel_title, 60), v.duration_seconds
        )
        for v in selection.videos
    )
    description = clean_text(
        f"Made with the YouTube Video MCP Server. Topic: {constraints.topic}", 5000
    )
    proposal = Proposal(
        id=new_proposal_id(),
        content_hash=content_hash(constraints.title, description, [v.id for v in videos]),
        title=clean_text(constraints.title, MAX_TITLE_CHARS),
        description=description,
        videos=videos,
        constraints={
            "topic": constraints.topic,
            "total_minutes": constraints.total_minutes,
            "max_video_minutes": constraints.max_video_minutes,
            "min_video_minutes": constraints.min_video_minutes,
            "language": constraints.language,
        },
        created_at=now,
        expires_at=now + PROPOSAL_TTL_SECONDS,
    )
    store.save(proposal)
    return proposal, selection


def load_open_proposal(store: ProposalStore, proposal_id: str, now: float) -> Proposal:
    """A proposal that exists, has not been used and has not expired."""
    proposal = store.get(proposal_id.strip()) if isinstance(proposal_id, str) else None
    if proposal is None:
        raise ProposalNotFoundError("There is no proposal with that ID.")
    if proposal.status in USED_STATUSES:
        raise ProposalUsedError(f"That proposal was already used (status: {proposal.status}).")
    if now >= proposal.expires_at:
        raise ProposalExpiredError("That proposal has expired.")
    return proposal


def prepare_create(
    store: ProposalStore, proposal_id: str, given_hash: str, now: float
) -> Proposal:
    """Everything that must be true before a person is even asked (FR-5.5)."""
    proposal = load_open_proposal(store, proposal_id, now)
    stored_matches = hmac.compare_digest(
        proposal.content_hash,
        content_hash(proposal.title, proposal.description, proposal.video_ids),
    )
    given_matches = isinstance(given_hash, str) and hmac.compare_digest(
        given_hash.strip(), proposal.content_hash
    )
    if not (stored_matches and given_matches):
        raise ProposalMismatchError("The content hash does not match this proposal.")
    return proposal


def decline(store: ProposalStore, proposal_id: str) -> None:
    store.decline(proposal_id)


def create_playlist(
    account: AccountProvider,
    store: ProposalStore,
    proposal_id: str,
    given_hash: str,
    user_approved: bool,
    now: float,
) -> CreateResult:
    """Create the playlist. `user_approved` means a person said yes to the client's question
    just now. Otherwise the proposal must already be confirmed in the terminal."""
    proposal = prepare_create(store, proposal_id, given_hash, now)
    if proposal.status == CONFIRMED:
        from_status = CONFIRMED
    elif user_approved:
        from_status = PROPOSED
    else:
        raise ConfirmationRequiredError(proposal.id)

    # both of these run before the proposal is used up, so the user can fix them and retry
    account.ensure_budget(estimate_create_cost(len(proposal.videos)))  # FR-5.6
    account.ensure_write_access()  # FR-6.1

    if not store.claim(proposal.id, now, from_status):
        raise ProposalUsedError("That proposal was already used or has just expired.")
    try:
        playlist_id = account.create_playlist(proposal.title, proposal.description)
    except Exception:
        store.finish(proposal.id, FAILED)  # the playlist may or may not exist: do not retry
        raise

    added: list[str] = []
    failed: list[tuple[str, str]] = []
    not_attempted: list[str] = []
    stopped: str | None = None
    for index, video in enumerate(proposal.videos):
        try:
            account.add_video(playlist_id, video.id)
            added.append(video.id)
        except YouTubeApiError as exc:  # this video only (deleted, already there, ...)
            failed.append((video.id, exc.reason or "error"))
        except YtmcpError as exc:  # quota or login problem: every later call would fail too
            stopped = exc.code
            not_attempted = [v.id for v in proposal.videos[index:]]
            break

    status = CREATED if not failed and not not_attempted else PARTIAL
    store.finish(proposal.id, status, playlist_id)
    return CreateResult(playlist_id, status, added, failed, not_attempted, stopped)
