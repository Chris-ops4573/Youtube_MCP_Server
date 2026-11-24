# Quota

YouTube gives 10,000 units per day; it resets at midnight Pacific time (FR-7).
File: `src/ytmcp/quota.py`

| API method | Cost |
|---|---|
| search.list | 100 |
| videos.list | 1 |
| channels.list | 1 |
| playlistItems.list | 1 |
| playlists.insert | 50 |
| playlistItems.insert | 50 |

(Costs from SRS 2.5; re-check in Google's Quota Calculator, TBD-8.)

Planned calls for FR-3 and FR-4 (not in `quota.py` yet; add when they are built). These are the published costs, **not yet confirmed** in the Quota Calculator:

| API method | Cost | Used by |
|---|---|---|
| subscriptions.list | 1 | FR-3, FR-4 |
| playlists.list | 1 | FR-3, FR-4 |
| videoCategories.list | 1 | FR-4 (category names) |

Reading about 4,000 likes is about 80 `playlistItems.list` calls (50 per call): see [[ADR-010 Like dates from the likes playlist]]. A playlist of 10 videos costs 50 + 10 x 50 = 550 units (FR-5.6).

## Closing TBD-8 (a person has to do this)
Our count is only what this server believes it spent. To check it against Google:
1. In Google Cloud Console open the project, then APIs & Services, YouTube Data API v3, Quotas and System Limits. Note today's "Queries per day" usage.
2. Run one fresh `find_similar_channels` request (expected cost: 118 units) with an empty cache (`YTMCP_CACHE=off` or a new `YTMCP_CACHE_PATH`).
3. Look at the console again (it can lag a few minutes). The difference should be 118.
4. Write the result in [[Stage 2 Review]] and fix `COSTS` in `quota.py` if it is different.

## How it works
- A reserve of 500 units is kept back (assumed, TBD-6), so 9,500 are usable.
- Before a request runs, the service calls `provider.ensure_budget(estimate)`. If there isn't enough left it fails with `QUOTA_EXCEEDED` **before any API call** (FR-7.1).
- Every API call (including retries) is recorded.
- One `find_similar_videos` costs **102** units: videos.list (seed) + search.list + videos.list (candidates). SRS 5.1 limit is 210.
- One `find_similar_channels` costs **118** units (15 candidates): see [[Channels]].
- One `propose_playlist` costs **101** units (a search plus video details). `create_playlist` costs **50 + 50 per video** (550 for 10 videos), checked before anything is created and shared with the reads in one counter: see [[Playlist]].

## Saved across restarts
With the cache on, each call is also written to the `quota_usage` table (one row per Pacific-time day), so the count survives restarts. See [[Cache]]. With `YTMCP_CACHE=off` it is memory only.

Used by [[Providers]]. Part of [[Architecture]].
