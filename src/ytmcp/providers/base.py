from abc import ABC, abstractmethod

from ytmcp.models import Channel, LikedVideo, Subscription, Video


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
    def get_recent_uploads(self, channel_id: str, max_results: int = 10) -> list[str]:
        """Titles of the channel's most recent public uploads, newest first."""

    def category_names(self, region: str = "US") -> dict[str, str]:
        """Names of the video categories, by category ID (1 quota unit).

        Providers that cannot look them up return an empty dict, and the callers then show
        a generic label instead of the name.
        """
        return {}

    def ensure_budget(self, units: int) -> None:
        """Raise QuotaExceededError if `units` quota units are not available (FR-7.1).

        Providers that do not use quota (e.g. fixtures) keep this no-op.
        """


class AccountProvider(ABC):
    """Everything done as the signed-in user, with the user's own login (SE-6): reading the
    account (likes, subscriptions, playlists: FR-3, FR-4) and creating playlists (FR-5).
    Separate from VideoProvider on purpose: VideoProvider reads public data with an API key.
    Nothing here can edit or delete (SRS 5.2)."""

    @abstractmethod
    def liked_videos(self, limit: int) -> list[LikedVideo]:
        """The newest `limit` videos the user liked, newest first, with the date liked."""

    @abstractmethod
    def subscriptions(self, limit: int) -> list[Subscription]:
        """Up to `limit` channels the user subscribes to."""

    @abstractmethod
    def playlist_video_ids(self, max_playlists: int) -> set[str]:
        """IDs of videos in up to `max_playlists` of the user's own playlists (first 50 of each)."""

    @abstractmethod
    def ensure_write_access(self) -> None:
        """Raise WriteAccessRequiredError unless the user has signed in with write permission."""

    @abstractmethod
    def ensure_budget(self, units: int) -> None:
        """Raise QuotaExceededError if `units` quota units are not available (FR-5.6)."""

    @abstractmethod
    def create_playlist(self, title: str, description: str) -> str:
        """Create a new PRIVATE playlist and return its ID."""

    @abstractmethod
    def add_video(self, playlist_id: str, video_id: str) -> None:
        """Add one video to a playlist created by this server."""
