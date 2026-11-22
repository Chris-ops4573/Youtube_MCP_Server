"""Caching wrapper around another provider (FR-7.2).

Implements the same VideoProvider interface (SE-6), so services do not know
the cache exists. Only IDs that are missing or expired are fetched, which
saves quota: a repeated search costs 0 units instead of 100.
"""

from ytmcp.cache import Cache
from ytmcp.models import Channel, Video
from ytmcp.providers.base import VideoProvider

HOUR = 3600
METADATA_MAX_AGE = 24 * HOUR  # video and channel metadata
SEARCH_MAX_AGE = 1 * HOUR  # search results change more often


class CachingProvider(VideoProvider):
    def __init__(
        self,
        inner: VideoProvider,
        cache: Cache,
        metadata_max_age: float = METADATA_MAX_AGE,
        search_max_age: float = SEARCH_MAX_AGE,
    ):
        self._inner = inner
        self._cache = cache
        self._metadata_max_age = metadata_max_age
        self._search_max_age = search_max_age
        cache.prune(metadata_max_age, search_max_age)

    def ensure_budget(self, units: int) -> None:
        self._inner.ensure_budget(units)

    def get_videos(self, video_ids: list[str]) -> list[Video]:
        ids = list(dict.fromkeys(video_ids))
        found = self._cache.get_videos(ids, self._metadata_max_age)
        missing = [i for i in ids if i not in found]
        if missing:
            fetched = self._inner.get_videos(missing)
            self._cache.put_videos(fetched)
            found.update({v.id: v for v in fetched})
        return [found[i] for i in ids if i in found]

    def search_videos(self, query: str, max_results: int = 25) -> list[Video]:
        ids = self._cache.get_search(query, max_results, self._search_max_age)
        if ids is not None:
            return self.get_videos(ids)
        videos = self._inner.search_videos(query, max_results)
        self._cache.put_videos(videos)
        self._cache.put_search(query, max_results, [v.id for v in videos])
        return videos

    def get_channels(self, channel_ids: list[str]) -> list[Channel]:
        ids = list(dict.fromkeys(channel_ids))
        found = self._cache.get_channels(ids, self._metadata_max_age)
        missing = [i for i in ids if i not in found]
        if missing:
            fetched = self._inner.get_channels(missing)
            self._cache.put_channels(fetched)
            found.update({c.id: c for c in fetched})
        return [found[i] for i in ids if i in found]
