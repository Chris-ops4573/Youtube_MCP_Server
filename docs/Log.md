# Log

Newest at the bottom. Format: `YYYY-MM-DD - who - what changed`

- 2026-11-22 - Chris - Created the brain (Index, Log, PARA folders, notes, ADRs) and AGENTS.md. See [[Index]].
- 2026-11-22 - Chris - Added local-check skill (SK-2) and 80% coverage gate in CI. See [[Testing]].
- 2026-11-22 - Chris - Added live YouTubeProvider (API key from .env), quota pre-check and new error codes. See [[Providers]], [[Quota]], [[ADR-004 Live provider with API key]].
- 2026-11-22 - Chris - Added SQLite cache (CachingProvider) and saved the quota count across restarts. See [[Cache]], [[ADR-005 SQLite cache]].
- 2026-11-22 - Chris - Added FR-2 find_similar_channels (handle/ID/URL input, uploads-based profiles, channel search cache). See [[Channels]], [[ADR-006 Channel candidates and uploads]].
- 2026-11-22 - Chris - Grouped requirements.txt (runtime / dev), added version limits and tzdata for Windows time zones.
- 2026-11-23 - Chris - Added OAuth sign-in core (PKCE, loopback redirect, keyring storage) and `auth login|status|logout` commands. See [[Auth]], [[ADR-007 OAuth with PKCE and keyring]].
- 2026-11-23 - Chris - Stage 2 docs: four design notes (components, classes, sequences, data), ADR-008 to ADR-011 (settles TBD-1, 3, 4, 9), Development Plan and Stage 2 Review. See [[Stage 2 Review]], [[Design Components]].
- 2026-11-23 - Chris - Added brain skills (brain-query, brain-ingest, brain-refine), scripts/brain.py with check/search/new, evals for every skill, and a CI step that validates notes and skills. See [[Brain]], [[Skill Evaluations]], [[ADR-012 Brain checks in a standard library script]].
- 2026-11-23 - Chris - Added FR-5 playlist creation: propose_playlist and create_playlist, proposals with a 15 minute expiry, confirmation by the user through the client or in a terminal, write permission via auth login --write. See [[Playlist]], [[ADR-013 Playlist creation needs a person's confirmation]], [[ADR-014 How playlist videos are chosen]].
- 2026-11-23 - Chris - Added min_video_minutes to propose_playlist and a warning when short clips are chosen without it. Tested for real. See [[Playlist]], [[ADR-014 How playlist videos are chosen]].
