# Cache

SQLite cache for video and channel metadata, search results and the quota count (FR-7.2).
Files: `src/ytmcp/database.py` (the SQLite file, class Database: it also holds the quota count and the playlist proposals), `src/ytmcp/providers/caching.py` (the wrapper)

## How it fits
```
services -> CachingProvider -> YouTubeProvider -> YouTube API
                  |
             Database (SQLite)
```
`CachingProvider` has the same interface as every provider ([[Providers]]), so services and tools did not change.

## Behaviour
- `get_videos` / `get_channels`: return cached rows, fetch only the missing IDs.
- `search_videos`: a repeat of the same search (case and spacing ignored) is served from the cache, so it costs **0 units instead of 100**. Search results also fill the video cache.
- Channel searches are cached like video searches (kept apart, so the same words don't clash). Recent uploads are cached per channel, including "no uploads".
- A handle lookup always costs 1 unit but fills the channel cache.
- IDs YouTube doesn't return (private/deleted) are not cached, so they are asked for again.

## Expiry (YouTube API terms: refresh or delete stale data, SRS 6)
| Data | Max age |
|---|---|
| Video and channel metadata | 24 hours |
| Search results (video and channel) | 1 hour |
| Recent upload titles | 6 hours |

Expired rows are ignored, and deleted at startup (`prune`).

## Database
- Default `.cache/ytmcp.db` in the project (git-ignored). Change with `YTMCP_CACHE_PATH`; turn off with `YTMCP_CACHE=off` (see `.env.example`).
- WAL mode (SRS 2.4). All SQL uses parameters, never string-built values (SRS 5.3); a test checks this.
- Tables: `videos`, `channels`, `searches`, `uploads`, `quota_usage`, and `proposals` (playlist proposals, not a cache: they are kept even with `YTMCP_CACHE=off`, see [[Playlist]]).
- `quota_usage` keeps the daily unit count, so [[Quota]] survives restarts.
- No real user data is stored: only public video and channel metadata.

## Known limits
- The budget check (`ensure_budget`) assumes a full request cost (102 units) even if the answer is cached, so it can refuse a request that would have been free when the quota is almost gone.
- Single process only; two servers sharing one file is not tested.

Why: [[ADR-005 SQLite cache]]. Part of [[Architecture]].
