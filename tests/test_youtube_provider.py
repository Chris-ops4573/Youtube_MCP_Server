import pytest
from fake_youtube import FakeYouTube, sample

from ytmcp.errors import ApiKeyMissingError, QuotaExceededError, YouTubeApiError
from ytmcp.providers.youtube import YouTubeProvider
from ytmcp.quota import QuotaTracker

KEY = "test-key-123"


def make(queue=None, key=KEY, quota=None):
    fake = FakeYouTube(queue)
    sleeps: list[float] = []
    provider = YouTubeProvider(
        key, quota=quota or QuotaTracker(reserve=0), fetch=fake, sleep=sleeps.append
    )
    return provider, fake, sleeps


# --- API key ---------------------------------------------------------------


@pytest.mark.parametrize("key", [None, ""])
def test_missing_key_raises_without_calling_api(key):
    provider, fake, _ = make(key=key)
    with pytest.raises(ApiKeyMissingError) as exc:
        provider.get_videos(["aaaaaaaaaaa"])
    assert exc.value.code == "API_KEY_MISSING"
    assert fake.calls == []


def test_key_is_sent_with_request():
    provider, fake, _ = make()
    provider.get_videos(["aaaaaaaaaaa"])
    assert fake.calls[0][1]["key"] == KEY


# --- videos ----------------------------------------------------------------


def test_get_videos_maps_fields():
    provider, _, _ = make()
    (video,) = provider.get_videos(["aaaaaaaaaaa"])
    assert video.title == "Rust ownership explained"
    assert video.channel_id == "UC1"
    assert video.channel_title == "Rust Lab"
    assert video.tags == ["rust", "ownership"]
    assert video.category_id == "27"
    assert video.language == "en"  # "en-US" shortened
    assert video.duration_seconds == 600
    assert video.is_live is False


def test_live_video_without_tags():
    provider, _, _ = make()
    (video,) = provider.get_videos(["ccccccccccc"])
    assert video.is_live is True
    assert video.tags == []
    assert video.language is None
    assert video.duration_seconds == 0


def test_get_videos_keeps_order_drops_missing_and_duplicates():
    provider, _, _ = make()
    videos = provider.get_videos(["bbbbbbbbbbb", "zzzzzzzzzzz", "aaaaaaaaaaa", "bbbbbbbbbbb"])
    assert [v.id for v in videos] == ["bbbbbbbbbbb", "aaaaaaaaaaa"]


def test_get_videos_batches_50_ids_per_call():
    provider, fake, _ = make()
    provider.get_videos([f"id{n:09d}" for n in range(120)])
    assert fake.resources() == ["videos", "videos", "videos"]
    assert [len(p["id"].split(",")) for _, p in fake.calls] == [50, 50, 20]


def test_search_enriches_with_videos_list():
    quota = QuotaTracker(reserve=0)
    provider, fake, _ = make(quota=quota)
    videos = provider.search_videos("rust", max_results=10)
    assert fake.resources() == ["search", "videos"]
    assert [v.id for v in videos] == ["bbbbbbbbbbb", "aaaaaaaaaaa", "ccccccccccc"]
    assert videos[0].duration_seconds == 900  # full metadata, not just the ID
    assert quota.spent == 101


def test_search_respects_max_results():
    provider, fake, _ = make()
    assert len(provider.search_videos("rust", max_results=1)) == 1
    assert fake.calls[0][1]["maxResults"] == "1"


# --- channels --------------------------------------------------------------


def test_get_channels():
    provider, _, _ = make()
    rust, bake = provider.get_channels(["UC1", "UC2"])
    assert rust.subscriber_count == 12000
    assert rust.keywords == ["rust", "systems programming"]
    assert bake.subscriber_count is None  # hidden
    assert bake.keywords == []


# --- errors and retries ----------------------------------------------------


def test_quota_exceeded_is_not_retried():
    provider, fake, sleeps = make(queue=[(403, sample("error_quota"))])
    with pytest.raises(QuotaExceededError):
        provider.get_videos(["aaaaaaaaaaa"])
    assert len(fake.calls) == 1
    assert sleeps == []


def test_server_error_is_retried_then_succeeds():
    provider, fake, sleeps = make(queue=[(500, {}), (503, {})])
    assert len(provider.get_videos(["aaaaaaaaaaa"])) == 1
    assert len(fake.calls) == 3
    assert sleeps == [1, 2]


def test_network_error_is_retried():
    provider, fake, _ = make(queue=[OSError("connection reset")])
    assert len(provider.get_videos(["aaaaaaaaaaa"])) == 1
    assert len(fake.calls) == 2


def test_gives_up_after_three_retries():
    provider, fake, sleeps = make(queue=[(500, {})] * 4)
    with pytest.raises(YouTubeApiError) as exc:
        provider.get_videos(["aaaaaaaaaaa"])
    assert len(fake.calls) == 4  # 1 try + 3 retries
    assert sleeps == [1, 2, 4]
    assert exc.value.code == "YOUTUBE_API_ERROR"


def test_bad_request_is_not_retried():
    provider, fake, _ = make(queue=[(400, sample("error_bad_request"))])
    with pytest.raises(YouTubeApiError) as exc:
        provider.get_videos(["aaaaaaaaaaa"])
    assert len(fake.calls) == 1
    assert "invalidParameter" in str(exc.value)


def test_api_key_never_appears_in_errors():
    provider, _, _ = make(queue=[(400, sample("error_bad_request"))])
    with pytest.raises(YouTubeApiError) as exc:
        provider.get_videos(["aaaaaaaaaaa"])
    assert KEY not in str(exc.value)


def test_every_attempt_counts_against_quota():
    quota = QuotaTracker(reserve=0)
    provider, _, _ = make(queue=[(500, {})], quota=quota)
    provider.get_videos(["aaaaaaaaaaa"])
    assert quota.spent == 2


def test_ensure_budget_uses_quota():
    provider, _, _ = make(quota=QuotaTracker(daily_limit=100, reserve=0))
    provider.ensure_budget(100)
    with pytest.raises(QuotaExceededError):
        provider.ensure_budget(101)


# --- channels: topics, handle, search, uploads (FR-2) ----------------------

RUST_LAB = "UC1111111111111111111111"


def test_channel_topics_and_handle_mapped():
    provider, _, _ = make()
    (channel,) = provider.get_channels([RUST_LAB])
    assert channel.handle == "@rustlab"  # lower-cased
    assert channel.topics == ["Computer programming", "Technology"]  # sorted
    assert channel.keywords == ["rust", "systems programming"]


def test_channel_without_optional_parts():
    provider, _, _ = make()
    (channel,) = provider.get_channels(["UC4444444444444444444444"])
    assert channel.handle is None
    assert channel.topics == []
    assert channel.subscriber_count is None


def test_get_channels_asks_for_topic_details():
    provider, fake, _ = make()
    provider.get_channels([RUST_LAB])
    assert "topicDetails" in fake.calls[0][1]["part"]


def test_get_channel_by_handle():
    provider, fake, _ = make()
    channel = provider.get_channel_by_handle("@RustLab")
    assert channel.id == RUST_LAB
    assert fake.calls[0][1]["forHandle"] == "@RustLab"


def test_get_channel_by_handle_not_found():
    provider, _, _ = make()
    assert provider.get_channel_by_handle("@nobodyhere") is None


def test_search_channels_enriches_and_skips_unknown_ids():
    quota = QuotaTracker(reserve=0)
    provider, fake, _ = make(quota=quota)
    channels = provider.search_channels("rust", max_results=10)
    assert fake.resources() == ["search", "channels"]
    assert fake.calls[0][1]["type"] == "channel"
    assert [c.id for c in channels] == [
        "UC3333333333333333333333", RUST_LAB, "UC4444444444444444444444"
    ]
    assert quota.spent == 101


def test_get_recent_uploads_hides_private_and_deleted():
    provider, fake, _ = make()
    titles = provider.get_recent_uploads(RUST_LAB)
    assert titles == ["Rust ownership explained", "Rust lifetimes tutorial"]
    assert fake.calls[0][1]["playlistId"] == "UU1111111111111111111111"  # UC... -> UU...


def test_get_recent_uploads_playlist_not_found_is_empty():
    provider, _, _ = make()
    assert provider.get_recent_uploads("UC4444444444444444444444") == []


def test_get_recent_uploads_other_errors_still_raise():
    provider, _, _ = make(queue=[(400, sample("error_bad_request"))])
    with pytest.raises(YouTubeApiError) as exc:
        provider.get_recent_uploads(RUST_LAB)
    assert exc.value.reason == "invalidParameter"


def test_get_recent_uploads_ignores_non_channel_ids():
    provider, fake, _ = make()
    assert provider.get_recent_uploads("not-a-channel") == []
    assert fake.calls == []


def test_playlist_items_cost_one_unit():
    quota = QuotaTracker(reserve=0)
    provider, _, _ = make(quota=quota)
    provider.get_recent_uploads(RUST_LAB)
    assert quota.spent == 1


# --- the real HTTP function, against a tiny local server (no internet) --------------------------------------------


@pytest.fixture
def local_api():
    """A throwaway HTTP server on 127.0.0.1 that answers /ok, /bad and /boom like YouTube would."""
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/ok":
                status, body = 200, {"auth": self.headers.get("Authorization")}
            elif self.path == "/bad":
                status, body = 403, {"error": {"errors": [{"reason": "quotaExceeded"}]}}
            else:
                status, body = 500, None
            payload = json.dumps(body).encode() if body is not None else b"<html>not json</html>"
            self.send_response(status)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_urllib_fetch_without_headers_still_works_as_before(local_api):
    from ytmcp.providers.youtube import urllib_fetch

    assert urllib_fetch(f"{local_api}/ok") == (200, {"auth": None})


def test_urllib_fetch_can_send_headers(local_api):
    from ytmcp.providers.youtube import urllib_fetch

    status, body = urllib_fetch(f"{local_api}/ok", {"Authorization": "Bearer abc"})
    assert (status, body) == (200, {"auth": "Bearer abc"})


def test_urllib_fetch_returns_the_error_body_and_status(local_api):
    from ytmcp.providers.youtube import urllib_fetch

    assert urllib_fetch(f"{local_api}/bad") == (403, {"error": {"errors": [{"reason": "quotaExceeded"}]}})


def test_urllib_fetch_survives_an_error_page_that_is_not_json(local_api):
    from ytmcp.providers.youtube import urllib_fetch

    assert urllib_fetch(f"{local_api}/boom") == (500, {})


# --- category names (FR-4) ----------------------------------------------------------------------------------------------


def test_category_names_maps_ids_to_names_and_costs_one_unit():
    quota = QuotaTracker(reserve=0)
    provider, fake, _ = make(quota=quota)
    assert provider.category_names() == {"1": "Film & Animation", "27": "Education", "28": "Science & Technology"}
    assert fake.resources() == ["videoCategories"]
    assert fake.calls[0][1]["part"] == "snippet" and fake.calls[0][1]["regionCode"] == "US"
    assert quota.spent == 1


def test_category_names_can_use_another_region():
    provider, fake, _ = make()
    provider.category_names("IN")
    assert fake.calls[0][1]["regionCode"] == "IN"


def test_category_names_with_odd_items():
    body = {"items": [{"id": "5"}, {"snippet": {"title": "No id"}}, {"id": "6", "snippet": {"title": "Six"}}]}
    provider, _, _ = make(queue=[(200, body)])
    assert provider.category_names() == {"5": "", "6": "Six"}


def test_category_names_needs_the_api_key():
    provider, fake, _ = make(key=None)
    with pytest.raises(ApiKeyMissingError):
        provider.category_names()
    assert fake.calls == []
