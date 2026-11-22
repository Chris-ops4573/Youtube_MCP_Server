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
| FR-2.1 (ID, @handle, URL) | `src/ytmcp/ids.py`, `providers/youtube.py` | `tests/test_ids.py`, `tests/test_youtube_provider.py` | [[Channels]] | |
| FR-2.2 (channel profile) | `src/ytmcp/services/similar_channels.py`, `channel_similarity.py` | `tests/test_similar_channels.py`, `tests/test_channel_similarity.py` | [[Channels]] | |
| FR-2.3 (rank, exclude seed, hidden subs) | `src/ytmcp/channel_similarity.py`, `tools/similar_channels.py` | `tests/test_channel_similarity.py`, `tests/test_similar_channels_tool.py` | [[Channels]] | |
| FR-6.1 (OAuth, PKCE, read-only default) | `src/ytmcp/auth/oauth.py`, `pkce.py`, `loopback.py`, `service.py` | `tests/test_oauth.py`, `test_pkce.py`, `test_loopback.py`, `test_auth_service.py` | [[Auth]] | |
| FR-6.2 (tokens only in keyring, re-auth on expiry) | `src/ytmcp/auth/tokens.py`, `service.py` | `tests/test_tokens.py`, `tests/test_auth_service.py` | [[Auth]] | |
| UI-4 (CLI: auth part only) | `src/ytmcp/cli.py` | `tests/test_cli.py` | [[Auth]] | |
| FR-7.1 (quota pre-check) | `src/ytmcp/quota.py`, `services/similar_videos.py` | `tests/test_quota.py`, `tests/test_similar_videos.py` | [[Quota]] | |
| FR-7.2 (SQLite cache, batching) | `src/ytmcp/cache.py`, `providers/caching.py` | `tests/test_cache.py`, `tests/test_caching_provider.py` | [[Cache]] | |
| FR-7.1 (ledger survives restart) | `src/ytmcp/quota.py`, `src/ytmcp/cache.py` | `tests/test_cache.py` | [[Quota]] | |
| SRS 3.4 (retries, no key in errors) | `src/ytmcp/providers/youtube.py` | `tests/test_youtube_provider.py` | [[Providers]] | |
| SK-3 (brain-ingest, brain-refine, brain-query) | `.claude/skills/brain-*/`, `scripts/brain.py` | `tests/test_brain.py` | [[Brain]] | |
| SK-4 (valid SKILL.md, cites a note), TQ-7 (evals) | `scripts/brain.py check`, `.claude/skills/*/evals.md` | `tests/test_brain.py` | [[Skill Evaluations]] | |
| CI validates notes and skills (SRS section 6) | `.github/workflows/ci.yml` | CI step `Validate brain notes and skills` | [[Brain]] | |
| SE-2 (design docs, UML, ER) | docs only | n/a | [[Design Components]], [[Design Classes]], [[Design Sequences]], [[Design Data]] | |
| SE-3 (ADRs cite notes) | `docs/adr/` | n/a | [[Index]] (ADR-001 to ADR-011) | |
| SE-4 (development plan) | docs only | n/a | [[Development Plan]] | |
| SE-6 / SI-1 | `src/ytmcp/providers/` | `tests/test_fixture_provider.py` | [[Providers]] | |
| SK-2 | `scripts/local_check.py`, `.claude/skills/local-check/` | run `python scripts/local_check.py` | [[Testing]] | |
| SRS 5.4 (coverage >= 80%) | `.github/workflows/ci.yml` | CI pytest step | [[Testing]] | |
| FR-5.2 (durations) | `src/ytmcp/durations.py` | `tests/test_durations.py` | | |

Not started: FR-3 to FR-5, UI-2, SK-1. Partly done: UI-4 (only the `auth` commands).

Back to [[Requirements]].
