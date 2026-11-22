# Providers

All YouTube access goes through `VideoProvider` (SE-6, SI-1).
File: `src/ytmcp/providers/base.py`

Methods:
- `get_videos(ids)` - missing/private/deleted IDs are left out
- `search_videos(query, max_results)`
- `get_channels(ids)`
- `ensure_budget(units)` - quota pre-check (FR-7.1); does nothing for fixtures

## Implementations
- `YouTubeProvider` (`providers/youtube.py`) - live YouTube Data API v3 with an API key.
  - `search_videos` gets IDs from `search.list`, then full metadata from `videos.list` (FR-1.2).
  - IDs are sent in batches of 50.
  - Language `en-US` is shortened to `en` so videos compare equal.
  - Retries at most 3 times (waits 1s, 2s, 4s) on network errors, 5xx and rate limits. `quotaExceeded` is never retried (SRS 3.4).
  - Every call is counted in [[Quota]].
  - The API key never appears in error messages.
- `CachingProvider` (`providers/caching.py`) - wraps another provider and serves repeats from SQLite. See [[Cache]].
- `FixtureProvider` (`providers/fixture.py`) - reads `tests/fixtures/*.json`; no API calls.

## Choosing a provider
Set in `.env` (copy `.env.example`):
- `YTMCP_PROVIDER=youtube` (default) - needs `YOUTUBE_API_KEY`. Without a key the server still starts and tools return `API_KEY_MISSING`.
- `YTMCP_PROVIDER=fixture` - sample data; used by `local-check`.

## Tests
`tests/fake_youtube.py` replaces the network and serves sample API responses from `tests/fixtures/youtube/` (TQ-5). These are hand-written in the API's format; swap in real recorded responses later.

Why: [[ADR-001 Provider interface]], [[ADR-004 Live provider with API key]], [[ADR-005 SQLite cache]]. Part of [[Architecture]].
