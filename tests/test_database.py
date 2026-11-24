from datetime import date

from ytmcp.database import Database, normalize_query
from ytmcp.models import Channel, Video
from ytmcp.quota import QuotaTracker

DAY = 24 * 3600


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


def video(vid="aaaaaaaaaaa", **kw):
    return Video(id=vid, title="T", description="D", channel_id="UC1", channel_title="C", **kw)


def test_video_roundtrip_keeps_all_fields():
    cache = Database()
    v = video(tags=["a", "b"], category_id="27", language="en", duration_seconds=90, is_live=True)
    cache.put_videos([v])
    assert cache.get_videos([v.id], DAY) == {v.id: v}


def test_channel_roundtrip_with_hidden_subscribers():
    cache = Database()
    c = Channel(id="UC1", title="T", description="D", keywords=["x"], subscriber_count=None)
    cache.put_channels([c])
    assert cache.get_channels(["UC1"], DAY) == {"UC1": c}


def test_unknown_and_empty_ids():
    cache = Database()
    assert cache.get_videos(["nope"], DAY) == {}
    assert cache.get_videos([], DAY) == {}


def test_expired_rows_are_ignored():
    clock = Clock()
    cache = Database(now=clock)
    cache.put_videos([video()])
    clock.t += DAY + 1
    assert cache.get_videos(["aaaaaaaaaaa"], DAY) == {}


def test_put_replaces_and_refreshes():
    clock = Clock()
    cache = Database(now=clock)
    cache.put_videos([video(duration_seconds=1)])
    clock.t += DAY - 10
    cache.put_videos([video(duration_seconds=2)])
    clock.t += 100  # old row would be expired, refreshed row is not
    assert cache.get_videos(["aaaaaaaaaaa"], DAY)["aaaaaaaaaaa"].duration_seconds == 2


def test_search_roundtrip_normalizes_query():
    cache = Database()
    cache.put_search("  Rust   Lifetimes ", 25, ["a", "b"])
    assert cache.get_search("rust lifetimes", 25, 3600) == ["a", "b"]
    assert cache.get_search("rust lifetimes", 10, 3600) is None  # different max_results
    assert normalize_query(" A  b ") == "a b"


def test_search_expires():
    clock = Clock()
    cache = Database(now=clock)
    cache.put_search("q", 25, ["a"])
    clock.t += 3601
    assert cache.get_search("q", 25, 3600) is None


def test_prune_deletes_old_rows_only():
    clock = Clock()
    cache = Database(now=clock)
    cache.put_videos([video("aaaaaaaaaaa")])
    cache.put_search("q", 25, ["a"])
    clock.t += 2 * DAY
    cache.put_videos([video("bbbbbbbbbbb")])
    cache.prune(DAY, 3600)
    assert set(cache.get_videos(["aaaaaaaaaaa", "bbbbbbbbbbb"], 10 * DAY)) == {"bbbbbbbbbbb"}
    assert cache.get_search("q", 25, 10 * DAY) is None


def test_values_are_parameterised_not_injected():
    cache = Database()
    evil = "x'; DROP TABLE videos; --"
    cache.put_search(evil, 1, ["a"])
    assert cache.get_search(evil, 1, 3600) == ["a"]
    cache.put_videos([video()])  # table still exists
    assert cache.get_videos(["aaaaaaaaaaa"], DAY)


def test_quota_ledger_adds_up():
    cache = Database()
    assert cache.get_spent("2026-11-22") == 0
    cache.add_spent("2026-11-22", 100)
    cache.add_spent("2026-11-22", 1)
    assert cache.get_spent("2026-11-22") == 101
    assert cache.get_spent("2026-11-23") == 0


def test_file_database_uses_wal_and_survives_reopen(tmp_path):
    path = tmp_path / "sub" / "cache.db"  # parent folder is created
    cache = Database(path)
    assert cache.journal_mode() == "wal"
    cache.put_videos([video()])
    cache.close()
    assert Database(path).get_videos(["aaaaaaaaaaa"], DAY)


def test_quota_survives_restart(tmp_path):
    day = lambda: date(2026, 11, 22)
    first = QuotaTracker(reserve=0, today=day, cache=Database(tmp_path / "c.db"))
    first.record("search.list")
    second = QuotaTracker(reserve=0, today=day, cache=Database(tmp_path / "c.db"))
    assert second.spent == 100


def test_quota_new_day_starts_at_zero_with_cache():
    days = [date(2026, 11, 22)]
    cache = Database()
    quota = QuotaTracker(reserve=0, today=lambda: days[0], cache=cache)
    quota.record("search.list")
    days[0] = date(2026, 11, 23)
    assert quota.spent == 0
    quota.record("videos.list")
    assert cache.get_spent("2026-11-22") == 100
    assert cache.get_spent("2026-11-23") == 1


def test_uploads_roundtrip_and_expiry():
    clock = Clock()
    cache = Database(now=clock)
    assert cache.get_uploads("UC1", 10, 3600) is None
    cache.put_uploads("UC1", 10, ["a", "b"])
    assert cache.get_uploads("UC1", 10, 3600) == ["a", "b"]
    assert cache.get_uploads("UC1", 5, 3600) is None  # different max_results
    clock.t += 3601
    assert cache.get_uploads("UC1", 10, 3600) is None


def test_empty_uploads_are_cached_too():
    cache = Database()
    cache.put_uploads("UC1", 10, [])
    assert cache.get_uploads("UC1", 10, 3600) == []


def test_prune_removes_old_uploads():
    clock = Clock()
    cache = Database(now=clock)
    cache.put_uploads("UC1", 10, ["a"])
    clock.t += 2 * DAY
    cache.prune(DAY, 3600)
    assert cache.get_uploads("UC1", 10, 10 * DAY) is None


def test_channel_fields_roundtrip():
    cache = Database()
    c = Channel(id="UC1", title="T", description="D", handle="@t", topics=["Technology"])
    cache.put_channels([c])
    assert cache.get_channels(["UC1"], DAY) == {"UC1": c}
