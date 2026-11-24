import pytest

from ytmcp.auth.oauth import SCOPE_WRITE
from ytmcp.errors import (
    AuthRequiredError,
    OAuthConfigError,
    QuotaExceededError,
    WriteAccessRequiredError,
    YouTubeApiError,
    YouTubeChannelRequiredError,
)
from ytmcp.providers.youtube import YouTubePlaylistWriter
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
    writer = YouTubePlaylistWriter(token_source or get_token, quota, post=post)
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


def test_the_writer_can_only_create_it_has_no_way_to_edit_or_delete():
    public = {n for n in dir(YouTubePlaylistWriter) if not n.startswith("_")}
    assert public == {"add_video", "create_playlist", "ensure_budget", "ensure_write_access"}
