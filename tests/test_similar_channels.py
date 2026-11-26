import pytest
from fake_youtube import FakeYouTube

from ytmcp.errors import ChannelNotFoundError, QuotaExceededError
from ytmcp.models import Channel, Video
from ytmcp.providers.youtube import YouTubeProvider
from ytmcp.quota import QuotaTracker
from ytmcp.services.similar_channels import (
    build_channel_query,
    candidate_channel_ids,
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


def test_query_comes_from_upload_titles_not_the_name():
    seed = Channel(id="x", title="Byte Garden", description="", keywords=[])
    titles = ["Async Rust explained", "Rust lifetimes deep dive", "Garden of bytes: async tips"]
    query = build_channel_query(seed, titles)
    assert query == "async rust bytes"  # most common words first, then alphabetical
    assert "garden" not in query  # a word from the channel's name is left out


def test_a_name_word_that_is_also_a_keyword_is_kept():
    seed = Channel(id="x", title="Rust Lab", description="", keywords=["rust", "systems programming"])
    titles = ["Rust ownership explained", "Rust lifetimes tutorial"]
    assert build_channel_query(seed, titles) == "rust explained lifetimes"  # "lab" is left out


def test_query_falls_back_to_keywords_then_title():
    no_words = Channel(id="x", title="Quiet Channel", description="", keywords=["angular", "firebase", "web"])
    assert build_channel_query(no_words, ["Quiet channel"]) == "angular firebase web"
    keywords_only_short = Channel(id="x", title="Ok", description="", keywords=["go", "ui"])
    assert build_channel_query(keywords_only_short, []) == "go ui"  # too short to be topic words
    nothing = Channel(id="x", title="Quiet Channel", description="", keywords=[])
    assert build_channel_query(nothing, []) == "quiet channel"


def test_query_is_stable_when_topic_order_changes():
    a = Channel(id="x", title="T", description="", keywords=["k"], topics=["B", "A"])
    b = Channel(id="x", title="T", description="", keywords=["k"], topics=["A", "B"])
    titles = ["rust async", "python async"]
    assert build_channel_query(a, titles) == build_channel_query(b, titles)  # topics are not used
    assert build_channel_query(a, titles) == build_channel_query(a, list(reversed(titles))) == "async python rust"


def test_candidates_are_the_channels_behind_the_videos():
    def video(vid, channel):
        return Video(id=vid, title="t", description="", channel_id=channel, channel_title="c")

    videos = [video("a", "SEED"), video("b", "UC_B"), video("c", "UC_A"), video("d", "UC_B"), video("e", "")]
    assert candidate_channel_ids(videos, "SEED", 10) == ["UC_B", "UC_A"]  # no seed, no repeats
    assert candidate_channel_ids(videos, "SEED", 1) == ["UC_B"]


def test_estimate_cost():
    # seed, seed uploads, video search, video details, candidate details, candidate uploads
    assert estimate_cost(15) == 1 + 1 + 100 + 1 + 1 + 15
    assert estimate_cost(60) == 1 + 1 + 100 + 1 + 2 + 60


# --- with the live provider (fake API) -------------------------------------


def live(quota=None):
    quota = quota or QuotaTracker(reserve=0)
    fake = FakeYouTube()
    return YouTubeProvider("k", quota=quota, fetch=fake, sleep=lambda s: None), fake, quota


def test_live_provider_end_to_end():
    provider, fake, quota = live()
    results = find_similar_channels(provider, "@rustlab")
    found = ids(results)
    assert RUST_LAB not in found  # the seed's own videos are in the search results, but it is excluded
    assert found.index(RUST_WEEKLY) < found.index(SOURDOUGH)  # Rust content above unrelated content
    weekly = results[found.index(RUST_WEEKLY)]
    assert weekly.profile.recent_titles == ["Rust 2026 edition news", "Rust async tutorial"]
    search = fake.calls[2][1]
    assert search["type"] == "video" and search["q"] == "rust explained lifetimes"
    # seed by handle, seed uploads, video search, video details, candidate details, then uploads
    assert fake.resources() == ["channels", "playlistItems", "search", "videos", "channels"] + [
        "playlistItems"
    ] * len(results)
    assert quota.spent == 1 + 1 + 100 + 1 + 1 + len(results)


def test_quota_checked_before_any_api_call():
    provider, fake, _ = live(QuotaTracker(daily_limit=estimate_cost(15) - 1, reserve=0))
    with pytest.raises(QuotaExceededError):
        find_similar_channels(provider, RUST_LAB)
    assert fake.calls == []
