"""Metadata-based video similarity scoring (FR-1.3, FR-1.4).

YouTube has no "related videos" endpoint, so similarity is computed
locally from metadata. Everything here is a pure function over `Video`
objects: no API calls, no quota, fully deterministic.
"""

from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ytmcp.models import Video

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


def text_similarities(seed: Video, candidates: list[Video]) -> list[float]:
    """TF-IDF cosine similarity of each candidate to the seed."""
    if not candidates:
        return []
    docs = [_text_of(seed)] + [_text_of(c) for c in candidates]
    try:
        matrix = TfidfVectorizer(stop_words="english").fit_transform(docs)
    except ValueError:  # empty vocabulary, e.g. only stop words
        return [0.0] * len(candidates)
    return [float(s) for s in cosine_similarity(matrix[0], matrix[1:]).ravel()]


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