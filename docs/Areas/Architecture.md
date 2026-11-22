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
| Services | `src/ytmcp/services/` | The feature logic (e.g. FR-1) |
| Providers | `src/ytmcp/providers/` | All YouTube access - see [[Providers]] |
| Similarity | `src/ytmcp/similarity.py` | Scoring - see [[Similarity]] |
| Models | `src/ytmcp/models.py` | `Video` and `Channel` data classes |

Decisions: [[ADR-001 Provider interface]], [[ADR-003 Structured errors]].
