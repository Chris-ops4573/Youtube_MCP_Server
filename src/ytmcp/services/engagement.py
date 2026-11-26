"""Analyse the signed-in user's likes, subscriptions and playlists (FR-4).

Plain statistics from the three sources the API gives us: top channels and categories, a monthly
trend, duration preferences and a comparison of two periods. YouTube does not share watch
history, so it is never used (FR-4.4). The functions at the top are pure (no API calls);
`analyze_engagement` at the bottom does the reading.
"""

import math
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ytmcp.errors import (
    AccountUnavailableError,
    InvalidArgumentError,
    NotEnoughHistoryError,
)
from ytmcp.models import LikedVideo, Video
from ytmcp.providers.base import AccountProvider, VideoProvider
from ytmcp.quota import (
    COSTS,
    LIKES_CAP,
    MAX_IDS_PER_CALL,
    PAGE_SIZE,
    PLAYLISTS_CAP,
    SUBSCRIPTIONS_CAP,
)

SOURCES = ("likes", "subscriptions", "playlists")
MIN_PERIOD_MONTHS = 1
MAX_PERIOD_MONTHS = 60
DEFAULT_PERIOD_MONTHS = 12
TOP_N = 10  # entries in a top list
COMPARE_TOP_N = 5  # entries in a top list inside a comparison

DATE_FIELD = "date liked (snippet.publishedAt of the likes playlist)"  # FR-4.2
WATCH_HISTORY_NOTE = (  # FR-4.4
    "Based on your likes, subscriptions and playlists only. YouTube does not share watch history."
)
# (label, upper limit in seconds). A video belongs to the first bucket it is shorter than.
BUCKETS = (("under 5 min", 300), ("5 to 20 min", 1200), ("20 to 60 min", 3600))
LONGEST_BUCKET = "over 60 min"  # everything longer than the last limit


@dataclass(frozen=True)
class Arguments:
    sources: tuple[str, ...]  # in a fixed order, no duplicates
    period_months: int
    compare: bool


def _is_whole_number(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validate_arguments(sources: object = None, period_months: object = DEFAULT_PERIOD_MONTHS, compare: object = False) -> Arguments:
    """Check every argument before any API call, and report all problems together (FR-4)."""
    fields: dict[str, str] = {}

    chosen: tuple[str, ...] = SOURCES
    if sources is not None:
        if not isinstance(sources, list) or not sources or not all(isinstance(s, str) for s in sources):
            fields["sources"] = "must be a list with some of: likes, subscriptions, playlists"
        else:
            unknown = sorted({s for s in sources if s not in SOURCES})
            if unknown:
                fields["sources"] = f"unknown: {', '.join(unknown)}. Use likes, subscriptions or playlists"
            else:
                chosen = tuple(s for s in SOURCES if s in sources)

    months = DEFAULT_PERIOD_MONTHS
    if not _is_whole_number(period_months) or not MIN_PERIOD_MONTHS <= period_months <= MAX_PERIOD_MONTHS:  # type: ignore[operator]
        fields["period_months"] = (
            f"must be a whole number of months from {MIN_PERIOD_MONTHS} to {MAX_PERIOD_MONTHS}"
        )
    else:
        months = period_months  # type: ignore[assignment]

    if not isinstance(compare, bool):
        fields["compare"] = "must be true or false"
    elif compare and "likes" not in chosen:
        fields["compare"] = "needs 'likes' in sources: only likes have a date"

    if fields:
        raise InvalidArgumentError("Some arguments are not valid: " + ", ".join(sorted(fields)) + ".", fields)
    return Arguments(chosen, months, bool(compare))


def estimate_cost(sources: tuple[str, ...] = SOURCES) -> int:
    """Quota units for one FR-4 request: 47 with all three sources and the default caps."""
    units = 0
    detail_batches = 0  # videos.list batches of 50
    if "likes" in sources:
        units += COSTS["channels.list"] + math.ceil(LIKES_CAP / PAGE_SIZE) * COSTS["playlistItems.list"]
        detail_batches += math.ceil(LIKES_CAP / MAX_IDS_PER_CALL)
    if "subscriptions" in sources:
        units += math.ceil(SUBSCRIPTIONS_CAP / PAGE_SIZE) * COSTS["subscriptions.list"]
    if "playlists" in sources:
        units += COSTS["playlists.list"] + PLAYLISTS_CAP * COSTS["playlistItems.list"]
        detail_batches += math.ceil(PLAYLISTS_CAP * PAGE_SIZE / MAX_IDS_PER_CALL)
    if detail_batches:
        units += detail_batches * COSTS["videos.list"] + COSTS["videoCategories.list"]
    return units


# --- pure statistics ---------------------------------------------------------------------------------


def top_counts(
    keys: list[str],
    n: int = TOP_N,
    names: dict[str, str] | None = None,
    extra: Callable[[str], dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """The `n` most common keys with their count and share (FR-4.1). Ties are ordered by name."""
    names = names or {}
    counts = Counter(keys)
    ranked = sorted(counts.items(), key=lambda item: (-item[1], names.get(item[0], item[0]), item[0]))
    entries = []
    for key, count in ranked[:n]:
        entry: dict[str, Any] = {
            "name": names.get(key, key),
            "count": count,
            "share": round(count / len(keys), 3),
        }
        if extra:
            entry.update(extra(key))
        entries.append(entry)
    return entries


def _month_start(moment: datetime) -> datetime:
    return datetime(moment.year, moment.month, 1, tzinfo=UTC)


def _shift_month(start: datetime, delta: int) -> datetime:
    """The first day of the month `delta` months after (or before, if negative) `start`."""
    index = start.year * 12 + (start.month - 1) + delta
    return datetime(index // 12, index % 12 + 1, 1, tzinfo=UTC)


def _parse(liked_at: str) -> datetime | None:
    try:
        return datetime.fromisoformat(liked_at).astimezone(UTC)
    except ValueError:  # empty or unreadable date
        return None


def monthly_trend(liked: list[LikedVideo], months: int, now: datetime) -> list[dict[str, Any]]:
    """Likes per UTC month for the last `months` months, oldest first, with empty months as 0
    (FR-4.2). Likes outside that range are ignored."""
    first = _shift_month(_month_start(now), -(months - 1))
    stop = _shift_month(_month_start(now), 1)
    counts: Counter[str] = Counter()
    for item in liked:
        when = _parse(item.liked_at)
        if when and first <= when < stop:
            counts[when.strftime("%Y-%m")] += 1
    labels = [_shift_month(first, i).strftime("%Y-%m") for i in range(months)]
    return [{"month": label, "likes": counts[label]} for label in labels]


def _bucket(seconds: int) -> str:
    for label, limit in BUCKETS:
        if seconds < limit:
            return label
    return LONGEST_BUCKET


def duration_buckets(videos: list[Video]) -> list[dict[str, Any]]:
    """How the videos split by length (FR-4.3)."""
    counts = Counter(_bucket(v.duration_seconds) for v in videos)
    total = len(videos)
    return [
        {"bucket": label, "count": counts[label], "share": round(counts[label] / total, 3) if total else 0.0}
        for label in [*(name for name, _ in BUCKETS), LONGEST_BUCKET]
    ]


def _top_channels(videos: list[Video], n: int) -> list[dict[str, Any]]:
    names = {v.channel_id: v.channel_title for v in videos}
    return top_counts([v.channel_id for v in videos], n, names)


def _top_categories(videos: list[Video], category_names: dict[str, str], n: int) -> list[dict[str, Any]]:
    keys = [v.category_id or "unknown" for v in videos]
    names = {key: ("Unknown" if key == "unknown" else category_names.get(key, f"Category {key}")) for key in set(keys)}
    return top_counts(keys, n, names)


def compare_periods(
    liked: list[LikedVideo],
    details: dict[str, Video],
    months: int,
    now: datetime,
    category_names: dict[str, str],
) -> dict[str, Any]:
    """The last `months` months next to the `months` before them, using only liked videos
    inside each window (FR-4.3)."""
    this_month = _month_start(now)
    current_start = _shift_month(this_month, -(months - 1))
    previous_start = _shift_month(current_start, -months)
    stop = _shift_month(this_month, 1)

    def window(start: datetime, end: datetime) -> dict[str, Any]:
        ids = [i.video_id for i in liked if (when := _parse(i.liked_at)) and start <= when < end]
        videos = [details[i] for i in ids if i in details]
        return {
            "from": start.strftime("%Y-%m"),
            "to": _shift_month(end, -1).strftime("%Y-%m"),
            "likes": len(ids),
            "top_channels": _top_channels(videos, COMPARE_TOP_N),
            "top_categories": _top_categories(videos, category_names, COMPARE_TOP_N),
            "duration_preferences": duration_buckets(videos),
        }

    return {"current": window(current_start, stop), "previous": window(previous_start, current_start)}


# --- the analysis -------------------------------------------------------------------------------------


def analyze_engagement(
    provider: VideoProvider,
    account: AccountProvider | None,
    arguments: Arguments,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Read the chosen sources and return the statistics. Raises AccountUnavailableError without
    an account (fixture mode), NotEnoughHistoryError when the sources are empty,
    AuthRequiredError if not signed in, and QuotaExceededError (before any API call)."""
    if account is None:
        raise AccountUnavailableError("Engagement analysis needs your own YouTube data.")
    now = now or datetime.now(UTC)
    sources = arguments.sources
    provider.ensure_budget(estimate_cost(sources))  # before any API call (FR-7.1)

    liked = account.liked_videos(LIKES_CAP) if "likes" in sources else []
    subscriptions = account.subscriptions(SUBSCRIPTIONS_CAP) if "subscriptions" in sources else []
    playlist_ids = account.playlist_video_ids(PLAYLISTS_CAP) if "playlists" in sources else set()
    if not liked and not subscriptions and not playlist_ids:
        raise NotEnoughHistoryError("There is nothing in the chosen sources to analyse.")

    # a video that is both liked and in a playlist is analysed once
    wanted = list(dict.fromkeys([item.video_id for item in liked] + sorted(playlist_ids)))
    details = {v.id: v for v in provider.get_videos(wanted)} if wanted else {}
    videos = list(details.values())
    category_names = provider.category_names() if videos else {}

    # every liked video, saved video and subscription counts once for its channel
    names = {v.channel_id: v.channel_title for v in videos}
    names.update({s.channel_id: s.title for s in subscriptions if s.channel_id not in names})
    subscribed = {s.channel_id for s in subscriptions}
    channel_keys = [v.channel_id for v in videos] + [s.channel_id for s in subscriptions]
    flag_subscribed = (lambda key: {"subscribed": key in subscribed}) if "subscriptions" in sources else None

    report: dict[str, Any] = {
        "sources": list(sources),
        "period_months": arguments.period_months,
        "totals": {
            "likes": len(liked),
            "subscriptions": len(subscriptions),
            "playlist_videos": len(playlist_ids),
        },
        "top_channels": top_counts(channel_keys, TOP_N, names, flag_subscribed),
        "top_categories": _top_categories(videos, category_names, TOP_N),
        "duration_preferences": duration_buckets(videos),
    }
    caveats: list[str] = []
    if "likes" in sources:
        report["monthly_trend"] = {
            "date_field": DATE_FIELD,
            "months": monthly_trend(liked, arguments.period_months, now),
        }
        if arguments.compare:
            report["comparison"] = compare_periods(liked, details, arguments.period_months, now, category_names)
        caveats += _likes_caveat(liked, arguments, now)
    if len(subscriptions) >= SUBSCRIPTIONS_CAP:
        caveats.append(f"Only the first {SUBSCRIPTIONS_CAP} subscriptions were read.")
    report["caveats"] = caveats
    report["note"] = WATCH_HISTORY_NOTE
    return report


def _likes_caveat(liked: list[LikedVideo], arguments: Arguments, now: datetime) -> list[str]:
    """If the like cap cut off the period, say so instead of showing empty months as real."""
    if len(liked) < LIKES_CAP:
        return []
    dates = [d for d in (_parse(item.liked_at) for item in liked) if d]
    if not dates:
        return []
    oldest = min(dates)
    months_needed = arguments.period_months * (2 if arguments.compare else 1)
    earliest = _shift_month(_month_start(now), -(months_needed - 1))
    if oldest <= earliest:
        return []
    return [f"Only your newest {LIKES_CAP} likes were read (back to {oldest:%Y-%m-%d}), so earlier months are incomplete."]
