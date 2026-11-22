import pytest
from fake_youtube import FakeYouTube

from ytmcp.providers.youtube import YouTubeProvider
from ytmcp.quota import QuotaTracker
from ytmcp.tools import channel_url, similar_channels_tool

RUST_LAB = "UC1111111111111111111111"


def test_channel_url():
    assert channel_url(RUST_LAB) == f"https://www.youtube.com/channel/{RUST_LAB}"


def test_success_shape(provider):
    out = similar_channels_tool(provider, RUST_LAB)
    (item,) = out["results"]
    assert item["rank"] == 1
    assert item["title"] == "Rust Weekly"
    assert item["handle"] == "@rustweekly"
    assert item["subscribers"] == 500
    assert item["url"] == "https://www.youtube.com/channel/UC3333333333333333333333"
    assert 0 <= item["score"] <= 1
    assert set(item["score_breakdown"]) == {"text", "keywords", "topics"}
    assert item["low_confidence"] is False


def test_hidden_subscribers_are_labelled(provider):
    out = similar_channels_tool(provider, "@sourdoughdaily")
    assert out["results"][0]["title"] == "Bake Club"
    assert out["results"][0]["subscribers"] == "hidden"


def test_invalid_reference_returns_error(provider):
    out = similar_channels_tool(provider, "not a channel")
    assert out["error"]["code"] == "INVALID_CHANNEL_REFERENCE"
    assert out["error"]["remediation"]


def test_missing_channel_returns_error(provider):
    out = similar_channels_tool(provider, "UC5555555555555555555555")
    assert out["error"]["code"] == "CHANNEL_NOT_FOUND"
    assert "Traceback" not in str(out)


@pytest.mark.parametrize("top_n", [0, -1, 51])
def test_top_n_out_of_range(provider, top_n):
    assert similar_channels_tool(provider, RUST_LAB, top_n=top_n)["error"]["code"] == "INVALID_ARGUMENT"


def test_quota_error_has_remediation():
    provider = YouTubeProvider("k", quota=QuotaTracker(daily_limit=0, reserve=0), fetch=FakeYouTube())
    out = similar_channels_tool(provider, RUST_LAB)
    assert out["error"]["code"] == "QUOTA_EXCEEDED"
    assert "midnight Pacific" in out["error"]["remediation"]


def test_missing_api_key_error():
    out = similar_channels_tool(YouTubeProvider(None), RUST_LAB)
    assert out["error"]["code"] == "API_KEY_MISSING"
