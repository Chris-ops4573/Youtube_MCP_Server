# Traceability

Requirement -> code -> test -> note (SE-5). Fill in Issue/PR as you go.

| Req | Code | Test | Note | Issue/PR |
|---|---|---|---|---|
| FR-1.1 | `src/ytmcp/ids.py` | `tests/test_ids.py` | [[Errors]] | |
| FR-1.2 | `src/ytmcp/services/similar_videos.py`, `src/ytmcp/providers/youtube.py` | `tests/test_similar_videos.py`, `tests/test_youtube_provider.py` | [[Providers]] | |
| FR-1.3 | `src/ytmcp/similarity.py` | `tests/test_similarity.py` | [[Similarity]] | |
| FR-1.4 | `src/ytmcp/similarity.py` | `tests/test_similarity.py` | [[Similarity]] | |
| UI-1 | `src/ytmcp/tools.py` | `tests/test_similar_videos_tool.py` | [[Errors]] | |
| UI-3 | `src/ytmcp/tools.py`, `src/ytmcp/errors.py` | `tests/test_similar_videos_tool.py`, `tests/test_server.py` | [[Errors]] | |
| FR-2.1 (ID, @handle, URL) | `src/ytmcp/ids.py`, `providers/youtube.py` | `tests/test_ids.py`, `tests/test_youtube_provider.py` | [[Channels]] | |
| FR-2.2 (channel profile) | `src/ytmcp/services/similar_channels.py`, `src/ytmcp/similarity.py` | `tests/test_similar_channels.py`, `tests/test_channel_similarity.py` | [[Channels]] | |
| FR-2.3 (rank, exclude seed, hidden subs) | `src/ytmcp/similarity.py`, `src/ytmcp/tools.py` | `tests/test_channel_similarity.py`, `tests/test_similar_channels_tool.py` | [[Channels]] | |
| FR-6.1 (OAuth, PKCE, read-only default) | `src/ytmcp/auth/oauth.py`, `pkce.py`, `loopback.py`, `service.py` | `tests/test_oauth.py`, `test_pkce.py`, `test_loopback.py`, `test_auth_service.py` | [[Auth]] | |
| FR-6.2 (tokens only in keyring, re-auth on expiry) | `src/ytmcp/auth/tokens.py`, `service.py` | `tests/test_tokens.py`, `tests/test_auth_service.py` | [[Auth]] | |
| UI-4 (CLI: auth part only) | `src/ytmcp/cli.py` | `tests/test_cli.py` | [[Auth]] | |
| FR-5.1 (validate before any API call, field-level errors) | `src/ytmcp/playlist_planner.py`, `src/ytmcp/tools.py` | `tests/test_playlist_planner.py`, `tests/test_playlist_tools.py` | [[Playlist]] | |
| FR-5.2, FR-5.3 (drop live/long/short/wrong language, total within 10%, no duplicates, explain) | `src/ytmcp/playlist_planner.py` | `tests/test_playlist_planner.py` | [[ADR-014 How playlist videos are chosen]] | |
| FR-5.4 (proposal with ID, hash, 15 minute expiry) | `src/ytmcp/proposals.py`, `src/ytmcp/database.py` | `tests/test_proposals.py`, `tests/test_playlist_service.py` | [[Playlist]] | |
| FR-5.5 (confirmation enforced on the server) | `src/ytmcp/services/playlists.py`, `src/ytmcp/tools.py`, `src/ytmcp/server.py`, `src/ytmcp/cli.py` | `tests/test_playlist_server.py`, `tests/test_playlist_service.py`, `tests/test_cli.py` | [[ADR-013 Playlist creation needs a person's confirmation]] | |
| FR-5.6 (quota estimate, partial failures, signup required) | `src/ytmcp/services/playlists.py`, `src/ytmcp/providers/youtube.py` | `tests/test_playlist_service.py`, `tests/test_playlist_writer.py` | [[Playlist]] | |
| UI-2 (proposal shows videos, totals, longest, asks to confirm) | `src/ytmcp/tools.py` | `tests/test_playlist_tools.py` | [[Playlist]] | |
| FR-6.1 (write permission only when needed) | `src/ytmcp/cli.py`, `src/ytmcp/providers/youtube.py` | `tests/test_cli.py`, `tests/test_playlist_writer.py` | [[Auth]] | |
| SRS 5.2 (private, create only, no retries) | `src/ytmcp/providers/youtube.py` | `tests/test_playlist_writer.py` | [[Playlist]] | |
| FR-7.1 (quota pre-check) | `src/ytmcp/quota.py`, `services/similar_videos.py` | `tests/test_quota.py`, `tests/test_similar_videos.py` | [[Quota]] | |
| FR-7.2 (SQLite cache, batching) | `src/ytmcp/database.py`, `providers/caching.py` | `tests/test_database.py`, `tests/test_caching_provider.py` | [[Cache]] | |
| FR-7.1 (ledger survives restart) | `src/ytmcp/quota.py`, `src/ytmcp/database.py` | `tests/test_database.py` | [[Quota]] | |
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

Not started: FR-3, FR-4, SK-1. Partly done: UI-4 (the `auth` and `playlist confirm` commands; `quota status`, `serve` and `local-check` are not CLI commands yet). FR-5 is built and tested, including one real private playlist created and read back from YouTube; the terminal confirmation has not been tried in a real terminal.

Back to [[Requirements]].
