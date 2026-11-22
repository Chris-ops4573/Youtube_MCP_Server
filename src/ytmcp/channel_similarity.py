"""Channel similarity scoring (FR-2.2, FR-2.3).

A channel is described by a profile: its title, description, keywords,
topics and the titles of its recent uploads. Candidates are ranked by how
similar their profile is to the seed channel's. Like video scoring, these
are pure functions: no API calls, deterministic.

Subscriber counts are never used for ranking (SRS 5.5: metadata, not
engagement counts), so hidden counts cannot affect a score.
"""

from dataclasses import dataclass

from ytmcp.models import Channel
from ytmcp.similarity import tag_overlap, tfidf_similarities

# Must sum to 1. Starting guesses; tuned later on sample channels (TBD-2).
DEFAULT_CHANNEL_WEIGHTS: dict[str, float] = {
    "text": 0.60,
    "keywords": 0.25,
    "topics": 0.15,
}


@dataclass(frozen=True)
class ChannelProfile:
    channel: Channel
    recent_titles: list[str]


@dataclass(frozen=True)
class ChannelScoreBreakdown:
    """Each signal is in [0, 1] before weighting."""

    text: float
    keywords: float
    topics: float


@dataclass(frozen=True)
class ScoredChannel:
    profile: ChannelProfile
    score: float
    breakdown: ChannelScoreBreakdown
    low_confidence: bool  # True when keywords and topics are both missing


def profile_text(profile: ChannelProfile) -> str:
    c = profile.channel
    parts = [c.title, c.description, *c.keywords, *c.topics, *profile.recent_titles]
    return " ".join(parts)


def _has_labels(channel: Channel) -> bool:
    return bool(channel.keywords or channel.topics)


def rank_similar_channels(
    seed: ChannelProfile,
    candidates: list[ChannelProfile],
    top_n: int = 10,
    weights: dict[str, float] | None = None,
) -> list[ScoredChannel]:
    """Rank candidate channels by similarity to the seed, best first.

    The seed channel and duplicate candidates are excluded. Ties are broken
    by channel ID so results are deterministic.
    """
    weights = weights or DEFAULT_CHANNEL_WEIGHTS
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ValueError("Similarity weights must sum to 1")

    unique: dict[str, ChannelProfile] = {}
    for candidate in candidates:
        if candidate.channel.id != seed.channel.id:
            unique.setdefault(candidate.channel.id, candidate)
    pool = list(unique.values())

    texts = tfidf_similarities(profile_text(seed), [profile_text(p) for p in pool])
    scored = []
    for profile, text in zip(pool, texts, strict=True):
        channel = profile.channel
        breakdown = ChannelScoreBreakdown(
            text=text,
            keywords=tag_overlap(seed.channel.keywords, channel.keywords),
            topics=tag_overlap(seed.channel.topics, channel.topics),
        )
        score = sum(weights[name] * getattr(breakdown, name) for name in weights)
        scored.append(
            ScoredChannel(
                profile=profile,
                score=score,
                breakdown=breakdown,
                low_confidence=not _has_labels(seed.channel) or not _has_labels(channel),
            )
        )

    scored.sort(key=lambda s: (-s.score, s.profile.channel.id))
    return scored[:top_n]
