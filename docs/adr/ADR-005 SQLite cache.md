# ADR-005 SQLite cache

Status: Accepted

## Context
FR-7.2 requires caching video and channel metadata in SQLite. The quota count
was only in memory and reset on every restart. A search costs 100 units, so
repeating one wastes 1% of the day's quota.

## Decision
- Add a `Cache` (SQLite, WAL mode, parameterised SQL) and a `CachingProvider` that wraps any provider with the same `VideoProvider` interface.
- Use Python's built-in `sqlite3`: no new dependency.
- Store the quota count in the same database (`quota_usage`).
- Expire metadata after 24 h and searches after 1 h, and delete expired rows at startup.
- Wrap only the live provider. The fixture provider is already local.

## Consequences
- Repeat lookups and searches cost 0 units; the quota count survives restarts.
- Cached data can be up to 24 h old (searches 1 h).
- The budget check is conservative for cached requests (see [[Cache]]).
- Max ages are fixed constants for now (TBD-6 area, tune later).

Cites: [[Cache]], [[Quota]], [[Providers]]
