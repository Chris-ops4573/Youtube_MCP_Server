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
