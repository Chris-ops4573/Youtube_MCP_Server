# Traceability

Requirement -> code -> test -> note (SE-5). Fill in Issue/PR as you go.

| Req | Code | Test | Note | Issue/PR |
|---|---|---|---|---|
| FR-1.1 | `src/ytmcp/ids.py` | `tests/test_ids.py` | [[Errors]] | |
| FR-1.2 | `src/ytmcp/services/similar_videos.py`, `src/ytmcp/providers/youtube.py` | `tests/test_similar_videos.py`, `tests/test_youtube_provider.py` | [[Providers]] | |
| FR-1.3 | `src/ytmcp/similarity.py` | `tests/test_similarity.py` | [[Similarity]] | |
| FR-1.4 | `src/ytmcp/similarity.py` | `tests/test_similarity.py` | [[Similarity]] | |
| UI-1 | `src/ytmcp/tools/similar_videos.py` | `tests/test_similar_videos_tool.py` | [[Errors]] | |
| UI-3 | `src/ytmcp/tools/similar_videos.py`, `src/ytmcp/errors.py` | `tests/test_similar_videos_tool.py`, `tests/test_server.py` | [[Errors]] | |
| FR-7.1 (quota pre-check) | `src/ytmcp/quota.py`, `services/similar_videos.py` | `tests/test_quota.py`, `tests/test_similar_videos.py` | [[Quota]] | |
| SRS 3.4 (retries, no key in errors) | `src/ytmcp/providers/youtube.py` | `tests/test_youtube_provider.py` | [[Providers]] | |
| SE-6 / SI-1 | `src/ytmcp/providers/` | `tests/test_fixture_provider.py` | [[Providers]] | |
| SK-2 | `scripts/local_check.py`, `.claude/skills/local-check/` | run `python scripts/local_check.py` | [[Testing]] | |
| SRS 5.4 (coverage >= 80%) | `.github/workflows/ci.yml` | CI pytest step | [[Testing]] | |
| FR-5.2 (durations) | `src/ytmcp/durations.py` | `tests/test_durations.py` | | |

Not started: FR-2 to FR-6, FR-7.2 (cache), UI-2, UI-4, SK-1, SK-3.

Back to [[Requirements]].
