# Traceability

Requirement -> code -> test -> note (SE-5). Fill in Issue/PR as you go.

| Req | Code | Test | Note | Issue/PR |
|---|---|---|---|---|
| FR-1.1 | `src/ytmcp/ids.py` | `tests/test_ids.py` | [[Errors]] | |
| FR-1.2 | `src/ytmcp/services/similar_videos.py` | `tests/test_similar_videos.py` | [[Providers]] | |
| FR-1.3 | `src/ytmcp/similarity.py` | `tests/test_similarity.py` | [[Similarity]] | |
| FR-1.4 | `src/ytmcp/similarity.py` | `tests/test_similarity.py` | [[Similarity]] | |
| UI-1 | `src/ytmcp/tools/similar_videos.py` | `tests/test_similar_videos_tool.py` | [[Errors]] | |
| UI-3 | `src/ytmcp/tools/similar_videos.py`, `src/ytmcp/errors.py` | `tests/test_similar_videos_tool.py`, `tests/test_server.py` | [[Errors]] | |
| SE-6 / SI-1 | `src/ytmcp/providers/` | `tests/test_fixture_provider.py` | [[Providers]] | |
| FR-5.2 (durations) | `src/ytmcp/durations.py` | `tests/test_durations.py` | | |

Not started: FR-2 to FR-7, UI-2, UI-4, SK-1 to SK-4.

Note: FR-1.2 "enrich with videos.list" will matter once the live provider exists; the fixture provider already returns full metadata.

Back to [[Requirements]].
