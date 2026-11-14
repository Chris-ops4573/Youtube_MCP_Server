import pytest

from ytmcp.tools import format_duration, similar_videos_tool, video_url


@pytest.mark.parametrize(
    "seconds, expected",
    [(0, "0:00"), (45, "0:45"), (600, "10:00"), (3870, "1:04:30"), (-5, "0:00")],
)
def test_format_duration(seconds, expected):
    assert format_duration(seconds) == expected


def test_video_url():
    assert video_url("abcdefghijk") == "https://www.youtube.com/watch?v=abcdefghijk"


def test_success_shape(provider):
    out = similar_videos_tool(provider, "aaaaaaaaaaa")
    (item,) = out["results"]
    assert item["rank"] == 1
    assert item["title"] == "Rust lifetimes tutorial"
    assert item["channel"] == "Rust Lab"
    assert item["duration"] == "15:00"
    assert item["url"] == "https://www.youtube.com/watch?v=bbbbbbbbbbb"
    assert 0 <= item["score"] <= 1
    assert set(item["score_breakdown"]) == {
        "text", "tags", "category", "language", "channel", "duration"
    }
    assert item["low_confidence"] is False


def test_invalid_reference_returns_error(provider):
    out = similar_videos_tool(provider, "not a video")
    assert out["error"]["code"] == "INVALID_VIDEO_REFERENCE"
    assert out["error"]["remediation"]


def test_missing_video_returns_error(provider):
    out = similar_videos_tool(provider, "zzzzzzzzzzz")
    assert out["error"]["code"] == "VIDEO_NOT_FOUND"
    assert "Traceback" not in str(out)


@pytest.mark.parametrize("top_n", [0, -1, 51])
def test_top_n_out_of_range(provider, top_n):
    out = similar_videos_tool(provider, "aaaaaaaaaaa", top_n=top_n)
    assert out["error"]["code"] == "INVALID_ARGUMENT"