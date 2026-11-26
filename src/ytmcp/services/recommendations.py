"""Recommend videos from the signed-in user's likes, subscriptions and playlists (FR-3)."""

import math
from dataclasses import dataclass

from ytmcp.errors import (
    AccountUnavailableError,
    InvalidArgumentError,
    NotEnoughHistoryError,
)
from ytmcp.models import Video
from ytmcp.playlist_planner import DEFAULT_MIN_VIDEO_MINUTES
from ytmcp.providers.base import AccountProvider, VideoProvider
from ytmcp.quota import (
    COSTS,
    LIKES_CAP,
    MAX_IDS_PER_CALL,
    PAGE_SIZE,
    PLAYLISTS_CAP,
    SUBSCRIPTIONS_CAP,
)
from ytmcp.similarity import (
    LOW_SCORE,
    ScoredRecommendation,
    build_taste_profile,
    rank_for_profile,
)

SEARCH_SIZE = 50  # candidates from one search
TOP_TERMS = 3  # words in the search query
MIN_LIKES_FOR_CONFIDENCE = 5


@dataclass(frozen=True)
class Recommendations:
    results: list[ScoredRecommendation]
    likes: int  # how many likes were read
    subscriptions: int
    playlist_videos: int  # distinct videos found in the user's playlists
    low_confidence: bool  # True when confidence_note says why
    confidence_note: str | None  # why the results may be weak, or None
    min_video_minutes: int  # the minimum length used (0 = none)
    left_out_short: int  # candidates left out for being live or shorter than the minimum


def validate_min_video_minutes(value: object) -> int:
    """None means the default (3 minutes, as in propose_playlist), 0 turns the minimum off."""
    if value is None:
        return DEFAULT_MIN_VIDEO_MINUTES
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise InvalidArgumentError(
            "Some arguments are not valid: min_video_minutes.",
            {"min_video_minutes": "must be a whole number of minutes, 0 or more (0 = no minimum)"},
        )
    return value


def long_enough(video: Video, min_video_minutes: int) -> bool:
    """Live videos and clips under the minimum are left out, unless the minimum is 0."""
    if min_video_minutes == 0:
        return True
    return not video.is_live and video.duration_seconds >= min_video_minutes * 60


def confidence_note(likes: int, results: list[ScoredRecommendation]) -> str | None:
    """Say why the results may be weak: too little history, nothing found, or low scores."""
    reasons = []
    if likes < MIN_LIKES_FOR_CONFIDENCE:
        reasons.append(f"Only {likes} likes were read, so your taste profile is thin.")
    if not results:
        reasons.append("No new videos were found for your interests.")
    elif results[0].score < LOW_SCORE:
        reasons.append(
            f"The best match scores {results[0].score:.2f}, below {LOW_SCORE}, so these are weak matches."
        )
    return " ".join(reasons) or None


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
    provider: VideoProvider,
    account: AccountProvider | None,
    top_n: int = 10,
    min_video_minutes: int = DEFAULT_MIN_VIDEO_MINUTES,
) -> Recommendations:
    """Recommend videos the user has not liked or saved, at least `min_video_minutes` long
    (0 = any length). Raises AccountUnavailableError without an account (fixture mode),
    NotEnoughHistoryError with no likes and no subscriptions, AuthRequiredError if not signed
    in, and QuotaExceededError (before any API call)."""
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
    new = [
        v
        for v in provider.search_videos(" ".join(profile.top_terms), SEARCH_SIZE)
        if v.id not in already_known
    ]
    candidates = [v for v in new if long_enough(v, min_video_minutes)]
    results = rank_for_profile(profile, candidates, top_n=top_n)
    note = confidence_note(len(liked), results)
    return Recommendations(
        results=results,
        likes=len(liked),
        subscriptions=len(subscriptions),
        playlist_videos=len(in_playlists),
        low_confidence=note is not None,
        confidence_note=note,
        min_video_minutes=min_video_minutes,
        left_out_short=len({v.id for v in new}) - len({v.id for v in candidates}),
    )
