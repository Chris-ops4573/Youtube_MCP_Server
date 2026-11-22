"""Live provider for YouTube Data API v3, using an API key (SE-6, FR-1.2).

Only public data is read (videos, search, channels), so no OAuth is needed.
Every call is counted against the daily quota (FR-7.1). Failed calls are
retried at most 3 times with backoff; quotaExceeded is never retried (SRS 3.4).
The API key is only ever put in the request URL, never in errors or logs.
"""

import json
import shlex
import time
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

from ytmcp.durations import parse_duration
from ytmcp.errors import ApiKeyMissingError, QuotaExceededError, YouTubeApiError
from ytmcp.models import Channel, Video
from ytmcp.providers.base import VideoProvider
from ytmcp.quota import MAX_IDS_PER_CALL, QuotaTracker

API_URL = "https://www.googleapis.com/youtube/v3"
MAX_RETRIES = 3
TIMEOUT_SECONDS = 10
RETRY_STATUSES = {429, 500, 502, 503, 504}
RETRY_REASONS = {"rateLimitExceeded", "userRateLimitExceeded", "backendError"}
QUOTA_REASONS = {"quotaExceeded", "dailyLimitExceeded"}

# Takes a full URL, returns (HTTP status, parsed JSON body). Tests pass a fake.
Fetch = Callable[[str], tuple[int, dict[str, Any]]]


def urllib_fetch(url: str) -> tuple[int, dict[str, Any]]:
    try:
        with urlopen(url, timeout=TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read())
        except ValueError:
            return exc.code, {}


def _error_reason(body: dict[str, Any]) -> str | None:
    errors = body.get("error", {}).get("errors") or [{}]
    return errors[0].get("reason")


def _language(snippet: dict[str, Any]) -> str | None:
    """'en-US' -> 'en', so videos in the same language compare equal."""
    lang = snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage")
    return lang.split("-")[0].lower() if lang else None


def _duration(value: str | None) -> int:
    try:
        return parse_duration(value or "")
    except ValueError:
        return 0


def _keywords(value: str) -> list[str]:
    """Channel keywords are space-separated, with quotes around phrases."""
    try:
        return shlex.split(value)
    except ValueError:
        return value.split()


def _to_video(item: dict[str, Any]) -> Video:
    snippet = item.get("snippet", {})
    return Video(
        id=item["id"],
        title=snippet.get("title", ""),
        description=snippet.get("description", ""),
        channel_id=snippet.get("channelId", ""),
        channel_title=snippet.get("channelTitle", ""),
        tags=snippet.get("tags", []),
        category_id=snippet.get("categoryId"),
        language=_language(snippet),
        duration_seconds=_duration(item.get("contentDetails", {}).get("duration")),
        is_live=snippet.get("liveBroadcastContent") in ("live", "upcoming"),
    )


def _to_channel(item: dict[str, Any]) -> Channel:
    snippet = item.get("snippet", {})
    stats = item.get("statistics", {})
    keywords = item.get("brandingSettings", {}).get("channel", {}).get("keywords", "")
    hidden = stats.get("hiddenSubscriberCount") or "subscriberCount" not in stats
    return Channel(
        id=item["id"],
        title=snippet.get("title", ""),
        description=snippet.get("description", ""),
        keywords=_keywords(keywords),
        subscriber_count=None if hidden else int(stats["subscriberCount"]),
    )


class YouTubeProvider(VideoProvider):
    def __init__(
        self,
        api_key: str | None,
        quota: QuotaTracker | None = None,
        fetch: Fetch = urllib_fetch,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._api_key = api_key
        self._quota = quota or QuotaTracker()
        self._fetch = fetch
        self._sleep = sleep

    def ensure_budget(self, units: int) -> None:
        self._quota.ensure_budget(units)

    def _get(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Call one API method (e.g. 'videos.list') with retries."""
        if not self._api_key:
            raise ApiKeyMissingError("No YouTube API key is configured.")
        resource = method.split(".")[0]
        url = f"{API_URL}/{resource}?{urlencode({**params, 'key': self._api_key})}"

        for attempt in range(MAX_RETRIES + 1):
            self._quota.record(method)
            try:
                status, body = self._fetch(url)
            except OSError:  # network error or timeout
                status, body = None, {}
            if status == 200:
                return body

            reason = _error_reason(body)
            if reason in QUOTA_REASONS:
                raise QuotaExceededError("YouTube says the daily quota is used up.")
            retryable = status is None or status in RETRY_STATUSES or reason in RETRY_REASONS
            if not retryable or attempt == MAX_RETRIES:
                raise YouTubeApiError(
                    f"YouTube API call {method} failed (status {status}, reason {reason})."
                )
            self._sleep(2**attempt)  # 1s, 2s, 4s
        raise AssertionError("unreachable")

    def get_videos(self, video_ids: list[str]) -> list[Video]:
        ids = list(dict.fromkeys(video_ids))  # drop duplicates, keep order
        found: dict[str, Video] = {}
        for start in range(0, len(ids), MAX_IDS_PER_CALL):
            batch = ids[start : start + MAX_IDS_PER_CALL]
            body = self._get(
                "videos.list",
                {"part": "snippet,contentDetails", "id": ",".join(batch), "maxResults": len(batch)},
            )
            for item in body.get("items", []):
                found[item["id"]] = _to_video(item)
        return [found[i] for i in ids if i in found]

    def search_videos(self, query: str, max_results: int = 25) -> list[Video]:
        """search.list finds IDs; videos.list fills in full metadata (FR-1.2)."""
        body = self._get(
            "search.list",
            {"part": "id", "type": "video", "q": query, "maxResults": min(max(max_results, 1), 50)},
        )
        ids = [i["id"]["videoId"] for i in body.get("items", []) if i.get("id", {}).get("videoId")]
        return self.get_videos(ids)[:max_results]

    def get_channels(self, channel_ids: list[str]) -> list[Channel]:
        ids = list(dict.fromkeys(channel_ids))
        found: dict[str, Channel] = {}
        for start in range(0, len(ids), MAX_IDS_PER_CALL):
            batch = ids[start : start + MAX_IDS_PER_CALL]
            body = self._get(
                "channels.list",
                {"part": "snippet,statistics,brandingSettings", "id": ",".join(batch)},
            )
            for item in body.get("items", []):
                found[item["id"]] = _to_channel(item)
        return [found[i] for i in ids if i in found]
