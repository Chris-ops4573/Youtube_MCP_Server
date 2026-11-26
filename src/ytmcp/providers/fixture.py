import json
from pathlib import Path

from ytmcp.models import Channel, Video
from ytmcp.providers.base import VideoProvider


class FixtureProvider(VideoProvider):
    def __init__(self, fixtures_dir: Path):
        self._videos = {
            v["id"]: Video(**v)
            for v in json.loads((fixtures_dir / "videos.json").read_text())
        }
        self._channels = {
            c["id"]: Channel(**c)
            for c in json.loads((fixtures_dir / "channels.json").read_text())
        }
        categories_file = fixtures_dir / "categories.json"
        self._categories: dict[str, str] = (
            json.loads(categories_file.read_text()) if categories_file.exists() else {}
        )
        uploads_file = fixtures_dir / "uploads.json"
        self._uploads: dict[str, list[str]] = (
            json.loads(uploads_file.read_text()) if uploads_file.exists() else {}
        )

    def get_videos(self, video_ids):
        return [self._videos[i] for i in video_ids if i in self._videos]

    def search_videos(self, query, max_results=25):
        terms = query.lower().split()
        hits = [
            v for v in self._videos.values()
            if any(t in f"{v.title} {v.description}".lower() for t in terms)
        ]
        return hits[:max_results]

    def get_channels(self, channel_ids):
        return [self._channels[i] for i in channel_ids if i in self._channels]

    def get_channel_by_handle(self, handle):
        for channel in self._channels.values():
            if channel.handle and channel.handle.lower() == handle.lower():
                return channel
        return None

    def category_names(self, region="US"):
        return dict(self._categories)

    def get_recent_uploads(self, channel_id, max_results=10):
        return self._uploads.get(channel_id, [])[:max_results]
