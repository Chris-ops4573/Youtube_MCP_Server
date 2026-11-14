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