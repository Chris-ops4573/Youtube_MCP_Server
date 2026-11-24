"""Create playlists with the user's Google login (FR-5, SE-6).

The only two calls are playlists.insert and playlistItems.insert: this can
create, never edit or delete (SRS 5.2). Writes are NOT retried. After an
unclear failure (a timeout, say) the playlist may already exist, and a retry
would make a duplicate. The login token is only ever sent to Google in the
Authorization header and never appears in errors or logs.
"""

import json
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ytmcp.auth.oauth import SCOPE_WRITE
from ytmcp.errors import (
    AuthRequiredError,
    QuotaExceededError,
    WriteAccessRequiredError,
    YouTubeApiError,
    YouTubeChannelRequiredError,
)
from ytmcp.providers.base import PlaylistWriter
from ytmcp.quota import QuotaTracker

API_URL = "https://www.googleapis.com/youtube/v3"
TIMEOUT_SECONDS = 15
QUOTA_REASONS = {"quotaExceeded", "dailyLimitExceeded"}

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
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read() or b"{}")
    except HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read())
        except ValueError:
            return exc.code, {}


def _reason(body: dict[str, Any]) -> str | None:
    errors = body.get("error", {}).get("errors") or [{}]
    return errors[0].get("reason")


class YouTubePlaylistWriter(PlaylistWriter):
    def __init__(
        self,
        get_token: Callable[[str], str],
        quota: QuotaTracker,
        post: PostJson = urllib_post_json,
    ):
        self._get_token = get_token  # (scope) -> access token; renews it when needed
        self._quota = quota
        self._post = post

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

        reason = _reason(response)
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
