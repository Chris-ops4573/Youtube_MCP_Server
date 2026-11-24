"""Plan a playlist from candidate videos (FR-5.1, FR-5.2, FR-5.3).

Pure functions: no API calls, no clock, fully deterministic. Everything the
user typed is checked here before any API call is made (FR-5.1).
"""

import re
import unicodedata
from dataclasses import dataclass

from ytmcp.errors import InvalidConstraintsError, NoVideosFoundError
from ytmcp.models import Video

MIN_TOTAL_MINUTES = 5
MAX_TOTAL_MINUTES = 24 * 60  # assumed maximum playlist length (TBD-6)
TOLERANCE_PERCENT = 10  # the total must be within +-10% of the target (FR-5.3)
MAX_TOPIC_CHARS = 100
MAX_TITLE_CHARS = 150  # YouTube's own limit for a playlist title
SEARCH_SIZE = 50  # one page of search results
SHORT_CLIP_SECONDS = 180  # YouTube Shorts can be up to 3 minutes
DEFAULT_MIN_VIDEO_MINUTES = 3  # used when min_video_minutes is not given; 0 turns it off

_LANGUAGE = re.compile(r"^[a-z]{2,3}$")


@dataclass(frozen=True)
class Constraints:
    topic: str
    total_minutes: int
    max_video_minutes: int | None
    language: str | None  # primary subtag, e.g. "en"
    title: str
    min_video_minutes: int | None = None  # leave out shorter videos, e.g. Shorts


@dataclass(frozen=True)
class Selection:
    videos: list[Video]
    total_seconds: int
    target_seconds: int
    longest_seconds: int
    meets_target: bool  # total is within +-10% of the target
    notes: list[str]  # plain-language explanations of anything unmet or left out


def clean_text(text: str, limit: int) -> str:
    """Make untrusted text (from YouTube or the user) safe to show: one line, no control
    characters, no more than `limit` characters. It is still just data, never instructions."""
    kept = "".join(" " if ch in "\r\n\t" else ch for ch in text if ch in "\r\n\t" or unicodedata.category(ch)[0] != "C")
    kept = " ".join(kept.split())
    return kept if len(kept) <= limit else kept[: limit - 1].rstrip() + "…"


def _is_whole_number(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validate_constraints(
    topic: object,
    total_minutes: object,
    max_video_minutes: object = None,
    language: object = None,
    title: object = None,
    min_video_minutes: object = None,
) -> Constraints:
    """Check every field and report all problems at once, field by field (FR-5.1)."""
    fields: dict[str, str] = {}
    if isinstance(language, str) and not language.strip():
        language = None  # AI clients often send "" for an optional field they are not using
    if isinstance(title, str) and not clean_text(title, 10_000):
        title = None

    clean_topic = ""
    if not isinstance(topic, str) or not topic.strip():
        fields["topic"] = "must be some text, for example 'rust programming'"
    else:
        clean_topic = clean_text(topic, 10_000)
        if len(clean_topic) > MAX_TOPIC_CHARS:
            fields["topic"] = f"must be at most {MAX_TOPIC_CHARS} characters"

    total = 0
    if not _is_whole_number(total_minutes) or not MIN_TOTAL_MINUTES <= total_minutes <= MAX_TOTAL_MINUTES:  # type: ignore[operator]
        fields["total_minutes"] = (
            f"must be a whole number of minutes from {MIN_TOTAL_MINUTES} to {MAX_TOTAL_MINUTES}"
        )
    else:
        total = total_minutes  # type: ignore[assignment]

    longest: int | None = None
    if max_video_minutes is not None:
        if not _is_whole_number(max_video_minutes) or max_video_minutes < 1:  # type: ignore[operator]
            fields["max_video_minutes"] = "must be a whole number of minutes, at least 1"
        elif total and max_video_minutes > total:  # type: ignore[operator]
            fields["max_video_minutes"] = "cannot be longer than total_minutes"
        else:
            longest = max_video_minutes  # type: ignore[assignment]

    shortest: int | None = None
    if min_video_minutes is None:
        # Default: leave out clips under DEFAULT_MIN_VIDEO_MINUTES, unless that cannot fit the settings
        fits = (not total or DEFAULT_MIN_VIDEO_MINUTES <= total) and (
            longest is None or DEFAULT_MIN_VIDEO_MINUTES <= longest
        )
        shortest = DEFAULT_MIN_VIDEO_MINUTES if fits else None
    elif not _is_whole_number(min_video_minutes) or min_video_minutes < 0:  # type: ignore[operator]
        fields["min_video_minutes"] = "must be a whole number of minutes, 0 or more (0 = no minimum)"
    elif min_video_minutes == 0:
        shortest = None  # the person asked for short clips to stay
    elif total and min_video_minutes > total:  # type: ignore[operator]
        fields["min_video_minutes"] = "cannot be longer than total_minutes"
    elif longest is not None and min_video_minutes > longest:  # type: ignore[operator]
        fields["min_video_minutes"] = "cannot be longer than max_video_minutes"
    else:
        shortest = min_video_minutes  # type: ignore[assignment]

    lang: str | None = None
    if language is not None:
        primary = str(language).strip().lower().replace("_", "-").split("-")[0]
        if not isinstance(language, str) or not _LANGUAGE.match(primary):
            fields["language"] = "must be a language code such as 'en' or 'de'"
        else:
            lang = primary

    final_title = ""
    if title is not None and not isinstance(title, str):
        fields["title"] = "must be some text, or left out"
    elif isinstance(title, str):
        final_title = clean_text(title, 10_000)
        if len(final_title) > MAX_TITLE_CHARS:
            fields["title"] = f"must be at most {MAX_TITLE_CHARS} characters"

    if fields:
        raise InvalidConstraintsError(
            "Some playlist settings are not valid: " + ", ".join(sorted(fields)) + ".", fields
        )
    return Constraints(
        topic=clean_topic,
        total_minutes=total,
        max_video_minutes=longest,
        language=lang,
        title=final_title or clean_text(f"{clean_topic} ({total} min)", MAX_TITLE_CHARS),
        min_video_minutes=shortest,
    )


def _minutes(seconds: float) -> str:
    return f"{round(seconds / 60)} min"


def select_videos(candidates: list[Video], constraints: Constraints) -> Selection:
    """Choose videos, in the order given (search relevance), for a total within +-10% of the
    target (FR-5.3). Drops live, unavailable, too-long and wrong-language videos (FR-5.2)
    and duplicates. Raises NoVideosFoundError if nothing is left."""
    target = constraints.total_minutes * 60

    def at_most_upper(seconds: int) -> bool:  # whole-number maths: no rounding at the edges
        return seconds * 100 <= target * (100 + TOLERANCE_PERCENT)

    def at_least_lower(seconds: int) -> bool:
        return seconds * 100 >= target * (100 - TOLERANCE_PERCENT)

    longest_allowed = (
        constraints.max_video_minutes * 60 if constraints.max_video_minutes else None
    )

    shortest_allowed = (
        constraints.min_video_minutes * 60 if constraints.min_video_minutes else None
    )

    dropped = {"live": 0, "no length": 0, "too long": 0, "too short": 0, "language": 0}
    seen: set[str] = set()
    eligible: list[Video] = []
    for video in candidates:
        if video.id in seen:
            continue
        seen.add(video.id)
        if video.is_live:
            dropped["live"] += 1
        elif video.duration_seconds <= 0:
            dropped["no length"] += 1
        elif longest_allowed is not None and video.duration_seconds > longest_allowed:
            dropped["too long"] += 1
        elif shortest_allowed is not None and video.duration_seconds < shortest_allowed:
            dropped["too short"] += 1
        elif constraints.language and video.language and video.language != constraints.language:
            dropped["language"] += 1
        else:
            eligible.append(video)

    chosen: list[Video] = []
    total = 0
    for video in eligible:  # relevance order; skip any video that would overshoot
        if total >= target:
            break
        if at_most_upper(total + video.duration_seconds):
            chosen.append(video)
            total += video.duration_seconds

    if not chosen:
        raise NoVideosFoundError(
            f"No videos matched '{constraints.topic}' with these settings"
            f" ({len(candidates)} found, {len(candidates) - len(eligible)} left out)."
        )

    notes: list[str] = []
    meets = at_least_lower(total) and at_most_upper(total)
    if not meets:
        notes.append(
            f"Only about {_minutes(total)} of the requested {_minutes(target)} was found:"
            " there were not enough matching videos."
        )
    for key, text in (
        ("live", "live or upcoming"),
        ("no length", "with no usable length"),
        ("too long", f"longer than {constraints.max_video_minutes} min"),
        ("too short", f"shorter than {constraints.min_video_minutes} min"),
        ("language", f"not in language '{constraints.language}'"),
    ):
        if dropped[key]:
            notes.append(f"Left out {dropped[key]} video(s) {text}.")
    unknown_language = sum(1 for v in chosen if not v.language) if constraints.language else 0
    if unknown_language:
        notes.append(f"{unknown_language} video(s) have no language information and were kept.")

    short_clips = sum(1 for v in chosen if v.duration_seconds < SHORT_CLIP_SECONDS)
    if short_clips and not constraints.min_video_minutes:
        notes.append(
            f"{short_clips} video(s) are under 3 minutes and may be Shorts or short clips."
            " Set min_video_minutes to 3 or more to leave them out."
        )

    return Selection(
        videos=chosen,
        total_seconds=total,
        target_seconds=target,
        longest_seconds=max(v.duration_seconds for v in chosen),
        meets_target=meets,
        notes=notes,
    )
