# Design Data

Design document 4 of 4 (SE-2). The ER diagram of the local database, and where every kind of data lives.
Back to [[Design Components]]. How the cache behaves: [[Cache]].

## Database (SQLite, WAL mode)
File `.cache/ytmcp.db`, created by `src/ytmcp/database.py`. Metadata is stored as JSON text in `data`. The links between tables are logical (an ID inside JSON), not SQL foreign keys.

```mermaid
erDiagram
  videos {
    text id PK
    text data
    real fetched_at
  }
  channels {
    text id PK
    text data
    real fetched_at
  }
  searches {
    text query PK
    int max_results PK
    text video_ids
    real fetched_at
  }
  uploads {
    text channel_id PK
    int max_results PK
    text titles
    real fetched_at
  }
  quota_usage {
    text day PK
    int units
  }
  searches }o--o{ videos : "lists IDs of"
  uploads }o--|| channels : "recent titles of"
```

Notes:
- FR-2 finds candidate channels through a video search, so it uses the same `searches` rows as FR-1.
- `quota_usage` has one row per Pacific-time day. It is the only table that is never expired ([[Quota]]).
- `prune` runs at startup and deletes rows older than their limit.

## Playlist proposals (FR-5.4)
The same database file also holds the saved proposals, so the server and the terminal command (`python -m ytmcp playlist confirm`) see the same data. This is true even when the cache is switched off. See [[Playlist]].

```mermaid
erDiagram
  proposals {
    text id PK
    text content_hash
    text title
    text description
    text videos
    text constraints
    real created_at
    real expires_at
    text status
    text playlist_id
  }
```

`status` is one of `proposed`, `confirmed`, `creating`, `created`, `partial`, `failed`, `declined`. Changes happen in single database statements that only succeed from the right status, so two callers can never both create from one proposal.

## How long data is kept
YouTube's API terms require refreshing or deleting stale data (SRS section 6).

| Data | Kept for |
|---|---|
| Video and channel metadata | 24 hours |
| Video and channel searches | 1 hour |
| Recent upload titles | 6 hours |
| Quota count | per day, small |
| Proposals | usable for 15 minutes, deleted after a day |

## Where each kind of data lives
| Data | Where | Why there |
|---|---|---|
| YouTube API key | `.env` (git-ignored) | read by the server at start |
| Google OAuth client ID and secret | `.env` (git-ignored) | identifies this app to Google |
| Google login tokens | **OS keyring only** | SRS 5.3: never in files, database, logs |
| Video, channel, search data, quota count | SQLite file | cache and ledger (FR-7) |
| Sample data for tests | `tests/fixtures/` | no live calls, no real user data (TQ-5) |

No real user data (likes, subscriptions, existing playlists) is stored anywhere yet. A proposal holds only public video titles and the title the user asked for. When FR-3 and FR-4 arrive, that data must stay in memory or in the cache with the same expiry rules, and never in fixtures or logs.
