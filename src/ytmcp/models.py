from dataclasses import dataclass, field


@dataclass(frozen=True)
class Video:
    id: str
    title: str
    description: str
    channel_id: str
    channel_title: str
    tags: list[str] = field(default_factory=list)
    category_id: str | None = None
    language: str | None = None
    duration_seconds: int = 0
    is_live: bool = False


@dataclass(frozen=True)
class Channel:
    id: str
    title: str
    description: str
    keywords: list[str] = field(default_factory=list)
    subscriber_count: int | None = None  # None when hidden
    handle: str | None = None  # e.g. "@rustlab"
    topics: list[str] = field(default_factory=list)  # from topicDetails


@dataclass(frozen=True)
class LikedVideo:
    """A video the signed-in user liked, with the date they liked it (ADR-010)."""

    video_id: str
    liked_at: str  # ISO 8601, e.g. "2026-11-11T04:28:52Z"


@dataclass(frozen=True)
class Subscription:
    """A channel the signed-in user subscribes to."""

    channel_id: str
    title: str
    subscribed_at: str | None = None
