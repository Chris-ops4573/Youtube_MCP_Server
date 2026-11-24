"""All the YouTube HTTP code (SE-6): reads with an API key, writes with the user's login.

Reads (YouTubeProvider, FR-1.2): only public data (videos, search, channels), so no OAuth
is needed. Every call is counted against the daily quota (FR-7.1). Failed calls are retried
at most 3 times with backoff; quotaExceeded is never retried (SRS 3.4). The API key is only
ever put in the request URL, never in errors or logs.

The account (YouTubeAccount, FR-3 to FR-5): acts as the signed-in user with their Google
login. Reading likes, subscriptions and playlists uses the read-only scope and is retried
exactly like the other reads. Creating playlists uses the write scope: the only two write
calls are playlists.insert and playlistItems.insert, so this can create, never edit or
delete (SRS 5.2). Writes are NOT retried. After an unclear failure (a timeout, say) the
playlist may already exist, and a retry would make a duplicate. The login token is only ever
sent to Google in the Authorization header and never appears in errors or logs.
"""

import json
import shlex
import time
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError
from urllib.parse import unquote, urlencode
from urllib.request import Request, urlopen

from ytmcp.auth.oauth import SCOPE_READONLY, SCOPE_WRITE
from ytmcp.durations import parse_duration
from ytmcp.errors import (
    ApiKeyMissingError,
    AuthRequiredError,
    QuotaExceededError,
    WriteAccessRequiredError,
    YouTubeApiError,
    YouTubeChannelRequiredError,
)
from ytmcp.models import Channel, LikedVideo, Subscription, Video
from ytmcp.providers.base import AccountProvider, VideoProvider
from ytmcp.quota import MAX_IDS_PER_CALL, QuotaTracker

API_URL = "https://www.googleapis.com/youtube/v3"
MAX_RETRIES = 3
READ_TIMEOUT_SECONDS = 10
WRITE_TIMEOUT_SECONDS = 15
READ_PAGE_SIZE = 50  # items per page (the API maximum); each page costs 1 quota unit
RETRY_STATUSES = {429, 500, 502, 503, 504}
RETRY_REASONS = {"rateLimitExceeded", "userRateLimitExceeded", "backendError"}
QUOTA_REASONS = {"quotaExceeded", "dailyLimitExceeded"}
CHANNEL_PARTS = "snippet,statistics,brandingSettings,topicDetails"
HIDDEN_UPLOAD_TITLES = {"Private video", "Deleted video"}

# Takes a full URL, returns (HTTP status, parsed JSON body). Tests pass a fake.
Fetch = Callable[[str], tuple[int, dict[str, Any]]]
# The same, plus request headers (the login token). Used to read as the signed-in user.
FetchWithHeaders = Callable[[str, dict[str, str]], tuple[int, dict[str, Any]]]


def urllib_fetch(url: str, headers: dict[str, str] | None = None) -> tuple[int, dict[str, Any]]:
    try:
        with urlopen(Request(url, headers=headers or {}), timeout=READ_TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read())
        except ValueError:
            return exc.code, {}


def _error_reason(body: dict[str, Any]) -> str | None:
    errors = body.get("error", {}).get("errors") or [{}]
    return errors[0].get("reason")


def _get_with_retries(
    fetch: Fetch, url: str, method: str, quota: QuotaTracker, sleep: Callable[[float], None]
) -> dict[str, Any]:
    """Call one read method with retries (SRS 3.4): at most 3 retries, waiting 1, 2 and 4
    seconds, and quotaExceeded is never retried. Every attempt is counted in the quota."""
    for attempt in range(MAX_RETRIES + 1):
        quota.record(method)
        try:
            status, body = fetch(url)
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
                f"YouTube API call {method} failed (status {status}, reason {reason}).",
                reason=reason,
            )
        sleep(2**attempt)  # 1s, 2s, 4s
    raise AssertionError("unreachable")


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


def _topics(item: dict[str, Any]) -> list[str]:
    """topicCategories are Wikipedia URLs; keep the readable last part, sorted."""
    urls = item.get("topicDetails", {}).get("topicCategories", [])
    names = {unquote(u.rsplit("/", 1)[-1]).replace("_", " ") for u in urls}
    return sorted(names)  # YouTube returns these in a changing order


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
        handle=(snippet.get("customUrl") or "").lower() or None,
        topics=_topics(item),
    )


def _to_liked(item: dict[str, Any]) -> LikedVideo | None:
    """One likes-playlist item. snippet.publishedAt is the date the video was liked (ADR-010)."""
    snippet = item.get("snippet", {})
    video_id = item.get("contentDetails", {}).get("videoId")
    if not video_id or snippet.get("title") in HIDDEN_UPLOAD_TITLES:  # private or deleted video
        return None
    return LikedVideo(video_id=video_id, liked_at=snippet.get("publishedAt", ""))


def _to_subscription(item: dict[str, Any]) -> Subscription | None:
    snippet = item.get("snippet", {})
    channel_id = snippet.get("resourceId", {}).get("channelId")
    if not channel_id:
        return None
    return Subscription(channel_id, snippet.get("title", ""), snippet.get("publishedAt"))


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
        return _get_with_retries(self._fetch, url, method, self._quota, self._sleep)

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
                {"part": CHANNEL_PARTS, "id": ",".join(batch)},
            )
            for item in body.get("items", []):
                found[item["id"]] = _to_channel(item)
        return [found[i] for i in ids if i in found]

    def get_channel_by_handle(self, handle: str) -> Channel | None:
        body = self._get("channels.list", {"part": CHANNEL_PARTS, "forHandle": handle})
        items = body.get("items", [])
        return _to_channel(items[0]) if items else None

    def search_channels(self, query: str, max_results: int = 25) -> list[Channel]:
        """search.list finds channel IDs; channels.list fills in the metadata."""
        body = self._get(
            "search.list",
            {"part": "id", "type": "channel", "q": query,
             "maxResults": min(max(max_results, 1), 50)},
        )
        ids = [i["id"]["channelId"] for i in body.get("items", []) if i.get("id", {}).get("channelId")]
        return self.get_channels(ids)[:max_results]

    def get_recent_uploads(self, channel_id: str, max_results: int = 10) -> list[str]:
        """Read the channel's uploads playlist (UC... -> UU...): 1 unit, not search's 100."""
        if not channel_id.startswith("UC"):
            return []
        try:
            body = self._get(
                "playlistItems.list",
                {"part": "snippet", "playlistId": "UU" + channel_id[2:],
                 "maxResults": min(max(max_results, 1), 50)},
            )
        except YouTubeApiError as exc:
            if exc.reason == "playlistNotFound":  # channel with no uploads
                return []
            raise
        titles = [i.get("snippet", {}).get("title", "") for i in body.get("items", [])]
        return [t for t in titles if t and t not in HIDDEN_UPLOAD_TITLES]


# --- writes: playlists, with the user's login (FR-5) ---------------------------------------------

# Takes (url, headers, JSON body), returns (HTTP status, parsed JSON). Tests pass a fake.
PostJson = Callable[[str, dict[str, str], dict[str, Any]], tuple[int, dict[str, Any]]]


def urllib_post_json(
    url: str, headers: dict[str, str], body: dict[str, Any]
) -> tuple[int, dict[str, Any]]:
    request = Request(
        url,
        data=json.dumps(body).encode(),
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=WRITE_TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read() or b"{}")
    except HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read())
        except ValueError:
            return exc.code, {}


class YouTubeAccount(AccountProvider):
    def __init__(
        self,
        get_token: Callable[[str], str],
        quota: QuotaTracker,
        post: PostJson = urllib_post_json,
        fetch: FetchWithHeaders = urllib_fetch,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._get_token = get_token  # (scope) -> access token; renews it when needed
        self._quota = quota
        self._post = post
        self._fetch = fetch
        self._sleep = sleep

    # --- reads: the user's own data, read-only scope (FR-3, FR-4) ---

    def _read(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Call one read method as the user, with the same retries as the other reads. An
        AuthRequiredError from the login (not signed in) passes through and becomes AUTH_REQUIRED."""
        token = self._get_token(SCOPE_READONLY)
        resource = method.split(".")[0]
        url = f"{API_URL}/{resource}?{urlencode(params)}"

        def fetch(request_url: str) -> tuple[int, dict[str, Any]]:
            status, body = self._fetch(request_url, {"Authorization": f"Bearer {token}"})
            if status == 401:
                raise AuthRequiredError("Google rejected the saved login.")
            return status, body

        return _get_with_retries(fetch, url, method, self._quota, self._sleep)

    def _collect(
        self,
        method: str,
        params: dict[str, Any],
        limit: int,
        convert: Callable[[dict[str, Any]], Any],
    ) -> list[Any]:
        """Read pages (1 unit each) until `limit` converted items are found or the pages end.
        Items that `convert` turns into None (private or deleted videos) do not count."""
        results: list[Any] = []
        page_token = None
        while len(results) < limit:
            page = {**params, "maxResults": min(READ_PAGE_SIZE, limit - len(results))}
            if page_token:
                page["pageToken"] = page_token
            body = self._read(method, page)
            for item in body.get("items", []):
                converted = convert(item)
                if converted is not None:
                    results.append(converted)
                    if len(results) == limit:
                        break
            page_token = body.get("nextPageToken")
            if not page_token:
                break
        return results

    def liked_videos(self, limit: int) -> list[LikedVideo]:
        """The likes playlist, newest first, with the date each video was liked (ADR-010)."""
        if limit <= 0:
            return []
        channel = self._read("channels.list", {"part": "contentDetails", "mine": "true"})
        items = channel.get("items", [])
        playlists = items[0].get("contentDetails", {}).get("relatedPlaylists", {}) if items else {}
        likes_playlist = playlists.get("likes")
        if not likes_playlist:
            return []
        params = {"part": "snippet,contentDetails", "playlistId": likes_playlist}
        return self._collect("playlistItems.list", params, limit, _to_liked)

    def subscriptions(self, limit: int) -> list[Subscription]:
        if limit <= 0:
            return []
        params = {"part": "snippet", "mine": "true"}
        return self._collect("subscriptions.list", params, limit, _to_subscription)

    def playlist_video_ids(self, max_playlists: int) -> set[str]:
        """The user's own playlists (1 unit), then the first page of each (1 unit per playlist)."""
        if max_playlists <= 0:
            return set()
        body = self._read(
            "playlists.list",
            {"part": "id", "mine": "true", "maxResults": min(max_playlists, READ_PAGE_SIZE)},
        )
        ids: set[str] = set()
        for playlist in body.get("items", [])[:max_playlists]:
            page = self._read(
                "playlistItems.list",
                {"part": "contentDetails", "playlistId": playlist["id"], "maxResults": READ_PAGE_SIZE},
            )
            for item in page.get("items", []):
                video_id = item.get("contentDetails", {}).get("videoId")
                if video_id:
                    ids.add(video_id)
        return ids

    # --- writes: create playlists, write scope (FR-5) ---

    def _token(self) -> str:
        try:
            return self._get_token(SCOPE_WRITE)
        except AuthRequiredError as exc:  # not signed in, or signed in without write permission
            raise WriteAccessRequiredError(str(exc)) from None

    def ensure_write_access(self) -> None:
        self._token()

    def ensure_budget(self, units: int) -> None:
        self._quota.ensure_budget(units)

    def _send(self, method: str, parts: str, body: dict[str, Any]) -> dict[str, Any]:
        token = self._token()
        self._quota.record(method)  # counted even if it fails: we cannot know what Google charged
        resource = method.split(".")[0]
        url = f"{API_URL}/{resource}?{urlencode({'part': parts})}"
        try:
            status, response = self._post(url, {"Authorization": f"Bearer {token}"}, body)
        except OSError:
            raise YouTubeApiError(
                f"YouTube API call {method} failed (network error).", reason="network"
            ) from None
        if status == 200:
            return response

        reason = _error_reason(response)
        if reason in QUOTA_REASONS:
            raise QuotaExceededError("YouTube says the daily quota is used up.")
        if reason == "youtubeSignupRequired":
            raise YouTubeChannelRequiredError("This Google account has no YouTube channel.")
        if status == 401:
            raise AuthRequiredError("Google rejected the saved login.")
        if reason == "insufficientPermissions":
            raise WriteAccessRequiredError("The saved login does not allow creating playlists.")
        raise YouTubeApiError(
            f"YouTube API call {method} failed (status {status}, reason {reason}).", reason=reason
        )

    def create_playlist(self, title: str, description: str) -> str:
        response = self._send(
            "playlists.insert",
            "snippet,status",
            {
                "snippet": {"title": title, "description": description},
                "status": {"privacyStatus": "private"},  # always private (SRS 5.2)
            },
        )
        playlist_id = response.get("id")
        if not isinstance(playlist_id, str) or not playlist_id:
            raise YouTubeApiError("YouTube did not return a playlist ID.", reason="no_id")
        return playlist_id

    def add_video(self, playlist_id: str, video_id: str) -> None:
        self._send(
            "playlistItems.insert",
            "snippet",
            {
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                }
            },
        )
