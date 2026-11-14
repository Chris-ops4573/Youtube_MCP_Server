import pytest

from ytmcp.ids import extract_video_id

VID = "dQw4w9WgXcQ"

@pytest.mark.parametrize("value", [
    VID,
    f"https://www.youtube.com/watch?v={VID}",
    f"https://www.youtube.com/watch?v={VID}&t=30s",
    f"https://youtu.be/{VID}",
    f"https://www.youtube.com/shorts/{VID}",
    f"https://www.youtube.com/embed/{VID}",
])
def test_valid(value):
    assert extract_video_id(value) == VID

@pytest.mark.parametrize("value", ["", "abc", "https://example.com/watch?v=" + VID, "not a url"])
def test_invalid(value):
    with pytest.raises(ValueError):
        extract_video_id(value)