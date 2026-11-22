"""Find videos similar to a given video (FR-1)."""

import math

from ytmcp.errors import VideoNotFoundError
from ytmcp.ids import extract_video_id
from ytmcp.models import Video
from ytmcp.providers.base import VideoProvider
from ytmcp.quota import COSTS, MAX_IDS_PER_CALL
from ytmcp.similarity import ScoredVideo, rank_similar

MAX_QUERY_TAGS = 3


def estimate_cost(search_size: int) -> int:
    """Quota units for one FR-1 request: seed lookup + search + candidate lookup."""
    lookups = 1 + math.ceil(search_size / MAX_IDS_PER_CALL)
    return COSTS["search.list"] + lookups * COSTS["videos.list"]


def build_query(seed: Video) -> str:
    """Build a search query from the seed's title and its top tags."""
    words = f"{seed.title} {' '.join(seed.tags[:MAX_QUERY_TAGS])}".lower().split()
    return " ".join(dict.fromkeys(words))  # drop repeats, keep order


def find_similar_videos(
    provider: VideoProvider,
    video_ref: str,
    top_n: int = 10,
    search_size: int = 25,
) -> list[ScoredVideo]:
    """Return the top_n videos most similar to the given video.

    `video_ref` is an 11-character ID or a YouTube URL. Raises ValueError
    for an invalid reference, VideoNotFoundError if the video is
    private, deleted or missing, and QuotaExceededError (before any API
    call) if the daily quota cannot cover the request.
    """
    video_id = extract_video_id(video_ref)
    provider.ensure_budget(estimate_cost(search_size))

    seeds = provider.get_videos([video_id])
    if not seeds:
        raise VideoNotFoundError(f"Video {video_id} is private, deleted or does not exist")
    seed = seeds[0]

    candidates = provider.search_videos(build_query(seed), max_results=search_size)
    return rank_similar(seed, candidates, top_n=top_n)