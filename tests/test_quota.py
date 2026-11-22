from datetime import date

import pytest

from ytmcp.errors import QuotaExceededError
from ytmcp.quota import COSTS, QuotaTracker


def test_costs_match_srs():
    assert COSTS == {"search.list": 100, "videos.list": 1, "channels.list": 1}


def test_remaining_excludes_reserve():
    quota = QuotaTracker(daily_limit=1000, reserve=100)
    assert quota.remaining == 900


def test_record_adds_cost():
    quota = QuotaTracker(daily_limit=1000, reserve=0)
    quota.record("search.list")
    quota.record("videos.list")
    assert quota.spent == 101
    assert quota.remaining == 899


def test_ensure_budget_allows_exact_fit():
    QuotaTracker(daily_limit=1000, reserve=100).ensure_budget(900)


def test_ensure_budget_rejects_over_budget():
    quota = QuotaTracker(daily_limit=1000, reserve=100)
    with pytest.raises(QuotaExceededError) as exc:
        quota.ensure_budget(901)
    assert exc.value.code == "QUOTA_EXCEEDED"


def test_remaining_never_negative():
    quota = QuotaTracker(daily_limit=100, reserve=50)
    quota.record("search.list")
    assert quota.remaining == 0


def test_resets_on_a_new_day():
    day = [date(2026, 11, 22)]
    quota = QuotaTracker(daily_limit=1000, reserve=0, today=lambda: day[0])
    quota.record("search.list")
    day[0] = date(2026, 11, 23)
    assert quota.spent == 0
