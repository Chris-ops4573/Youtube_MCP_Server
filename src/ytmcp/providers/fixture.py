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