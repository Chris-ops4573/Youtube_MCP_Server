"""Find channels similar to a given channel (FR-2)."""

import math

from ytmcp.channel_similarity import (
    ChannelProfile,
    ScoredChannel,
    rank_similar_channels,
)
from ytmcp.errors import ChannelNotFoundError
from ytmcp.ids import extract_channel_ref
from ytmcp.models import Channel
from ytmcp.providers.base import VideoProvider
from ytmcp.quota import COSTS, MAX_IDS_PER_CALL

MAX_QUERY_KEYWORDS = 2  # more words make the search too narrow
DEFAULT_SEARCH_SIZE = 15  # each candidate needs one more call for its recent uploads


def estimate_cost(search_size: int) -> int:
    """Quota units for one FR-2 request."""
    return (
        COSTS["channels.list"]  # seed channel
        + COSTS["playlistItems.list"]  # seed recent uploads
        + COSTS["search.list"]  # find candidates
        + math.ceil(search_size / MAX_IDS_PER_CALL) * COSTS["channels.list"]  # candidate details
        + search_size * COSTS["playlistItems.list"]  # candidate recent uploads
    )


def build_channel_query(seed: Channel) -> str:
    """Build a search query from the seed's top keywords.

    Keywords describe what the channel covers. The title is left out because
    it just finds the seed itself, and topics are too generic ("Knowledge").
    A channel with no keywords falls back to its title.
    """
    text = " ".join(seed.keywords[:MAX_QUERY_KEYWORDS]) or seed.title
    return " ".join(dict.fromkeys(text.lower().split()))  # drop repeats, keep order


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
    candidates = provider.search_channels(build_channel_query(seed), search_size)
    profiles = [
        ChannelProfile(c, provider.get_recent_uploads(c.id)) for c in candidates if c.id != seed.id
    ]
    return rank_similar_channels(seed_profile, profiles, top_n=top_n)
