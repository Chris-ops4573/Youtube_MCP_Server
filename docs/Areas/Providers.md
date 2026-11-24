# Providers

All YouTube access goes through two interfaces in `src/ytmcp/providers/base.py` (SE-6, SI-1):
- **VideoProvider** reads public data with an API key.
- **AccountProvider** acts as the signed-in user: it reads the user's likes, subscriptions and playlists (FR-3, FR-4) and creates playlists ([[Playlist]]).

They are separate on purpose. VideoProvider needs only an API key. AccountProvider needs the user's login: reading uses the read-only scope and is retried like every other read; writing needs write permission, is never retried, and can only create, so the dangerous part stays small.

## VideoProvider methods (public data, API key)
- `get_videos(ids)` - missing/private/deleted IDs are left out
- `search_videos(query, max_results)`
- `get_channels(ids)`
- `get_channel_by_handle(handle)` - `channels.list` with `forHandle`; None if not found (FR-2.1)
- `search_channels(query, max_results)` - `search.list type=channel`, then full details (FR-2)
- `get_recent_uploads(channel_id, max_results)` - titles from the uploads playlist, 1 unit (FR-2.2)
- `category_names(region)` - video category ID to name, 1 unit (FR-4.1). It has a default that returns nothing, for providers that cannot look names up; the caching provider passes it straight through
- `ensure_budget(units)` - quota pre-check (FR-7.1); does nothing for fixtures

## AccountProvider methods (the user's account, login)
- `liked_videos(limit)` - the likes playlist, newest first, with the date each video was liked ([[ADR-010 Like dates from the likes playlist]]). Costs 1 unit for the channel lookup plus 1 per page of 50. Private and deleted videos are skipped
- `subscriptions(limit)` - the channels the user subscribes to, 50 per page, 1 unit per page
- `playlist_video_ids(max_playlists)` - IDs of the videos in the user's own playlists (the first 50 of each): 1 unit plus 1 per playlist
- `ensure_write_access()` - raises `WRITE_ACCESS_REQUIRED` unless the login has write permission (FR-6.1)
- `ensure_budget(units)` - quota pre-check before creating anything: 50 + 50 per video (FR-5.6)
- `create_playlist(title, description)` - creates a new **private** playlist and returns its ID
- `add_video(playlist_id, video_id)` - adds one video to a playlist this server created

## Implementations
- `YouTubeProvider` (`providers/youtube.py`) - live YouTube Data API v3 with an API key.
  - `search_videos` gets IDs from `search.list`, then full metadata from `videos.list` (FR-1.2).
  - IDs are sent in batches of 50.
  - Channels also carry `handle` (`customUrl`) and `topics` (Wikipedia category names, sorted because YouTube's order changes).
  - Language `en-US` is shortened to `en` so videos compare equal.
  - Retries at most 3 times (waits 1s, 2s, 4s) on network errors, 5xx and rate limits. `quotaExceeded` is never retried (SRS 3.4).
  - Every call is counted in [[Quota]].
  - The API key never appears in error messages.
- `YouTubeAccount` (also in `providers/youtube.py`, so all the YouTube HTTP code is in one file) - acts as the user with their Google login. It implements `AccountProvider`, not `VideoProvider`.
  - **Reads** use the read-only scope and the same retry function as `YouTubeProvider` (3 retries, `quotaExceeded` never retried, every page counted in [[Quota]]). Not being signed in passes through as `AUTH_REQUIRED`, and Google rejecting the token (401) also means sign in again.
  - **Writes** (FR-5) use the write scope, can only create, are never retried, and have a 15 second timeout (reads use 10). See [[Playlist]].
- `CachingProvider` (`providers/caching.py`) - wraps another provider and serves repeats from SQLite. See [[Cache]].
- `FixtureProvider` (`providers/fixture.py`) - reads `tests/fixtures/*.json`; no API calls.

## Choosing a provider
Set in `.env` (copy `.env.example`):
- `YTMCP_PROVIDER=youtube` (default) - needs `YOUTUBE_API_KEY`. Without a key the server still starts and tools return `API_KEY_MISSING`.
- `YTMCP_PROVIDER=fixture` - sample data; used by `local-check`.

## Tests
`tests/fake_youtube.py` replaces the network and serves sample API responses from `tests/fixtures/youtube/` (TQ-5). These are hand-written in the API's format; swap in real recorded responses later.

Why: [[ADR-001 Provider interface]], [[ADR-004 Live provider with API key]], [[ADR-005 SQLite cache]]. Part of [[Architecture]].
