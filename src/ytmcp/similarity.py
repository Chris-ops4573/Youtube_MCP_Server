"""Metadata-based similarity scoring for videos (FR-1.3, FR-1.4) and channels (FR-2.2, FR-2.3).

YouTube has no "related videos" or "related channels" endpoint, so similarity is
computed locally from metadata. Everything here is a pure function over `Video`
and `Channel` objects: no API calls, no quota, fully deterministic.
"""

import re
from collections import Counter
from dataclasses import dataclass

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ytmcp.models import Channel, Video

# Must sum to 1. Starting guesses; tuned later on sample videos (TBD-2).
DEFAULT_WEIGHTS: dict[str, float] = {
    "text": 0.40,
    "tags": 0.20,
    "category": 0.10,
    "language": 0.05,
    "channel": 0.10,
    "duration": 0.15,
}


@dataclass(frozen=True)
class ScoreBreakdown:
    """Each signal is in [0, 1] before weighting."""

    text: float
    tags: float
    category: float
    language: float
    channel: float
    duration: float


@dataclass(frozen=True)
class ScoredVideo:
    video: Video
    score: float
    breakdown: ScoreBreakdown
    low_confidence: bool  # True when tags are missing (FR-1.4)


# --- simple signals -------------------------------------------------------


def tag_overlap(a: list[str], b: list[str]) -> float:
    """Jaccard similarity of two tag lists, case-insensitive."""
    set_a = {t.lower() for t in a}
    set_b = {t.lower() for t in b}
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def duration_proximity(a: int, b: int) -> float:
    """1.0 for equal durations, falling toward 0 as they differ."""
    if a <= 0 or b <= 0:
        return 0.0
    return 1 - abs(a - b) / max(a, b)


def _same(a: str | None, b: str | None) -> float:
    return 1.0 if a is not None and a == b else 0.0


# --- text similarity ------------------------------------------------------


def _text_of(video: Video) -> str:
    return f"{video.title} {video.description} {' '.join(video.tags)}"


def tfidf_similarities(seed_text: str, texts: list[str]) -> list[float]:
    """TF-IDF cosine similarity of each text to the seed text."""
    if not texts:
        return []
    docs = [seed_text, *texts]
    try:
        matrix = TfidfVectorizer(stop_words="english").fit_transform(docs)
    except ValueError:  # empty vocabulary, e.g. only stop words
        return [0.0] * len(texts)
    return [float(s) for s in cosine_similarity(matrix[0], matrix[1:]).ravel()]


def text_similarities(seed: Video, candidates: list[Video]) -> list[float]:
    """TF-IDF cosine similarity of each candidate video to the seed."""
    return tfidf_similarities(_text_of(seed), [_text_of(c) for c in candidates])


# --- ranking --------------------------------------------------------------


def rank_similar(
    seed: Video,
    candidates: list[Video],
    top_n: int = 10,
    weights: dict[str, float] | None = None,
) -> list[ScoredVideo]:
    """Rank candidates by similarity to the seed, best first.

    The seed itself and duplicate candidates are excluded. Ties are
    broken by video ID so results are deterministic.
    """
    weights = weights or DEFAULT_WEIGHTS
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ValueError("Similarity weights must sum to 1")

    unique: dict[str, Video] = {}
    for c in candidates:
        if c.id != seed.id:
            unique.setdefault(c.id, c)
    pool = list(unique.values())

    texts = text_similarities(seed, pool)
    scored = []
    for video, text in zip(pool, texts, strict=True):
        breakdown = ScoreBreakdown(
            text=text,
            tags=tag_overlap(seed.tags, video.tags),
            category=_same(seed.category_id, video.category_id),
            language=_same(seed.language, video.language),
            channel=_same(seed.channel_id, video.channel_id),
            duration=duration_proximity(seed.duration_seconds, video.duration_seconds),
        )
        score = sum(weights[name] * getattr(breakdown, name) for name in weights)
        scored.append(
            ScoredVideo(
                video=video,
                score=score,
                breakdown=breakdown,
                low_confidence=not seed.tags or not video.tags,
            )
        )

    scored.sort(key=lambda s: (-s.score, s.video.id))
    return scored[:top_n]


# --- topic words (used by channels and recommendations) ------------------------

_WORD = re.compile(r"[^\W\d_]{3,}")  # words made of 3 or more letters
# Words that name the format of a video, not what it is about. A real test showed "shorts" as
# the top interest of someone whose likes are mostly Shorts, which says nothing about taste.
FORMAT_WORDS = frozenset(
    {"shorts", "short", "video", "videos", "official", "full", "viral", "trending",
     "subscribe", "youtube", "edit", "edits"}
)


def _words(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in ENGLISH_STOP_WORDS and w not in FORMAT_WORDS]


def top_words(documents: list[str], n: int, exclude: frozenset[str] = frozenset()) -> list[str]:
    """The n most common topic words. A word counts once per document, so one document that
    repeats a word cannot outweigh the rest. Ties are broken alphabetically."""
    counts = Counter(
        word for document in documents for word in set(_words(document)) if word not in exclude
    )
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [word for word, _ in ranked[:n]]


# --- channels (FR-2.2, FR-2.3) --------------------------------------------
# A channel is described by a profile: its description, keywords, topics and the titles of
# its recent uploads (not its name, see ADR-020). Candidates are ranked by how similar their profile is to
# the seed channel's. Subscriber counts are never used for ranking (SRS 5.5: metadata,
# not engagement counts), so hidden counts cannot affect a score.

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
    """What the channel publishes. The title is left out on purpose: two channels with similar
    names are not similar unless their content is (ADR-020)."""
    c = profile.channel
    parts = [c.description, *c.keywords, *c.topics, *profile.recent_titles]
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


# --- taste profile for recommendations (FR-3.2) -----------------------------
# The user's likes and subscriptions become a taste profile, and candidate videos are scored
# against it. Still pure: no API calls, deterministic.

# Must sum to 1. Starting guesses; tuned later on real examples (TBD-2).
DEFAULT_TASTE_WEIGHTS: dict[str, float] = {
    "text": 0.60,
    "category": 0.20,
    "channel": 0.20,
}

LIKED_OFTEN_SHARE = 0.20  # a category is "liked often" when it is 20% of the user's likes
LOW_SCORE = 0.25  # a recommendation below this is a weak match (a starting guess, TBD-2)


@dataclass(frozen=True)
class TasteProfile:
    text: str  # liked titles and tags (subscription titles when there are no likes)
    top_terms: list[str]  # the most common words: they become the search query
    category_share: dict[str, float]  # category ID -> share of the user's likes
    channel_ids: frozenset[str]  # channels the user liked a video from, or subscribes to


@dataclass(frozen=True)
class RecommendationBreakdown:
    """Each signal is in [0, 1] before weighting."""

    text: float
    category: float
    channel: float


@dataclass(frozen=True)
class ScoredRecommendation:
    video: Video
    score: float
    breakdown: RecommendationBreakdown
    reason: str  # a short explanation from metadata (FR-3.3)


def build_taste_profile(
    liked: list[Video],
    subscription_titles: list[str],
    subscribed_channel_ids: list[str],
    term_count: int = 3,
) -> TasteProfile:
    """Describe what the user likes. With no liked videos, subscription titles stand in."""
    documents = [f"{v.title} {' '.join(v.tags)}" for v in liked]
    liked_text = " ".join(documents)
    if not liked_text.strip():  # no likes: the subscription titles stand in
        documents = list(subscription_titles)
    text = liked_text if liked_text.strip() else " ".join(subscription_titles)
    categories = Counter(v.category_id for v in liked if v.category_id)
    return TasteProfile(
        text=text,
        top_terms=top_words(documents, term_count),  # once per video, so long tag lists cannot dominate
        category_share={cid: n / len(liked) for cid, n in categories.items()},
        channel_ids=frozenset([v.channel_id for v in liked if v.channel_id] + subscribed_channel_ids),
    )


def reason_for(profile: TasteProfile, video: Video) -> str:
    """One short reason, the first that applies (FR-3.3)."""
    if video.channel_id in profile.channel_ids:
        return f"From a channel you like or subscribe to: {video.channel_title}"
    title_words = set(_words(video.title))
    matched = [term for term in profile.top_terms if term in title_words]
    if matched:
        return f"Matches your interests: {', '.join(matched)}"
    share = profile.category_share.get(video.category_id or "", 0.0)
    if share >= LIKED_OFTEN_SHARE:
        return f"In a category you like often ({round(share * 100)}% of your likes)"
    return "Similar to videos you liked"


def rank_for_profile(
    profile: TasteProfile,
    candidates: list[Video],
    top_n: int = 10,
    weights: dict[str, float] | None = None,
) -> list[ScoredRecommendation]:
    """Rank candidate videos for a taste profile, best first. Duplicates are dropped and ties
    are broken by video ID, so results are deterministic."""
    weights = weights or DEFAULT_TASTE_WEIGHTS
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ValueError("Similarity weights must sum to 1")

    unique: dict[str, Video] = {}
    for candidate in candidates:
        unique.setdefault(candidate.id, candidate)
    pool = list(unique.values())

    texts = tfidf_similarities(profile.text, [_text_of(v) for v in pool])
    scored = []
    for video, text in zip(pool, texts, strict=True):
        breakdown = RecommendationBreakdown(
            text=text,
            category=profile.category_share.get(video.category_id or "", 0.0),
            channel=1.0 if video.channel_id in profile.channel_ids else 0.0,
        )
        score = sum(weights[name] * getattr(breakdown, name) for name in weights)
        scored.append(ScoredRecommendation(video, score, breakdown, reason_for(profile, video)))

    scored.sort(key=lambda s: (-s.score, s.video.id))
    return scored[:top_n]
