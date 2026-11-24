"""Daily YouTube API quota tracking (FR-7.1).

Every API call has a unit cost. Before a workflow runs, `ensure_budget`
rejects it if it would go over what is left for the day. The count is kept
in memory, and also saved in the SQLite cache when one is given, so it survives restarts.
"""

from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

from ytmcp.cache import Cache
from ytmcp.errors import QuotaExceededError

# Unit cost per API method (SRS 2.5; re-check in Quota Calculator, TBD-8).
COSTS: dict[str, int] = {
    "search.list": 100,
    "videos.list": 1,
    "channels.list": 1,
    "playlistItems.list": 1,
    "playlists.insert": 50,
    "playlistItems.insert": 50,
}

MAX_IDS_PER_CALL = 50  # videos.list / channels.list accept up to 50 IDs

DAILY_LIMIT = 10_000
RESERVE = 500  # kept back as a safety margin (assumed, TBD-6)

# YouTube resets quota at midnight Pacific time.
_PACIFIC = ZoneInfo("America/Los_Angeles")


def _today_pacific() -> date:
    return datetime.now(_PACIFIC).date()


class QuotaTracker:
    def __init__(
        self,
        daily_limit: int = DAILY_LIMIT,
        reserve: int = RESERVE,
        today: Callable[[], date] = _today_pacific,
        cache: Cache | None = None,
    ):
        self.daily_limit = daily_limit
        self.reserve = reserve
        self._today = today
        self._cache = cache
        self._day = today()
        self._spent = cache.get_spent(self._day.isoformat()) if cache else 0

    def _roll_over(self) -> None:
        if self._today() != self._day:
            self._day = self._today()
            self._spent = self._cache.get_spent(self._day.isoformat()) if self._cache else 0

    @property
    def spent(self) -> int:
        self._roll_over()
        return self._spent

    @property
    def remaining(self) -> int:
        """Units still usable today, after the reserve."""
        return max(self.daily_limit - self.reserve - self.spent, 0)

    def ensure_budget(self, units: int) -> None:
        """Raise QuotaExceededError if `units` more would go over the budget."""
        if units > self.remaining:
            raise QuotaExceededError(
                f"This needs about {units} quota units but only {self.remaining} are left today."
            )

    def record(self, method: str) -> None:
        """Count one call to an API method, e.g. 'videos.list'."""
        self._roll_over()
        self._spent += COSTS[method]
        if self._cache:
            self._cache.add_spent(self._day.isoformat(), COSTS[method])
