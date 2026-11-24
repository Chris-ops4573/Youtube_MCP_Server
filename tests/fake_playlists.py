"""Fakes for the playlist tests: no network, no YouTube, no real login (TQ-5)."""

from ytmcp.models import Video
from ytmcp.providers.base import AccountProvider, VideoProvider


def make_video(vid, minutes, title=None, language="en", live=False, channel="Chan", seconds=None):
    return Video(
        id=vid,
        title=title or f"Video {vid}",
        description="d",
        channel_id="UC1",
        channel_title=channel,
        language=language,
        duration_seconds=seconds if seconds is not None else minutes * 60,
        is_live=live,
    )


class ListProvider(VideoProvider):
    """Answers every search with the videos it was given, and records what was asked."""

    def __init__(self, videos, budget_error=None):
        self.videos = list(videos)
        self.budget_error = budget_error
        self.searches: list[tuple[str, int]] = []
        self.budget_checks: list[int] = []

    def ensure_budget(self, units):
        self.budget_checks.append(units)
        if self.budget_error:
            raise self.budget_error

    def search_videos(self, query, max_results=25):
        self.searches.append((query, max_results))
        return list(self.videos)

    def get_videos(self, video_ids):
        return []

    def get_channels(self, channel_ids):
        return []

    def get_channel_by_handle(self, handle):
        return None

    def search_channels(self, query, max_results=25):
        return []

    def get_recent_uploads(self, channel_id, max_results=10):
        return []


class FakeAccount(AccountProvider):
    """Records every call in order, and can be told to fail in specific ways."""

    def __init__(
        self,
        create_error=None,
        video_errors=None,
        budget_error=None,
        access_error=None,
        liked=None,
        subscribed=None,
        playlist_ids=None,
        read_error=None,
    ):
        self.create_error = create_error
        self.video_errors = video_errors or {}
        self.budget_error = budget_error
        self.access_error = access_error
        self.liked = list(liked or [])  # LikedVideo objects, newest first
        self.subscribed = list(subscribed or [])  # Subscription objects
        self.playlist_ids = set(playlist_ids or [])
        self.read_error = read_error  # raised by every read, e.g. AuthRequiredError
        self.events: list[tuple] = []

    def ensure_budget(self, units):
        self.events.append(("budget", units))
        if self.budget_error:
            raise self.budget_error

    def ensure_write_access(self):
        self.events.append(("access",))
        if self.access_error:
            raise self.access_error

    def create_playlist(self, title, description):
        self.events.append(("create", title, description))
        if self.create_error:
            raise self.create_error
        return "PLfake"

    def add_video(self, playlist_id, video_id):
        self.events.append(("add", playlist_id, video_id))
        if video_id in self.video_errors:
            raise self.video_errors[video_id]

    def _read(self, name, argument):
        self.events.append((name, argument))
        if self.read_error:
            raise self.read_error

    def liked_videos(self, limit):
        self._read("liked", limit)
        return self.liked[:limit]

    def subscriptions(self, limit):
        self._read("subscriptions", limit)
        return self.subscribed[:limit]

    def playlist_video_ids(self, max_playlists):
        self._read("playlists", max_playlists)
        return set(self.playlist_ids)

    def names(self):
        return [event[0] for event in self.events]

    def added(self):
        return [event[2] for event in self.events if event[0] == "add"]
