import pytest

from ytmcp.auth.oauth import SCOPE_READONLY, SCOPE_WRITE
from ytmcp.errors import (
    AuthRequiredError,
    OAuthConfigError,
    QuotaExceededError,
    WriteAccessRequiredError,
    YouTubeApiError,
    YouTubeChannelRequiredError,
)
from ytmcp.models import LikedVideo, Subscription
from ytmcp.providers.youtube import YouTubeAccount
from ytmcp.quota import QuotaTracker

TOKEN = "SECRET-ACCESS-TOKEN"


class FakePost:
    """Use as the writer's `post`. Records each call; answers from `queue`, else 200."""

    def __init__(self, queue=None):
        self.queue = list(queue or [])
        self.calls: list[tuple[str, dict, dict]] = []

    def __call__(self, url, headers, body):
        self.calls.append((url, headers, body))
        if self.queue:
            item = self.queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        return 200, {"id": "PLnew"}


def make(queue=None, token_source=None, quota=None):
    scopes_asked: list[str] = []

    def get_token(scope):
        scopes_asked.append(scope)
        return TOKEN

    post = FakePost(queue)
    quota = quota or QuotaTracker(reserve=0)
    writer = YouTubeAccount(token_source or get_token, quota, post=post)
    return writer, post, quota, scopes_asked


def error_body(reason):
    return {"error": {"errors": [{"reason": reason}]}}


# --- what is sent --------------------------------------------------------------------------


def test_create_playlist_request():
    writer, post, quota, scopes = make()
    assert writer.create_playlist("My list", "About it") == "PLnew"
    (url, headers, body), = post.calls
    assert url == "https://www.googleapis.com/youtube/v3/playlists?part=snippet%2Cstatus"
    assert headers == {"Authorization": f"Bearer {TOKEN}"}
    assert body == {
        "snippet": {"title": "My list", "description": "About it"},
        "status": {"privacyStatus": "private"},
    }
    assert scopes == [SCOPE_WRITE]
    assert quota.spent == 50


def test_playlists_are_always_created_private():
    writer, post, _, _ = make()
    writer.create_playlist("t", "d")
    assert post.calls[0][2]["status"]["privacyStatus"] == "private"


def test_add_video_request():
    writer, post, quota, _ = make()
    writer.add_video("PL1", "aaaaaaaaaaa")
    (url, _headers, body), = post.calls
    assert url == "https://www.googleapis.com/youtube/v3/playlistItems?part=snippet"
    assert body == {
        "snippet": {"playlistId": "PL1", "resourceId": {"kind": "youtube#video", "videoId": "aaaaaaaaaaa"}}
    }
    assert quota.spent == 50


def test_the_token_is_requested_fresh_for_every_call():
    writer, _, _, scopes = make()
    writer.create_playlist("t", "d")
    writer.add_video("PL1", "aaaaaaaaaaa")
    assert scopes == [SCOPE_WRITE, SCOPE_WRITE]


@pytest.mark.parametrize("response", [{}, {"id": ""}, {"id": 5}])
def test_a_response_without_an_id_is_an_error(response):
    writer, _, _, _ = make([(200, response)])
    with pytest.raises(YouTubeApiError) as exc:
        writer.create_playlist("t", "d")
    assert exc.value.reason == "no_id"


# --- errors ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("reason", ["quotaExceeded", "dailyLimitExceeded"])
def test_quota_errors(reason):
    writer, _, _, _ = make([(403, error_body(reason))])
    with pytest.raises(QuotaExceededError):
        writer.create_playlist("t", "d")


def test_account_without_a_youtube_channel():
    writer, _, _, _ = make([(401, error_body("youtubeSignupRequired"))])  # reason wins over status
    with pytest.raises(YouTubeChannelRequiredError) as exc:
        writer.create_playlist("t", "d")
    assert exc.value.code == "YOUTUBE_CHANNEL_REQUIRED"
    assert "youtube.com" in exc.value.remediation


def test_rejected_login():
    writer, _, _, _ = make([(401, {})])
    with pytest.raises(AuthRequiredError):
        writer.create_playlist("t", "d")


def test_login_without_write_permission():
    writer, _, _, _ = make([(403, error_body("insufficientPermissions"))])
    with pytest.raises(WriteAccessRequiredError) as exc:
        writer.create_playlist("t", "d")
    assert "auth login --write" in exc.value.remediation


@pytest.mark.parametrize("status", [400, 404, 409, 500, 503])
def test_other_errors_keep_the_reason_and_are_not_retried(status):
    writer, post, _, _ = make([(status, error_body("videoNotFound"))])
    with pytest.raises(YouTubeApiError) as exc:
        writer.add_video("PL1", "aaaaaaaaaaa")
    assert exc.value.reason == "videoNotFound"
    assert f"status {status}" in str(exc.value)
    assert len(post.calls) == 1  # never retried: a retry could duplicate


def test_a_network_failure_is_not_retried_either():
    writer, post, _, _ = make([OSError("connection reset")])
    with pytest.raises(YouTubeApiError) as exc:
        writer.create_playlist("t", "d")
    assert exc.value.reason == "network"
    assert len(post.calls) == 1


def test_a_body_that_is_not_an_error_object_still_gives_a_clean_error():
    writer, _, _, _ = make([(500, {})])
    with pytest.raises(YouTubeApiError) as exc:
        writer.create_playlist("t", "d")
    assert exc.value.reason is None


def test_the_token_never_appears_in_errors():
    for answer in [(400, error_body("x")), (500, {}), (401, {}), (403, error_body("insufficientPermissions"))]:
        writer, _, _, _ = make([answer])
        with pytest.raises(Exception) as exc:
            writer.create_playlist("t", "d")
        assert TOKEN not in str(exc.value)


def test_a_failed_call_still_counts_against_the_quota():
    writer, _, quota, _ = make([(500, {})])
    with pytest.raises(YouTubeApiError):
        writer.create_playlist("t", "d")
    assert quota.spent == 50


# --- access and budget -----------------------------------------------------------------------------------


def test_ensure_write_access_asks_for_the_write_scope():
    writer, post, _, scopes = make()
    writer.ensure_write_access()
    assert scopes == [SCOPE_WRITE] and post.calls == []


@pytest.mark.parametrize("message", ["You are not signed in.", "Your login does not include the permission this needs."])
def test_no_login_or_no_write_scope_both_mean_write_access_required(message):
    def source(scope):
        raise AuthRequiredError(message)

    writer, _, _, _ = make(token_source=source)
    with pytest.raises(WriteAccessRequiredError) as exc:
        writer.ensure_write_access()
    assert message in str(exc.value)
    assert "auth login --write" in exc.value.remediation


def test_a_missing_oauth_setup_is_reported_as_such():
    def source(scope):
        raise OAuthConfigError("No Google OAuth client ID is configured.")

    writer, _, _, _ = make(token_source=source)
    with pytest.raises(OAuthConfigError):
        writer.ensure_write_access()


def test_no_call_is_made_when_there_is_no_token():
    def source(scope):
        raise AuthRequiredError("You are not signed in.")

    writer, post, quota, _ = make(token_source=source)
    with pytest.raises(WriteAccessRequiredError):
        writer.create_playlist("t", "d")
    assert post.calls == [] and quota.spent == 0


def test_ensure_budget_uses_the_shared_quota():
    writer, _, _, _ = make(quota=QuotaTracker(daily_limit=200, reserve=0))
    writer.ensure_budget(200)
    with pytest.raises(QuotaExceededError):
        writer.ensure_budget(201)


def test_the_account_can_read_and_create_but_has_no_way_to_edit_or_delete():
    public = {n for n in dir(YouTubeAccount) if not n.startswith("_")}
    assert public == {
        "add_video", "create_playlist", "ensure_budget", "ensure_write_access",  # writing: create only
        "liked_videos", "subscriptions", "playlist_video_ids",  # reading the account
    }


# --- reading the user's account (FR-3, FR-4) ----------------------------------------------------------------


class FakeRead:
    """Use as the account's `fetch`. Answers from `queue` in order and records every call."""

    def __init__(self, queue):
        self.queue = list(queue)
        self.calls: list[dict] = []

    def __call__(self, url, headers):
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(url)
        self.calls.append({
            "resource": parsed.path.rsplit("/", 1)[-1],
            "params": {k: v[0] for k, v in parse_qs(parsed.query).items()},
            "headers": headers,
            "url": url,
        })
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def resources(self):
        return [call["resource"] for call in self.calls]


def make_reader(queue, token_source=None, quota=None):
    scopes: list[str] = []
    sleeps: list[float] = []

    def get_token(scope):
        scopes.append(scope)
        return TOKEN

    fetch = FakeRead(queue)
    quota = quota or QuotaTracker(reserve=0)
    account = YouTubeAccount(token_source or get_token, quota, fetch=fetch, sleep=sleeps.append)
    return account, fetch, quota, scopes, sleeps


def channel_with_likes(playlist="LLfake"):
    return (200, {"items": [{"contentDetails": {"relatedPlaylists": {"likes": playlist, "uploads": "UUx"}}}]})


def like(video_id, liked_at="2026-11-11T04:28:52Z", title="A video"):
    return {"snippet": {"title": title, "publishedAt": liked_at}, "contentDetails": {"videoId": video_id}}


def page(items, next_token=None):
    body = {"items": items}
    if next_token:
        body["nextPageToken"] = next_token
    return (200, body)


def many_likes(count, start=0):
    return [like(f"v{n:010d}") for n in range(start, start + count)]


# --- likes -----------------------------------------------------------------------------------------------------


def test_liked_videos_finds_the_likes_playlist_then_reads_it():
    account, fetch, quota, _, _ = make_reader([channel_with_likes("LLabc"), page([like("aaaaaaaaaaa"), like("bbbbbbbbbbb", "2026-11-10T19:40:04Z")])])
    liked = account.liked_videos(10)
    assert liked == [LikedVideo("aaaaaaaaaaa", "2026-11-11T04:28:52Z"), LikedVideo("bbbbbbbbbbb", "2026-11-10T19:40:04Z")]
    assert fetch.resources() == ["channels", "playlistItems"]
    assert fetch.calls[0]["params"] == {"part": "contentDetails", "mine": "true"}
    assert fetch.calls[1]["params"]["playlistId"] == "LLabc"
    assert fetch.calls[1]["params"]["part"] == "snippet,contentDetails"
    assert quota.spent == 2


def test_reads_use_the_login_not_the_api_key():
    account, fetch, _, scopes, _ = make_reader([channel_with_likes(), page([])])
    account.liked_videos(10)
    assert all(call["headers"] == {"Authorization": f"Bearer {TOKEN}"} for call in fetch.calls)
    assert all("key=" not in call["url"] for call in fetch.calls)
    assert scopes == [SCOPE_READONLY, SCOPE_READONLY]  # the read-only scope, never write
    assert SCOPE_WRITE not in scopes


def test_liked_videos_follows_pages_until_the_pages_end():
    account, fetch, quota, _, _ = make_reader([channel_with_likes(), page(many_likes(2), "T2"), page(many_likes(1, 2))])
    assert len(account.liked_videos(100)) == 3
    assert fetch.calls[1]["params"].get("pageToken") is None
    assert fetch.calls[2]["params"]["pageToken"] == "T2"
    assert quota.spent == 3  # one unit for the channel, one for each page


def test_the_limit_is_respected_and_stops_reading_early():
    account, fetch, _, _, _ = make_reader([channel_with_likes(), page(many_likes(5), "MORE")])
    assert len(account.liked_videos(2)) == 2
    assert fetch.resources() == ["channels", "playlistItems"]  # did not ask for the next page
    assert fetch.calls[1]["params"]["maxResults"] == "2"


def test_page_sizes_never_ask_for_more_than_is_needed():
    queue = [channel_with_likes(), page(many_likes(50), "T2"), page(many_likes(50, 50), "T3"), page(many_likes(20, 100))]
    account, fetch, _, _, _ = make_reader(queue)
    assert len(account.liked_videos(120)) == 120
    assert [c["params"]["maxResults"] for c in fetch.calls[1:]] == ["50", "50", "20"]


def test_private_and_deleted_videos_are_skipped_and_do_not_count_toward_the_limit():
    first = page([like("xxxxxxxxxxx", title="Private video"), like("aaaaaaaaaaa"), like("yyyyyyyyyyy", title="Deleted video")], "T2")
    second = page([like("bbbbbbbbbbb")])
    account, fetch, _, _, _ = make_reader([channel_with_likes(), first, second])
    assert [v.video_id for v in account.liked_videos(2)] == ["aaaaaaaaaaa", "bbbbbbbbbbb"]
    assert fetch.resources().count("playlistItems") == 2


def test_items_without_a_video_id_are_skipped():
    account, _, _, _, _ = make_reader([channel_with_likes(), page([{"snippet": {"title": "x"}}, like("aaaaaaaaaaa")])])
    assert [v.video_id for v in account.liked_videos(5)] == ["aaaaaaaaaaa"]


@pytest.mark.parametrize("channel", [(200, {"items": []}), (200, {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU"}}}]}), (200, {})])
def test_no_likes_playlist_gives_an_empty_list_without_reading_a_playlist(channel):
    account, fetch, _, _, _ = make_reader([channel])
    assert account.liked_videos(10) == []
    assert fetch.resources() == ["channels"]


@pytest.mark.parametrize("limit", [0, -3])
def test_a_limit_of_nothing_makes_no_call(limit):
    account, fetch, _, _, _ = make_reader([])
    assert account.liked_videos(limit) == []
    assert account.subscriptions(limit) == []
    assert account.playlist_video_ids(limit) == set()
    assert fetch.calls == []


# --- subscriptions ----------------------------------------------------------------------------------------------


def sub(channel_id, title="A channel", at="2025-01-02T03:04:05Z"):
    return {"snippet": {"title": title, "publishedAt": at, "resourceId": {"kind": "youtube#channel", "channelId": channel_id}}}


def test_subscriptions_are_mapped_and_paged():
    account, fetch, quota, _, _ = make_reader([page([sub("UC1"), sub("UC2", "Two")], "T2"), page([sub("UC3")])])
    found = account.subscriptions(10)
    assert found == [
        Subscription("UC1", "A channel", "2025-01-02T03:04:05Z"),
        Subscription("UC2", "Two", "2025-01-02T03:04:05Z"),
        Subscription("UC3", "A channel", "2025-01-02T03:04:05Z"),
    ]
    assert fetch.calls[0]["params"] == {"part": "snippet", "mine": "true", "maxResults": "10"}
    assert fetch.calls[1]["params"]["pageToken"] == "T2"
    assert quota.spent == 2


def test_subscriptions_respect_the_limit():
    account, fetch, _, _, _ = make_reader([page([sub("UC1"), sub("UC2"), sub("UC3")], "MORE")])
    assert [s.channel_id for s in account.subscriptions(2)] == ["UC1", "UC2"]
    assert fetch.resources() == ["subscriptions"]


def test_subscription_without_a_channel_id_is_skipped_and_a_missing_date_is_none():
    odd = {"snippet": {"title": "No id"}}
    no_date = {"snippet": {"title": "T", "resourceId": {"channelId": "UC9"}}}
    account, _, _, _, _ = make_reader([page([odd, no_date])])
    assert account.subscriptions(5) == [Subscription("UC9", "T", None)]


# --- the user's own playlists ------------------------------------------------------------------------------------


def playlists_page(*ids):
    return (200, {"items": [{"id": i} for i in ids]})


def video_ids_page(*ids):
    return (200, {"items": [{"contentDetails": {"videoId": i}} for i in ids]})


def test_playlist_video_ids_reads_each_playlist_once():
    queue = [playlists_page("PL1", "PL2"), video_ids_page("aaaaaaaaaaa", "bbbbbbbbbbb"), video_ids_page("bbbbbbbbbbb", "ccccccccccc")]
    account, fetch, quota, _, _ = make_reader(queue)
    assert account.playlist_video_ids(10) == {"aaaaaaaaaaa", "bbbbbbbbbbb", "ccccccccccc"}
    assert fetch.resources() == ["playlists", "playlistItems", "playlistItems"]
    assert fetch.calls[0]["params"] == {"part": "id", "mine": "true", "maxResults": "10"}
    assert [c["params"]["playlistId"] for c in fetch.calls[1:]] == ["PL1", "PL2"]
    assert quota.spent == 3  # 1 + one per playlist


def test_playlist_video_ids_never_reads_more_playlists_than_asked():
    queue = [playlists_page("PL1", "PL2", "PL3"), video_ids_page("aaaaaaaaaaa"), video_ids_page("bbbbbbbbbbb")]
    account, fetch, _, _, _ = make_reader(queue)
    assert account.playlist_video_ids(2) == {"aaaaaaaaaaa", "bbbbbbbbbbb"}
    assert fetch.resources().count("playlistItems") == 2


def test_no_playlists_and_items_without_ids():
    account, fetch, _, _, _ = make_reader([(200, {"items": []})])
    assert account.playlist_video_ids(5) == set()
    assert fetch.resources() == ["playlists"]
    account, _, _, _, _ = make_reader([playlists_page("PL1"), (200, {"items": [{"contentDetails": {}}, {}]})])
    assert account.playlist_video_ids(5) == set()


# --- login, retries and errors on reads --------------------------------------------------------------------------------


@pytest.mark.parametrize("read", ["liked_videos", "subscriptions", "playlist_video_ids"])
def test_not_signed_in_passes_through_as_auth_required_and_makes_no_call(read):
    def source(scope):
        raise AuthRequiredError("You are not signed in.")

    account, fetch, quota, _, _ = make_reader([], token_source=source)
    with pytest.raises(AuthRequiredError) as exc:  # not WriteAccessRequiredError: reading needs no write permission
        getattr(account, read)(5)
    assert exc.value.code == "AUTH_REQUIRED"
    assert fetch.calls == [] and quota.spent == 0


def test_google_rejecting_the_token_means_sign_in_again():
    account, fetch, _, _, _ = make_reader([(401, {})])
    with pytest.raises(AuthRequiredError):
        account.subscriptions(5)
    assert len(fetch.calls) == 1  # not retried


def test_a_503_read_is_retried_and_every_attempt_counts_against_the_quota():
    account, fetch, quota, _, sleeps = make_reader([(503, {}), channel_with_likes(), page([like("aaaaaaaaaaa")])])
    assert [v.video_id for v in account.liked_videos(5)] == ["aaaaaaaaaaa"]
    assert fetch.resources() == ["channels", "channels", "playlistItems"]
    assert sleeps == [1]
    assert quota.spent == 3


def test_a_network_error_on_a_read_is_retried():
    account, fetch, _, _, sleeps = make_reader([OSError("reset"), page([sub("UC1")])])
    assert len(account.subscriptions(5)) == 1
    assert sleeps == [1] and len(fetch.calls) == 2


def test_reads_give_up_after_three_retries():
    account, fetch, _, _, sleeps = make_reader([(500, {})] * 4)
    with pytest.raises(YouTubeApiError) as exc:
        account.subscriptions(5)
    assert len(fetch.calls) == 4 and sleeps == [1, 2, 4]
    assert exc.value.code == "YOUTUBE_API_ERROR"


def test_quota_exceeded_on_a_read_is_never_retried():
    account, fetch, _, _, sleeps = make_reader([(403, error_body("quotaExceeded"))])
    with pytest.raises(QuotaExceededError):
        account.subscriptions(5)
    assert len(fetch.calls) == 1 and sleeps == []


def test_other_read_errors_keep_the_reason_and_are_not_retried():
    account, fetch, _, _, _ = make_reader([(404, error_body("playlistNotFound"))])
    with pytest.raises(YouTubeApiError) as exc:
        account.subscriptions(5)
    assert exc.value.reason == "playlistNotFound" and len(fetch.calls) == 1


def test_the_token_never_appears_in_a_read_error():
    account, _, _, _, _ = make_reader([(400, error_body("invalidParameter"))])
    with pytest.raises(YouTubeApiError) as exc:
        account.subscriptions(5)
    assert TOKEN not in str(exc.value)


def test_reads_and_writes_share_one_quota_counter():
    quota = QuotaTracker(reserve=0)
    account, _, _, _, _ = make_reader([page([sub("UC1")])], quota=quota)
    account._post = FakePost()
    account.subscriptions(5)
    account.create_playlist("t", "d")
    assert quota.spent == 1 + 50
