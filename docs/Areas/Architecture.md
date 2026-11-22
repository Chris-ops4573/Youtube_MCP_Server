# Architecture

A request flows through these layers:

```
AI client -> server.py -> tools/ -> services/ -> providers/ (YouTube data)
                                            \-> similarity.py (scoring)
```

| Layer | File | Job |
|---|---|---|
| Server | `src/ytmcp/server.py` | Registers MCP tools, nothing else |
| Tools | `src/ytmcp/tools/` | Formats results and errors for the AI client - see [[Errors]] |
| Services | `src/ytmcp/services/` | The feature logic (FR-1 videos, FR-2 [[Channels]]) |
| Providers | `src/ytmcp/providers/` | All YouTube access - see [[Providers]] |
| Channel similarity | `src/ytmcp/channel_similarity.py` | Channel scoring - see [[Channels]] |
| Cache | `src/ytmcp/cache.py`, `providers/caching.py` | SQLite cache - see [[Cache]] |
| Quota | `src/ytmcp/quota.py` | Daily API budget - see [[Quota]] |
| Similarity | `src/ytmcp/similarity.py` | Scoring - see [[Similarity]] |
| Models | `src/ytmcp/models.py` | `Video` and `Channel` data classes |

Decisions: [[ADR-001 Provider interface]], [[ADR-003 Structured errors]], [[ADR-004 Live provider with API key]], [[ADR-005 SQLite cache]], [[ADR-006 Channel candidates and uploads]].
