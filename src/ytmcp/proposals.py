"""Playlist proposals: saved, expiring plans that a person must confirm (FR-5.4, FR-5.5).

A proposal is stored with a random ID, a fingerprint of its content and a
15 minute expiry. Only a proposal made by `propose_playlist` can ever be
created, and only once.
"""

import hashlib
import json
import secrets
from dataclasses import dataclass

from ytmcp.database import Database

PROPOSAL_TTL_SECONDS = 15 * 60
PRIVACY = "private"  # playlists are always created private (SRS 5.2)

# status values
PROPOSED = "proposed"
CONFIRMED = "confirmed"  # a person confirmed it in the terminal
CREATING = "creating"
CREATED = "created"
PARTIAL = "partial"  # created, but some videos could not be added
FAILED = "failed"
DECLINED = "declined"
USED_STATUSES = (CREATING, CREATED, PARTIAL, FAILED, DECLINED)


@dataclass(frozen=True)
class ProposedVideo:
    id: str
    title: str
    channel: str
    duration_seconds: int


@dataclass(frozen=True)
class Proposal:
    id: str
    content_hash: str
    title: str
    description: str
    videos: tuple[ProposedVideo, ...]
    constraints: dict
    created_at: float
    expires_at: float
    status: str = PROPOSED
    playlist_id: str | None = None

    @property
    def video_ids(self) -> list[str]:
        return [v.id for v in self.videos]


def content_hash(title: str, description: str, video_ids: list[str]) -> str:
    """A short fingerprint of exactly what would be created. The AI client has to send it
    back, which proves it saw this exact proposal; it is not a secret."""
    payload = json.dumps(
        {"title": title, "description": description, "privacy": PRIVACY, "videos": video_ids},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def new_proposal_id() -> str:
    return secrets.token_urlsafe(12)


class ProposalStore:
    def __init__(self, cache: Database):
        self._cache = cache

    def save(self, proposal: Proposal) -> None:
        self._cache.put_proposal(
            {
                "id": proposal.id,
                "content_hash": proposal.content_hash,
                "title": proposal.title,
                "description": proposal.description,
                "videos": json.dumps(
                    [
                        [v.id, v.title, v.channel, v.duration_seconds]
                        for v in proposal.videos
                    ]
                ),
                "constraints": json.dumps(proposal.constraints),
                "created_at": proposal.created_at,
                "expires_at": proposal.expires_at,
                "status": proposal.status,
                "playlist_id": proposal.playlist_id,
            }
        )

    def get(self, proposal_id: str) -> Proposal | None:
        row = self._cache.get_proposal(proposal_id)
        if row is None:
            return None
        return Proposal(
            id=row["id"],
            content_hash=row["content_hash"],
            title=row["title"],
            description=row["description"],
            videos=tuple(ProposedVideo(*v) for v in json.loads(row["videos"])),
            constraints=json.loads(row["constraints"]),
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            status=row["status"],
            playlist_id=row["playlist_id"],
        )

    def confirm(self, proposal_id: str, now: float) -> bool:
        """A person confirmed in the terminal. Only works on a live, unused proposal."""
        return self._cache.change_proposal_status(
            proposal_id, CONFIRMED, (PROPOSED,), not_expired_at=now
        )

    def claim(self, proposal_id: str, now: float, from_status: str) -> bool:
        """Take the proposal for creation. Only one caller can ever succeed."""
        return self._cache.change_proposal_status(
            proposal_id, CREATING, (from_status,), not_expired_at=now
        )

    def finish(self, proposal_id: str, status: str, playlist_id: str | None = None) -> None:
        self._cache.change_proposal_status(
            proposal_id, status, (CREATING,), playlist_id=playlist_id
        )

    def decline(self, proposal_id: str) -> bool:
        return self._cache.change_proposal_status(proposal_id, DECLINED, (PROPOSED, CONFIRMED))
