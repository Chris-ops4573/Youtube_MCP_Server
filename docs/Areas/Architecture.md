# Architecture

Diagrams (components, classes, sequences, data): [[Design Components]], [[Design Classes]], [[Design Sequences]], [[Design Data]].

A request flows through these layers:

```
AI client -> server.py -> tools.py -> services/ -> providers/ (YouTube data)
                                            \-> similarity.py (scoring)
```

| Layer | File | Job |
|---|---|---|
| Server | `src/ytmcp/server.py` | Registers the MCP tools and asks the user to confirm a playlist |
| Config | `src/ytmcp/config.py` | Reads the settings and builds the objects for server.py and cli.py (the wiring). It imports neither |
| Tools | `src/ytmcp/tools.py` | Formats results and errors for the AI client - see [[Errors]] |
| Services | `src/ytmcp/services/` | The feature logic (FR-1 videos, FR-2 [[Channels]]) |
| Providers | `src/ytmcp/providers/` | All YouTube access - see [[Providers]] |
| Auth | `src/ytmcp/auth/` | Google sign-in and token storage - see [[Auth]] |
| CLI | `src/ytmcp/cli.py` | `python -m ytmcp auth ...` commands |
| Cache | `src/ytmcp/cache.py`, `providers/caching.py` | SQLite cache - see [[Cache]] |
| Quota | `src/ytmcp/quota.py` | Daily API budget - see [[Quota]] |
| Similarity | `src/ytmcp/similarity.py` | Video and channel scoring - see [[Similarity]] and [[Channels]] |
| Models | `src/ytmcp/models.py` | `Video` and `Channel` data classes |

Decisions: [[ADR-001 Provider interface]], [[ADR-003 Structured errors]], [[ADR-004 Live provider with API key]], [[ADR-005 SQLite cache]], [[ADR-006 Channel candidates and uploads]], [[ADR-007 OAuth with PKCE and keyring]].
