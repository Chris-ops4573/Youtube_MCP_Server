"""The one SQLite database file: cached video and channel data, searches and upload titles (FR-7.2),
the daily quota count (FR-7.1) and the playlist proposals (FR-5.4).

One database file in WAL mode (SRS 2.4). All SQL uses parameters, never
string formatting of values (SRS 5.3). Rows older than their max age are
treated as missing and pruned, so stale YouTube data is not kept (SRS 6, Legal).
"""

import json
import sqlite3
import threading
import time
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from ytmcp.models import Channel, Video

_SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    id TEXT PRIMARY KEY, data TEXT NOT NULL, fetched_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS channels (
    id TEXT PRIMARY KEY, data TEXT NOT NULL, fetched_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS searches (
    query TEXT NOT NULL, max_results INTEGER NOT NULL, video_ids TEXT NOT NULL,
    fetched_at REAL NOT NULL, PRIMARY KEY (query, max_results));
CREATE TABLE IF NOT EXISTS uploads (
    channel_id TEXT NOT NULL, max_results INTEGER NOT NULL, titles TEXT NOT NULL,
    fetched_at REAL NOT NULL, PRIMARY KEY (channel_id, max_results));
CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY, content_hash TEXT NOT NULL, title TEXT NOT NULL,
    description TEXT NOT NULL, videos TEXT NOT NULL, constraints TEXT NOT NULL,
    created_at REAL NOT NULL, expires_at REAL NOT NULL, status TEXT NOT NULL,
    playlist_id TEXT);
CREATE TABLE IF NOT EXISTS quota_usage (
    day TEXT PRIMARY KEY, units INTEGER NOT NULL);
"""


PROPOSAL_KEEP_SECONDS = 24 * 3600


def normalize_query(query: str) -> str:
    return " ".join(query.lower().split())


class Database:
    def __init__(self, path: str | Path = ":memory:", now: Callable[[], float] = time.time):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        self._now = now
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def journal_mode(self) -> str:
        return self._conn.execute("PRAGMA journal_mode").fetchone()[0]

    # --- videos and channels ------------------------------------------------

    def _get(self, table: str, ids: list[str], max_age: float) -> dict[str, dict]:
        if not ids:
            return {}
        marks = ",".join("?" * len(ids))
        sql = f"SELECT id, data FROM {table} WHERE id IN ({marks}) AND fetched_at >= ?"
        with self._lock:
            rows = self._conn.execute(sql, [*ids, self._now() - max_age]).fetchall()
        return {row_id: json.loads(data) for row_id, data in rows}

    def _put(self, table: str, items: list[tuple[str, dict]]) -> None:
        now = self._now()
        sql = f"INSERT OR REPLACE INTO {table} (id, data, fetched_at) VALUES (?, ?, ?)"
        with self._lock, self._conn:
            self._conn.executemany(sql, [(i, json.dumps(d), now) for i, d in items])

    def get_videos(self, ids: list[str], max_age: float) -> dict[str, Video]:
        return {i: Video(**d) for i, d in self._get("videos", ids, max_age).items()}

    def put_videos(self, videos: list[Video]) -> None:
        self._put("videos", [(v.id, asdict(v)) for v in videos])

    def get_channels(self, ids: list[str], max_age: float) -> dict[str, Channel]:
        return {i: Channel(**d) for i, d in self._get("channels", ids, max_age).items()}

    def put_channels(self, channels: list[Channel]) -> None:
        self._put("channels", [(c.id, asdict(c)) for c in channels])

    # --- searches -----------------------------------------------------------

    def get_search(self, query: str, max_results: int, max_age: float) -> list[str] | None:
        """Video IDs from a recent identical search, or None if not cached."""
        with self._lock:
            row = self._conn.execute(
                "SELECT video_ids FROM searches"
                " WHERE query = ? AND max_results = ? AND fetched_at >= ?",
                (normalize_query(query), max_results, self._now() - max_age),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def put_search(self, query: str, max_results: int, video_ids: list[str]) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO searches (query, max_results, video_ids, fetched_at)"
                " VALUES (?, ?, ?, ?)",
                (normalize_query(query), max_results, json.dumps(video_ids), self._now()),
            )

    # --- recent uploads (titles) ---------------------------------------------

    def get_uploads(self, channel_id: str, max_results: int, max_age: float) -> list[str] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT titles FROM uploads"
                " WHERE channel_id = ? AND max_results = ? AND fetched_at >= ?",
                (channel_id, max_results, self._now() - max_age),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def put_uploads(self, channel_id: str, max_results: int, titles: list[str]) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO uploads (channel_id, max_results, titles, fetched_at)"
                " VALUES (?, ?, ?, ?)",
                (channel_id, max_results, json.dumps(titles), self._now()),
            )

    # --- playlist proposals (FR-5.4) -------------------------------------------

    def put_proposal(self, row: dict) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO proposals (id, content_hash, title, description, videos, constraints,"
                " created_at, expires_at, status, playlist_id)"
                " VALUES (:id, :content_hash, :title, :description, :videos, :constraints,"
                " :created_at, :expires_at, :status, :playlist_id)",
                row,
            )

    def get_proposal(self, proposal_id: str) -> dict | None:
        with self._lock:
            cursor = self._conn.execute("SELECT * FROM proposals WHERE id = ?", (proposal_id,))
            row = cursor.fetchone()
            names = [d[0] for d in cursor.description]
        return dict(zip(names, row, strict=True)) if row else None

    def change_proposal_status(
        self,
        proposal_id: str,
        new_status: str,
        allowed_from: tuple[str, ...],
        not_expired_at: float | None = None,
        playlist_id: str | None = None,
    ) -> bool:
        """Move a proposal to a new status only if it is in one of `allowed_from` (and, when
        `not_expired_at` is given, has not expired). One atomic statement, so two callers
        can never both succeed. Returns whether this call made the change."""
        marks = ",".join("?" * len(allowed_from))
        sql = f"UPDATE proposals SET status = ?, playlist_id = COALESCE(?, playlist_id) WHERE id = ? AND status IN ({marks})"
        args: list = [new_status, playlist_id, proposal_id, *allowed_from]
        if not_expired_at is not None:
            sql += " AND expires_at > ?"
            args.append(not_expired_at)
        with self._lock, self._conn:
            return self._conn.execute(sql, args).rowcount == 1

    # --- quota ledger (used by QuotaTracker) --------------------------------

    def get_spent(self, day: str) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT units FROM quota_usage WHERE day = ?", (day,)
            ).fetchone()
        return row[0] if row else 0

    def add_spent(self, day: str, units: int) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO quota_usage (day, units) VALUES (?, ?)"
                " ON CONFLICT(day) DO UPDATE SET units = units + excluded.units",
                (day, units),
            )

    # --- cleanup ------------------------------------------------------------

    def prune(self, metadata_max_age: float, search_max_age: float) -> None:
        """Delete rows too old to be used."""
        now = self._now()
        with self._lock, self._conn:
            for table in ("videos", "channels"):
                self._conn.execute(
                    f"DELETE FROM {table} WHERE fetched_at < ?",
                    (now - metadata_max_age,),
                )
            self._conn.execute(
                "DELETE FROM searches WHERE fetched_at < ?", (now - search_max_age,)
            )
            self._conn.execute(
                "DELETE FROM uploads WHERE fetched_at < ?", (now - metadata_max_age,)
            )
            self._conn.execute(  # old proposals are no use to anyone
                "DELETE FROM proposals WHERE created_at < ?", (now - PROPOSAL_KEEP_SECONDS,)
            )
