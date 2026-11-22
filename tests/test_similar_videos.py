import pytest
from fake_youtube import FakeYouTube

from ytmcp.errors import QuotaExceededError, VideoNotFoundError
from ytmcp.models import Video
from ytmcp.providers.youtube import YouTubeProvider
from ytmcp.quota import QuotaTracker
from ytmcp.services import build_query, find_similar_videos
from ytmcp.services.similar_videos import estimate_cost


def test_build_query_uses_title_and_top_tags():
    seed = Video(
        id="x" * 11,
        title="Rust Ownership",
        description="",
        channel_id="c",
        channel_title="c",
        tags=["rust", "borrowing", "memory", "ignored"],
    )
    assert build_query(seed) == "rust ownership borrowing memory"


def test_finds_similar_video_from_fixtures(provider):
    results = find_similar_videos(provider, "aaaaaaaaaaa")
    assert [r.video.id for r in results] == ["bbbbbbbbbbb"]


def test_accepts_a_url(provider):
    results = find_similar_videos(provider, "https://youtu.be/aaaaaaaaaaa")
    assert [r.video.id for r in results] == ["bbbbbbbbbbb"]


def test_seed_is_not_in_results(provider):
    results = find_similar_videos(provider, "aaaaaaaaaaa")
    assert "aaaaaaaaaaa" not in {r.video.id for r in results}


def test_missing_seed_raises_not_found(provider):
    with pytest.raises(VideoNotFoundError) as exc:
        find_similar_videos(provider, "zzzzzzzzzzz")
    assert exc.value.code == "VIDEO_NOT_FOUND"


def test_invalid_reference_raises_value_error(provider):
    with pytest.raises(ValueError):
        find_similar_videos(provider, "not a video")


def test_top_n_is_respected(provider):
    assert find_similar_videos(provider, "aaaaaaaaaaa", top_n=0) == []

# --- with the live provider (fake API) -------------------------------------

def test_estimate_cost_for_default_search():
    assert estimate_cost(25) == 102  # videos.list + search.list + videos.list
    assert estimate_cost(60) == 103


def test_live_provider_end_to_end():
    quota = QuotaTracker(reserve=0)
    fake = FakeYouTube()
    provider = YouTubeProvider("k", quota=quota, fetch=fake, sleep=lambda s: None)
    results = find_similar_videos(provider, "https://youtu.be/aaaaaaaaaaa")
    assert results[0].video.id == "bbbbbbbbbbb"
    assert "aaaaaaaaaaa" not in [r.video.id for r in results]
    assert fake.resources() == ["videos", "search", "videos"]
    assert quota.spent == 102  # SRS 5.1: FR-1 must cost <= 210 units


def test_quota_checked_before_any_api_call():
    fake = FakeYouTube()
    provider = YouTubeProvider("k", quota=QuotaTracker(daily_limit=101, reserve=0), fetch=fake)
    with pytest.raises(QuotaExceededError):
        find_similar_videos(provider, "aaaaaaaaaaa")
    assert fake.calls == []
