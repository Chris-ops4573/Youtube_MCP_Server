import pytest

from ytmcp.channel_similarity import (
    DEFAULT_CHANNEL_WEIGHTS,
    ChannelProfile,
    profile_text,
    rank_similar_channels,
)
from ytmcp.models import Channel


def profile(cid, title="T", description="", keywords=(), topics=(), titles=(), subs=100):
    channel = Channel(
        id=cid, title=title, description=description, keywords=list(keywords),
        topics=list(topics), subscriber_count=subs,
    )
    return ChannelProfile(channel, list(titles))


SEED = profile("seed", "Rust Lab", "Rust tutorials", ["rust", "systems"], ["Technology"],
               ["Rust ownership explained", "Rust lifetimes tutorial"])
RUST = profile("rust", "Rust Weekly", "Weekly Rust news", ["rust", "news"], ["Technology"],
               ["Rust async tutorial"])
BAKE = profile("bake", "Bake Club", "Baking bread", ["bread"], ["Food"], ["Sourdough guide"])


def test_weights_sum_to_one():
    assert sum(DEFAULT_CHANNEL_WEIGHTS.values()) == pytest.approx(1)


def test_profile_text_has_all_parts():
    text = profile_text(SEED)
    for part in ["Rust Lab", "Rust tutorials", "systems", "Technology", "lifetimes"]:
        assert part in text


def test_similar_channel_ranks_first():
    ranked = rank_similar_channels(SEED, [BAKE, RUST])
    assert [r.profile.channel.id for r in ranked] == ["rust", "bake"]
    assert ranked[0].score > ranked[1].score


def test_seed_and_duplicates_are_excluded():
    ranked = rank_similar_channels(SEED, [SEED, RUST, RUST, BAKE])
    assert [r.profile.channel.id for r in ranked] == ["rust", "bake"]


def test_top_n_limits_results():
    assert len(rank_similar_channels(SEED, [RUST, BAKE], top_n=1)) == 1


def test_empty_candidates():
    assert rank_similar_channels(SEED, []) == []


def test_score_equals_weighted_breakdown_and_is_in_range():
    (item,) = rank_similar_channels(SEED, [RUST])
    b = item.breakdown
    expected = sum(w * getattr(b, k) for k, w in DEFAULT_CHANNEL_WEIGHTS.items())
    assert item.score == pytest.approx(expected)
    assert all(0 <= v <= 1 for v in vars(b).values())
    assert b.keywords == pytest.approx(1 / 3)  # {rust} of {rust, systems, news}
    assert b.topics == 1.0


def test_subscriber_count_does_not_change_the_score():
    hidden = profile("h", "Rust Weekly", "Weekly Rust news", ["rust", "news"], ["Technology"],
                     ["Rust async tutorial"], subs=None)
    big = profile("h", "Rust Weekly", "Weekly Rust news", ["rust", "news"], ["Technology"],
                  ["Rust async tutorial"], subs=10_000_000)
    assert rank_similar_channels(SEED, [hidden])[0].score == rank_similar_channels(SEED, [big])[0].score


def test_low_confidence_when_labels_missing():
    bare = profile("bare", "Rust Notes", "Rust notes", [], [])
    assert rank_similar_channels(SEED, [bare])[0].low_confidence is True
    assert rank_similar_channels(SEED, [RUST])[0].low_confidence is False
    bare_seed = profile("s", "Rust", "Rust", [], [])
    assert rank_similar_channels(bare_seed, [RUST])[0].low_confidence is True


def test_ties_are_broken_by_id_and_results_are_deterministic():
    a = profile("b-id", "Same", "Same words", ["x"], ["y"])
    b = profile("a-id", "Same", "Same words", ["x"], ["y"])
    first = rank_similar_channels(SEED, [a, b])
    assert [r.profile.channel.id for r in first] == ["a-id", "b-id"]
    assert first == rank_similar_channels(SEED, [b, a])


def test_only_stop_words_does_not_crash():
    stop = profile("stop", "the", "and of", [], [])
    seed = profile("s2", "a", "the", [], [])
    assert rank_similar_channels(seed, [stop])[0].breakdown.text == 0.0


def test_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        rank_similar_channels(SEED, [RUST], weights={"text": 0.5, "keywords": 0.2, "topics": 0.2})
