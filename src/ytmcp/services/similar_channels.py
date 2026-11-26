"""Find channels similar to a given channel (FR-2)."""

import math

from ytmcp.errors import ChannelNotFoundError
from ytmcp.ids import extract_channel_ref
from ytmcp.models import Channel, Video
from ytmcp.providers.base import VideoProvider
from ytmcp.quota import COSTS, MAX_IDS_PER_CALL
from ytmcp.similarity import (
    ChannelProfile,
    ScoredChannel,
    rank_similar_channels,
    top_words,
)

QUERY_WORDS = 3  # more words make the search too narrow
MAX_QUERY_KEYWORDS = 2  # used only when the uploads and keywords give no topic words
VIDEO_SEARCH_SIZE = 50  # videos searched; their channels become the candidates
DEFAULT_SEARCH_SIZE = 15  # candidate channels: each needs one more call for its recent uploads


def estimate_cost(search_size: int) -> int:
    """Quota units for one FR-2 request."""
    return (
        COSTS["channels.list"]  # seed channel
        + COSTS["playlistItems.list"]  # seed recent uploads
        + COSTS["search.list"]  # find videos on the seed's topics
        + math.ceil(VIDEO_SEARCH_SIZE / MAX_IDS_PER_CALL) * COSTS["videos.list"]  # their details
        + math.ceil(search_size / MAX_IDS_PER_CALL) * COSTS["channels.list"]  # candidate details
        + search_size * COSTS["playlistItems.list"]  # candidate recent uploads
    )


def build_channel_query(seed: Channel, recent_titles: list[str]) -> str:
    """Build a search query from what the channel publishes (ADR-020).

    The most common topic words in its recent upload titles and keywords. Words from the
    channel's name are left out, because a name only finds channels with similar names,
    unless the creator also lists the word as a keyword (then it names the topic, like
    "rust" in "Rust Lab"). With no topic words left, fall back to the keywords, then the title.
    """
    keywords = {k.lower() for k in seed.keywords}
    name_words = frozenset(w for w in seed.title.lower().split() if w not in keywords)
    words = top_words([*recent_titles, *seed.keywords], QUERY_WORDS, exclude=name_words)
    text = " ".join(words) or " ".join(seed.keywords[:MAX_QUERY_KEYWORDS]) or seed.title
    return " ".join(dict.fromkeys(text.lower().split()))  # drop repeats, keep order


def candidate_channel_ids(videos: list[Video], seed_id: str, limit: int) -> list[str]:
    """The channels behind the found videos, in result order, without the seed or repeats."""
    ids = [v.channel_id for v in videos if v.channel_id and v.channel_id != seed_id]
    return list(dict.fromkeys(ids))[:limit]


def find_similar_channels(
    provider: VideoProvider,
    channel_ref: str,
    top_n: int = 10,
    search_size: int = DEFAULT_SEARCH_SIZE,
) -> list[ScoredChannel]:
    """Return the top_n channels most similar to the given channel.

    `channel_ref` is a channel ID, an @handle or a YouTube channel URL.
    Raises ValueError for an invalid reference, ChannelNotFoundError if the
    channel does not exist, and QuotaExceededError (before any API call) if
    the daily quota cannot cover the request.

    Candidates are found by searching for videos on the seed's topics and taking the
    channels that made them, because a channel search matches mostly on channel names.
    """
    kind, value = extract_channel_ref(channel_ref)
    provider.ensure_budget(estimate_cost(search_size))

    if kind == "handle":
        seed = provider.get_channel_by_handle(value)
    else:
        found = provider.get_channels([value])
        seed = found[0] if found else None
    if seed is None:
        raise ChannelNotFoundError(f"Channel {value} does not exist")

    seed_profile = ChannelProfile(seed, provider.get_recent_uploads(seed.id))
    videos = provider.search_videos(build_channel_query(seed, seed_profile.recent_titles), VIDEO_SEARCH_SIZE)
    candidates = provider.get_channels(candidate_channel_ids(videos, seed.id, search_size))
    profiles = [ChannelProfile(c, provider.get_recent_uploads(c.id)) for c in candidates]
    return rank_similar_channels(seed_profile, profiles, top_n=top_n)
