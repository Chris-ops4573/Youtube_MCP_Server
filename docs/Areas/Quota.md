# Quota

YouTube gives 10,000 units per day; it resets at midnight Pacific time (FR-7).
File: `src/ytmcp/quota.py`

| API method | Cost |
|---|---|
| search.list | 100 |
| videos.list | 1 |
| channels.list | 1 |
| playlistItems.list | 1 |

(Costs from SRS 2.5; re-check in Google's Quota Calculator, TBD-8.)

## How it works
- A reserve of 500 units is kept back (assumed, TBD-6), so 9,500 are usable.
- Before a request runs, the service calls `provider.ensure_budget(estimate)`. If there isn't enough left it fails with `QUOTA_EXCEEDED` **before any API call** (FR-7.1).
- Every API call (including retries) is recorded.
- One `find_similar_videos` costs **102** units: videos.list (seed) + search.list + videos.list (candidates). SRS 5.1 limit is 210.
- One `find_similar_channels` costs **118** units (15 candidates): see [[Channels]].

## Saved across restarts
With the cache on, each call is also written to the `quota_usage` table (one row per Pacific-time day), so the count survives restarts. See [[Cache]]. With `YTMCP_CACHE=off` it is memory only.

Used by [[Providers]]. Part of [[Architecture]].
