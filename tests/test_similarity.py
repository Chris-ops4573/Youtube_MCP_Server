import pytest

from ytmcp.models import Video
from ytmcp.similarity import (
    DEFAULT_WEIGHTS,
    duration_proximity,
    rank_similar,
    tag_overlap,
    text_similarities,
)


def make_video(id: str, **overrides) -> Video:
    defaults = {
        "title": "Untitled",
        "description": "",
        "channel_id": "UC_default",
        "channel_title": "Default",
        "tags": [],
        "category_id": "27",
        "language": "en",
        "duration_seconds": 600,
    }
    return Video(id=id, **{**defaults, **overrides})


@pytest.fixture
def seed():
    return make_video(
        "seed0000000",
        title="Rust ownership explained",
        description="Borrow checker basics",
        channel_id="UC1",
        tags=["rust", "ownership"],
    )


@pytest.fixture
def candidates():
    return [
        make_video(
            "similar0000",
            title="Rust lifetimes and borrowing",
            description="Borrow checker and lifetimes",
            channel_id="UC1",
            tags=["rust", "lifetimes", "ownership"],
            duration_seconds=700,
        ),
        make_video(
            "other000000",
            title="Sourdough for beginners",
            description="Baking bread at home",
            channel_id="UC2",
            tags=["bread"],
            category_id="26",
            duration_seconds=3000,
        ),
        make_video(
            "middle00000",
            title="Learn programming basics",
            description="Variables and loops",
            channel_id="UC3",
            tags=["programming"],
            duration_seconds=620,
        ),
    ]


# --- simple signals ---


def test_tag_overlap_jaccard():
    assert tag_overlap(["a", "b"], ["b", "c"]) == pytest.approx(1 / 3)


def test_tag_overlap_is_case_insensitive():
    assert tag_overlap(["Rust"], ["rust"]) == 1.0


@pytest.mark.parametrize("a, b", [([], ["x"]), (["x"], []), ([], [])])
def test_tag_overlap_empty_is_zero(a, b):
    assert tag_overlap(a, b) == 0.0


def test_duration_proximity():
    assert duration_proximity(600, 600) == 1.0
    assert duration_proximity(300, 600) == pytest.approx(0.5)
    assert duration_proximity(0, 600) == 0.0


# --- text ---


def test_text_similarity_higher_for_related(seed, candidates):
    similar, other, _ = text_similarities(seed, candidates)
    assert similar > other


def test_text_similarity_empty_candidates(seed):
    assert text_similarities(seed, []) == []


def test_text_similarity_only_stop_words_does_not_crash():
    seed = make_video("seed0000000", title="the and of")
    assert text_similarities(seed, [make_video("c0000000000", title="a an the")]) == [0.0]


# --- ranking ---


def test_ranks_similar_video_first(seed, candidates):
    ranked = rank_similar(seed, candidates)
    assert ranked[0].video.id == "similar0000"
    assert ranked[-1].video.id == "other000000"


def test_scores_are_sorted_descending(seed, candidates):
    scores = [s.score for s in rank_similar(seed, candidates)]
    assert scores == sorted(scores, reverse=True)


def test_seed_is_excluded(seed, candidates):
    ranked = rank_similar(seed, [seed, *candidates])
    assert seed.id not in {s.video.id for s in ranked}


def test_duplicates_are_removed(seed, candidates):
    ranked = rank_similar(seed, candidates + candidates)
    assert len(ranked) == len(candidates)


def test_top_n_limits_results(seed, candidates):
    assert len(rank_similar(seed, candidates, top_n=2)) == 2


def test_breakdown_is_present_and_in_range(seed, candidates):
    for item in rank_similar(seed, candidates):
        for value in vars(item.breakdown).values():
            assert 0.0 <= value <= 1.0
        assert 0.0 <= item.score <= 1.0


def test_score_equals_weighted_breakdown(seed, candidates):
    item = rank_similar(seed, candidates)[0]
    expected = sum(DEFAULT_WEIGHTS[k] * getattr(item.breakdown, k) for k in DEFAULT_WEIGHTS)
    assert item.score == pytest.approx(expected)


def test_low_confidence_when_tags_missing(seed):
    untagged = make_video("untagged0000", title="Rust ownership", tags=[])
    (item,) = rank_similar(seed, [untagged])
    assert item.low_confidence is True


def test_not_low_confidence_when_tags_present(seed, candidates):
    assert rank_similar(seed, candidates)[0].low_confidence is False


def test_results_are_deterministic(seed, candidates):
    first = [s.video.id for s in rank_similar(seed, candidates)]
    second = [s.video.id for s in rank_similar(seed, list(reversed(candidates)))]
    assert first == second


def test_empty_candidates_returns_empty(seed):
    assert rank_similar(seed, []) == []


def test_weights_must_sum_to_one(seed, candidates):
    with pytest.raises(ValueError):
        rank_similar(seed, candidates, weights={**DEFAULT_WEIGHTS, "text": 0.9})