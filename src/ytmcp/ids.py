import re
from urllib.parse import urlparse, parse_qs

_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")

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