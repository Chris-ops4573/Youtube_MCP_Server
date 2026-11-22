import re
from urllib.parse import parse_qs, unquote, urlparse

_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_CHANNEL_ID = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
_HANDLE = re.compile(r"^@[A-Za-z0-9._-]{3,30}$")

def extract_video_id(value: str) -> str:
    """Return the 11-char video ID from an ID or YouTube URL.
    Raises ValueError if it can't be found or is invalid."""
    value = value.strip()
    if _ID.match(value):
        return value

    url = urlparse(value)
    host = (url.hostname or "").removeprefix("www.")
    candidate = None

    if host == "youtu.be":
        candidate = url.path.lstrip("/")
    elif host in ("youtube.com", "m.youtube.com"):
        if url.path == "/watch":
            candidate = parse_qs(url.query).get("v", [None])[0]
        else:
            parts = url.path.strip("/").split("/")
            if len(parts) >= 2 and parts[0] in ("shorts", "embed"):
                candidate = parts[1]

    if candidate and _ID.match(candidate):
        return candidate
    raise ValueError(f"Invalid YouTube video ID or URL: {value!r}")


def extract_channel_ref(value: str) -> tuple[str, str]:
    """Return ("id", "UC...") or ("handle", "@name") from a channel ID,
    @handle, or a youtube.com/channel/... or youtube.com/@... URL (FR-2.1).
    Raises ValueError if it is none of these."""
    value = value.strip()
    if _CHANNEL_ID.match(value):
        return "id", value
    if _HANDLE.match(value):
        return "handle", value

    url = urlparse(value)
    if (url.hostname or "").removeprefix("www.") in ("youtube.com", "m.youtube.com"):
        parts = [unquote(p) for p in url.path.split("/") if p]
        if parts and _HANDLE.match(parts[0]):
            return "handle", parts[0]
        if len(parts) >= 2 and parts[0] == "channel" and _CHANNEL_ID.match(parts[1]):
            return "id", parts[1]
    raise ValueError(f"Invalid YouTube channel ID, @handle or URL: {value!r}")
