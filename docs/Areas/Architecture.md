# Architecture

The whole design on one page, for the viva: [[Architecture Overview]]. Diagrams (components, classes, sequences, data): [[Design Components]], [[Design Classes]], [[Design Sequences]], [[Design Data]].

A request flows down these layers, and imports only point down ([[ADR-015 Simple module layout and one-way imports]]):

```
AI client -> server.py -> tools.py -> services/ -> providers/ (YouTube data)
                                            \-> similarity.py, playlist_planner.py (rules)
```

| Layer | Files | Job |
|---|---|---|
| Entry points | `src/ytmcp/server.py`, `src/ytmcp/cli.py` | server.py registers the MCP tools and asks the user to confirm a playlist. cli.py has the `python -m ytmcp` commands: `auth`, `playlist confirm`, `quota status`, `serve` and `local-check` |
| Wiring | `src/ytmcp/config.py` | Reads the settings and builds the objects for both entry points. It imports neither |
| Tools | `src/ytmcp/tools.py` | Checks arguments and formats results and errors for the AI client - see [[Errors]] |
| Services | `src/ytmcp/services/similar_videos.py`, `src/ytmcp/services/similar_channels.py`, `src/ytmcp/services/playlists.py` | The steps of each feature: FR-1, FR-2 ([[Channels]]) and FR-5 ([[Playlist]]) |
| Rules | `src/ytmcp/similarity.py`, `src/ytmcp/playlist_planner.py`, `src/ytmcp/proposals.py` | Pure scoring ([[Similarity]]), choosing playlist videos, and saved playlist proposals |
| Quota | `src/ytmcp/quota.py` | Daily API budget - see [[Quota]] |
| Providers | `src/ytmcp/providers/base.py`, `youtube.py`, `caching.py`, `fixture.py` | All YouTube access, through two interfaces - see [[Providers]] and [[Cache]] |
| Auth | `src/ytmcp/auth/` | Google sign-in and token storage - see [[Auth]] |
| Database | `src/ytmcp/database.py` | The one SQLite file: cached data, the quota count, the playlist proposals |
| Base | `src/ytmcp/models.py`, `src/ytmcp/errors.py`, `src/ytmcp/ids.py`, `src/ytmcp/durations.py` | Plain data, errors with codes, ID parsing, time parsing. They import nothing from above |

Every decision record is listed in the [[Index]]. The ones that shaped this layout: [[ADR-001 Provider interface]], [[ADR-003 Structured errors]], [[ADR-005 SQLite cache]], [[ADR-007 OAuth with PKCE and keyring]], [[ADR-013 Playlist creation needs a person's confirmation]], [[ADR-015 Simple module layout and one-way imports]].
