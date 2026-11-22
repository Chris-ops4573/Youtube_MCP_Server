# Providers

All YouTube access goes through `VideoProvider` (SE-6, SI-1).
File: `src/ytmcp/providers/base.py`

Methods:
- `get_videos(ids)` - missing/private/deleted IDs are left out
- `search_videos(query, max_results)`
- `get_channels(ids)`

Implementations:
- `FixtureProvider` - reads `tests/fixtures/*.json`; used by tests and by the server for now.
- Live provider (YouTube Data API v3) - not built yet.

Why: [[ADR-001 Provider interface]]. Part of [[Architecture]].
