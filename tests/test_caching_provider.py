from fake_youtube import FakeYouTube

from ytmcp.cache import Cache
from ytmcp.providers.caching import CachingProvider
from ytmcp.providers.youtube import YouTubeProvider
from ytmcp.quota import QuotaTracker
from ytmcp.services import find_similar_videos

DAY = 24 * 3600


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


def make(cache=None, clock=None, fake=None):
    clock = clock or Clock()
    cache = cache or Cache(now=clock)
    fake = fake or FakeYouTube()
    quota = QuotaTracker(reserve=0, cache=cache)
    inner = YouTubeProvider("k", quota=quota, fetch=fake, sleep=lambda s: None)
    return CachingProvider(inner, cache), fake, quota, clock


def test_second_get_videos_makes_no_api_call():
    provider, fake, quota, _ = make()
    first = provider.get_videos(["aaaaaaaaaaa"])
    second = provider.get_videos(["aaaaaaaaaaa"])
    assert first == second
    assert fake.resources() == ["videos"]
    assert quota.spent == 1


def test_only_missing_ids_are_fetched():
    provider, fake, _, _ = make()
    provider.get_videos(["aaaaaaaaaaa"])
    videos = provider.get_videos(["aaaaaaaaaaa", "bbbbbbbbbbb"])
    assert [v.id for v in videos] == ["aaaaaaaaaaa", "bbbbbbbbbbb"]
    assert fake.calls[1][1]["id"] == "bbbbbbbbbbb"


def test_unknown_ids_stay_omitted_and_are_requested_again():
    provider, fake, _, _ = make()
    assert provider.get_videos(["zzzzzzzzzzz"]) == []
    provider.get_videos(["zzzzzzzzzzz"])
    assert fake.resources() == ["videos", "videos"]  # missing is not cached


def test_repeat_search_costs_nothing():
    provider, fake, quota, _ = make()
    first = provider.search_videos("rust lifetimes", 25)
    spent = quota.spent
    second = provider.search_videos("Rust  Lifetimes", 25)
    assert [v.id for v in first] == [v.id for v in second]
    assert quota.spent == spent == 101
    assert fake.resources() == ["search", "videos"]


def test_search_primes_video_cache():
    provider, fake, _, _ = make()
    provider.search_videos("rust", 25)
    provider.get_videos(["aaaaaaaaaaa"])
    assert fake.resources() == ["search", "videos"]


def test_stale_search_is_refetched():
    provider, fake, _, clock = make()
    provider.search_videos("rust", 25)
    clock.t += 3601
    provider.search_videos("rust", 25)
    assert fake.resources().count("search") == 2


def test_stale_metadata_is_refetched():
    provider, fake, _, clock = make()
    provider.get_videos(["aaaaaaaaaaa"])
    clock.t += DAY + 1
    provider.get_videos(["aaaaaaaaaaa"])
    assert fake.resources() == ["videos", "videos"]


def test_channels_are_cached():
    provider, fake, _, _ = make()
    first = provider.get_channels(["UC1", "UC2"])
    assert provider.get_channels(["UC1", "UC2"]) == first
    assert fake.resources() == ["channels"]


def test_budget_check_goes_to_inner_provider():
    import pytest

    from ytmcp.errors import QuotaExceededError

    clock = Clock()
    cache = Cache(now=clock)
    inner = YouTubeProvider("k", quota=QuotaTracker(daily_limit=50, reserve=0, cache=cache), fetch=FakeYouTube())
    with pytest.raises(QuotaExceededError):
        CachingProvider(inner, cache).ensure_budget(51)


def test_cache_survives_restart(tmp_path):
    path = tmp_path / "c.db"
    first, _, _, _ = make(cache=Cache(path))
    first.search_videos("rust", 25)
    second, fake2, quota2, _ = make(cache=Cache(path))
    second.search_videos("rust", 25)
    assert fake2.calls == []  # served from disk
    assert quota2.spent == 101  # ledger remembered across restart


def test_end_to_end_second_request_is_free():
    provider, _, quota, _ = make()
    first = find_similar_videos(provider, "aaaaaaaaaaa")
    assert quota.spent == 102
    second = find_similar_videos(provider, "aaaaaaaaaaa")
    assert [r.video.id for r in first] == [r.video.id for r in second]
    assert quota.spent == 102
