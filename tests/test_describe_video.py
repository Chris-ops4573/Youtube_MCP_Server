"""describe_video: one video's details (1 quota unit)."""

import pytest

from ytmcp.errors import QuotaExceededError, VideoNotFoundError
from ytmcp.models import Video
from ytmcp.services.similar_videos import describe_video
from ytmcp.tools import UNTRUSTED_NOTICE, describe_video_tool


class BudgetProvider:
    """Records the budget asked for and the order of calls."""

    def __init__(self, videos=(), fail=False):
        self.videos, self.fail, self.calls = list(videos), fail, []

    def ensure_budget(self, units):
        self.calls.append(("budget", units))
        if self.fail:
            raise QuotaExceededError("no quota left")

    def get_videos(self, ids):
        self.calls.append(("get_videos", tuple(ids)))
        return self.videos


def video(**changes):
    base = {"id": "aaaaaaaaaaa", "title": "T", "description": "D", "channel_id": "UC1", "channel_title": "C"}
    return Video(**{**base, **changes})


def test_service_returns_the_video_after_checking_a_one_unit_budget():
    provider = BudgetProvider([video()])
    assert describe_video(provider, "aaaaaaaaaaa").id == "aaaaaaaaaaa"
    assert provider.calls == [("budget", 1), ("get_videos", ("aaaaaaaaaaa",))]


def test_service_accepts_a_url():
    provider = BudgetProvider([video()])
    describe_video(provider, "https://youtu.be/aaaaaaaaaaa")
    assert provider.calls[1] == ("get_videos", ("aaaaaaaaaaa",))


def test_service_raises_when_the_video_is_missing():
    with pytest.raises(VideoNotFoundError):
        describe_video(BudgetProvider([]), "aaaaaaaaaaa")


def test_service_rejects_a_bad_reference_before_any_call():
    provider = BudgetProvider([video()])
    with pytest.raises(ValueError):
        describe_video(provider, "nope")
    assert provider.calls == []


def test_tool_shape_with_the_fixture_video(provider):
    out = describe_video_tool(provider, "aaaaaaaaaaa")
    assert out["video"] == {
        "title": "Rust ownership explained",
        "channel": "Rust Lab",
        "duration": "10:00",
        "tags": ["rust", "ownership"],
        "category_id": "27",
        "language": "en",
        "description": "Borrow checker basics",
        "url": "https://www.youtube.com/watch?v=aaaaaaaaaaa",
        "is_live": False,
    }
    assert out["notice"] == UNTRUSTED_NOTICE


def test_tool_shortens_description_and_tags_and_cleans_text():
    long = video(description="x" * 900, tags=[f"t{i}" for i in range(30)], title="a\nb\x00c")
    out = describe_video_tool(BudgetProvider([long]), "aaaaaaaaaaa")["video"]
    assert len(out["description"]) <= 500
    assert len(out["tags"]) == 10
    assert "\n" not in out["title"] and "\x00" not in out["title"]


@pytest.mark.parametrize(
    "provider_, ref, code",
    [
        (BudgetProvider([]), "aaaaaaaaaaa", "VIDEO_NOT_FOUND"),
        (BudgetProvider([video()]), "not a video", "INVALID_VIDEO_REFERENCE"),
        (BudgetProvider([video()], fail=True), "aaaaaaaaaaa", "QUOTA_EXCEEDED"),
    ],
)
def test_tool_errors_have_code_message_and_remediation(provider_, ref, code):
    error = describe_video_tool(provider_, ref)["error"]
    assert error["code"] == code
    assert error["message"] and error["remediation"]
