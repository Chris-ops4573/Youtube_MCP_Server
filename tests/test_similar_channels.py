import pytest
from fake_youtube import FakeYouTube

from ytmcp.errors import ChannelNotFoundError, QuotaExceededError
from ytmcp.models import Channel
from ytmcp.providers.youtube import YouTubeProvider
from ytmcp.quota import QuotaTracker
from ytmcp.services.similar_channels import (
    build_channel_query,
    estimate_cost,
    find_similar_channels,
)

RUST_LAB = "UC1111111111111111111111"
RUST_WEEKLY = "UC3333333333333333333333"
BAKE_CLUB = "UC2222222222222222222222"
SOURDOUGH = "UC4444444444444444444444"
UNKNOWN = "UC5555555555555555555555"


def ids(results):
    return [r.profile.channel.id for r in results]


# --- with the fixture provider --------------------------------------------


def test_finds_similar_channel_by_id(provider):
    assert ids(find_similar_channels(provider, RUST_LAB)) == [RUST_WEEKLY]


def test_accepts_handle_and_url(provider):
    assert ids(find_similar_channels(provider, "@rustlab")) == [RUST_WEEKLY]
    assert ids(find_similar_channels(provider, "https://www.youtube.com/@rustlab")) == [RUST_WEEKLY]
    assert ids(find_similar_channels(provider, f"https://www.youtube.com/channel/{RUST_LAB}")) == [RUST_WEEKLY]


def test_seed_is_not_in_results(provider):
    assert RUST_LAB not in ids(find_similar_channels(provider, RUST_LAB))
    assert ids(find_similar_channels(provider, BAKE_CLUB)) == [SOURDOUGH]


def test_missing_channel_by_id_raises_not_found(provider):
    with pytest.raises(ChannelNotFoundError) as exc:
        find_similar_channels(provider, UNKNOWN)
    assert exc.value.code == "CHANNEL_NOT_FOUND"


def test_missing_handle_raises_not_found(provider):
    with pytest.raises(ChannelNotFoundError):
        find_similar_channels(provider, "@nobodyhere")


def test_invalid_reference_raises_value_error(provider):
    with pytest.raises(ValueError):
        find_similar_channels(provider, "not a channel")


def test_hidden_subscriber_channel_works(provider):
    (result,) = find_similar_channels(provider, BAKE_CLUB)
    assert result.profile.channel.subscriber_count == 200
    seed_hidden = provider.get_channels([BAKE_CLUB])[0]
    assert seed_hidden.subscriber_count is None  # seed with hidden count still scores fine


# --- query and cost ---------------------------------------------------------


def test_build_channel_query_uses_only_top_keywords():
    seed = Channel(id="x", title="Rust Lab", description="", keywords=["Rust", "rust", "systems", "web"],
                   topics=["Technology"])
    assert build_channel_query(seed) == "rust"  # title, topics and later keywords are left out


def test_build_channel_query_keeps_two_keywords():
    seed = Channel(id="x", title="Rust Lab", description="", keywords=["angular", "firebase", "web"])
    assert build_channel_query(seed) == "angular firebase"


def test_build_channel_query_falls_back_to_title():
    seed = Channel(id="x", title="Quiet Channel", description="", keywords=[])
    assert build_channel_query(seed) == "quiet channel"


def test_query_is_stable_when_topic_order_changes():
    a = Channel(id="x", title="T", description="", keywords=["k"], topics=["B", "A"])
    b = Channel(id="x", title="T", description="", keywords=["k"], topics=["A", "B"])
    assert build_channel_query(a) == build_channel_query(b)


def test_estimate_cost():
    assert estimate_cost(15) == 118  # 1 + 1 + 100 + 1 + 15
    assert estimate_cost(60) == 1 + 1 + 100 + 2 + 60


# --- with the live provider (fake API) -------------------------------------


def live(quota=None):
    quota = quota or QuotaTracker(reserve=0)
    fake = FakeYouTube()
    return YouTubeProvider("k", quota=quota, fetch=fake, sleep=lambda s: None), fake, quota


def test_live_provider_end_to_end():
    provider, fake, quota = live()
    results = find_similar_channels(provider, "@rustlab")
    assert ids(results) == [RUST_WEEKLY, SOURDOUGH]  # seed (in the search results) is excluded
    assert results[0].score > results[1].score
    assert results[0].profile.recent_titles == ["Rust 2026 edition news", "Rust async tutorial"]
    assert results[1].profile.recent_titles == []  # channel with no uploads playlist -> empty
    # seed by handle, seed uploads, search, candidate details, then uploads per candidate
    assert fake.resources() == ["channels", "playlistItems", "search", "channels",
                                "playlistItems", "playlistItems"]
    assert quota.spent == 1 + 1 + 100 + 1 + 2


def test_quota_checked_before_any_api_call():
    provider, fake, _ = live(QuotaTracker(daily_limit=estimate_cost(15) - 1, reserve=0))
    with pytest.raises(QuotaExceededError):
        find_similar_channels(provider, RUST_LAB)
    assert fake.calls == []
