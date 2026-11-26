"""Recommend videos from the signed-in user's likes, subscriptions and playlists (FR-3)."""

import math
from dataclasses import dataclass

from ytmcp.errors import AccountUnavailableError, NotEnoughHistoryError
from ytmcp.providers.base import AccountProvider, VideoProvider
from ytmcp.quota import (
    COSTS,
    LIKES_CAP,
    MAX_IDS_PER_CALL,
    PAGE_SIZE,
    PLAYLISTS_CAP,
    SUBSCRIPTIONS_CAP,
)
from ytmcp.similarity import ScoredRecommendation, build_taste_profile, rank_for_profile

SEARCH_SIZE = 50  # candidates from one search
TOP_TERMS = 3  # words in the search query
MIN_LIKES_FOR_CONFIDENCE = 5


@dataclass(frozen=True)
class Recommendations:
    results: list[ScoredRecommendation]
    likes: int  # how many likes were read
    subscriptions: int
    playlist_videos: int  # distinct videos found in the user's playlists
    low_confidence: bool  # True with fewer than 5 likes


def estimate_cost() -> int:
    """Quota units for one FR-3 request: 137 with the shared caps (FR-3.1 caps each source)."""
    return (
        COSTS["channels.list"]  # find the likes playlist
        + math.ceil(LIKES_CAP / PAGE_SIZE) * COSTS["playlistItems.list"]  # likes pages
        + math.ceil(SUBSCRIPTIONS_CAP / PAGE_SIZE) * COSTS["subscriptions.list"]
        + COSTS["playlists.list"]
        + PLAYLISTS_CAP * COSTS["playlistItems.list"]  # one page per playlist
        + math.ceil(LIKES_CAP / MAX_IDS_PER_CALL) * COSTS["videos.list"]  # details of liked videos
        + COSTS["search.list"]
        + COSTS["videos.list"]  # details of the search results
    )


def recommend_videos(
    provider: VideoProvider, account: AccountProvider | None, top_n: int = 10
) -> Recommendations:
    """Recommend videos the user has not liked or saved. Raises AccountUnavailableError without
    an account (fixture mode), NotEnoughHistoryError with no likes and no subscriptions,
    AuthRequiredError if not signed in, and QuotaExceededError (before any API call)."""
    if account is None:
        raise AccountUnavailableError("Recommendations need your own YouTube data.")
    provider.ensure_budget(estimate_cost())  # before any API call (FR-7.1)

    liked = account.liked_videos(LIKES_CAP)
    subscriptions = account.subscriptions(SUBSCRIPTIONS_CAP)
    if not liked and not subscriptions:
        raise NotEnoughHistoryError("There are no likes or subscriptions to learn your taste from.")
    in_playlists = account.playlist_video_ids(PLAYLISTS_CAP)

    liked_details = provider.get_videos([item.video_id for item in liked])
    profile = build_taste_profile(
        liked_details,
        [s.title for s in subscriptions],
        [s.channel_id for s in subscriptions],
        TOP_TERMS,
    )
    if not profile.top_terms:
        raise NotEnoughHistoryError("Your likes and subscriptions have no words to search with.")

    already_known = {item.video_id for item in liked} | in_playlists  # FR-3.3
    candidates = [
        v
        for v in provider.search_videos(" ".join(profile.top_terms), SEARCH_SIZE)
        if v.id not in already_known
    ]
    return Recommendations(
        results=rank_for_profile(profile, candidates, top_n=top_n),
        likes=len(liked),
        subscriptions=len(subscriptions),
        playlist_videos=len(in_playlists),
        low_confidence=len(liked) < MIN_LIKES_FOR_CONFIDENCE,
    )
