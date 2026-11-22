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
