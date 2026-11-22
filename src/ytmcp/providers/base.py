from abc import ABC, abstractmethod

from ytmcp.models import Channel, Video


class VideoProvider(ABC):
    """All YouTube access goes through this interface (SE-6)."""

    @abstractmethod
    def get_videos(self, video_ids: list[str]) -> list[Video]:
        """Fetch metadata for the given IDs. Missing/private/deleted IDs are omitted."""

    @abstractmethod
    def search_videos(self, query: str, max_results: int = 25) -> list[Video]:
        """Search for videos. Results include full metadata."""

    @abstractmethod
    def get_channels(self, channel_ids: list[str]) -> list[Channel]:
        """Fetch channel metadata. Missing IDs are omitted."""

    @abstractmethod
    def get_channel_by_handle(self, handle: str) -> Channel | None:
        """Look up a channel by @handle. Returns None if there is no such channel."""

    @abstractmethod
    def search_channels(self, query: str, max_results: int = 25) -> list[Channel]:
        """Search for channels. Results include full channel metadata."""

    @abstractmethod
    def get_recent_uploads(self, channel_id: str, max_results: int = 10) -> list[str]:
        """Titles of the channel's most recent public uploads, newest first."""

    def ensure_budget(self, units: int) -> None:
        """Raise QuotaExceededError if `units` quota units are not available (FR-7.1).

        Providers that do not use quota (e.g. fixtures) keep this no-op.
        """
