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