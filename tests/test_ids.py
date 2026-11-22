import pytest

from ytmcp.ids import extract_channel_ref, extract_video_id

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

# --- channel references (FR-2.1) -------------------------------------------

CHANNEL_ID = "UC" + "x" * 22


@pytest.mark.parametrize(
    "value, expected",
    [
        (CHANNEL_ID, ("id", CHANNEL_ID)),
        (f"  {CHANNEL_ID}  ", ("id", CHANNEL_ID)),
        ("@rustlab", ("handle", "@rustlab")),
        (f"https://www.youtube.com/channel/{CHANNEL_ID}", ("id", CHANNEL_ID)),
        (f"https://youtube.com/channel/{CHANNEL_ID}/videos", ("id", CHANNEL_ID)),
        ("https://www.youtube.com/@rustlab", ("handle", "@rustlab")),
        ("https://m.youtube.com/@rust.lab/videos", ("handle", "@rust.lab")),
        ("https://www.youtube.com/%40rustlab", ("handle", "@rustlab")),
    ],
)
def test_channel_ref_valid(value, expected):
    assert extract_channel_ref(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "rustlab",  # a bare name is ambiguous, needs the @
        "UC123",  # too short
        "@ab",  # handle too short
        "https://www.youtube.com/c/rustlab",  # legacy custom URL
        "https://www.youtube.com/channel/UC123",
        "https://example.com/@rustlab",
        "https://www.youtube.com/watch?v=aaaaaaaaaaa",
    ],
)
def test_channel_ref_invalid(value):
    with pytest.raises(ValueError):
        extract_channel_ref(value)
