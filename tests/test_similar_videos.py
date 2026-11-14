import pytest

from ytmcp.errors import VideoNotFoundError
from ytmcp.models import Video
from ytmcp.services import build_query, find_similar_videos


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