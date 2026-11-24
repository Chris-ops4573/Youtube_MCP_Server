"""A fake YouTube API for tests: serves sample responses, never the network (TQ-5)."""

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SAMPLES = Path(__file__).parent / "fixtures" / "youtube"


def sample(name: str) -> dict:
    return json.loads((SAMPLES / f"{name}.json").read_text())


class FakeYouTube:
    """Use as the provider's `fetch`. Records every call.

    By default it answers like the real API: videos/channels return only the
    requested IDs, search returns search.json. Put (status, body) pairs in
    `queue` to return those first (e.g. errors).
    """

    def __init__(self, queue: list | None = None):
        self.queue = list(queue or [])
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __call__(self, url: str):
        parsed = urlparse(url)
        resource = parsed.path.rsplit("/", 1)[-1]
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        self.calls.append((resource, params))
        if self.queue:
            item = self.queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        if resource == "search":
            return 200, sample("search_channels" if params.get("type") == "channel" else "search")
        if resource == "playlistItems":
            playlist = sample("playlist_items").get(params["playlistId"])
            if playlist is None:
                return 404, {"error": {"errors": [{"reason": "playlistNotFound"}]}}
            return 200, playlist
        if resource == "videoCategories":
            return 200, sample("video_categories")
        if "forHandle" in params:
            wanted = params["forHandle"].lower()
            items = [
                i for i in sample("channels")["items"]
                if i.get("snippet", {}).get("customUrl", "").lower() == wanted
            ]
            return 200, {"items": items}
        ids = params["id"].split(",")
        items = [i for i in sample(resource)["items"] if i["id"] in ids]
        return 200, {"items": items}

    def resources(self) -> list[str]:
        return [resource for resource, _ in self.calls]
