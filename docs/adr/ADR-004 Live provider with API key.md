# ADR-004 Live provider with API key

Status: Accepted

## Context
FR-1 only worked on fixture data. FR-1 and FR-2 read only public data, which
needs an API key, not OAuth. The quota must be checked before any call (FR-7.1).

## Decision
- Add `YouTubeProvider` using an API key from `.env` (`YOUTUBE_API_KEY`). OAuth (FR-6) comes later, for user data.
- Use Python's built-in `urllib` for HTTP: no new dependency, and tests pass in a fake `fetch` instead of mocking a library.
- Count quota in memory for now; save it in SQLite in the cache branch.
- Pick the provider with `YTMCP_PROVIDER` (`youtube` default, `fixture` for local checks).

## Consequences
- The server can answer real requests; one FR-1 call costs 102 units (about 90 a day).
- Quota count resets on restart until SQLite is added.
- Tests use sample responses, so a change in the real API format would not be caught; live tests on a schedule are planned (TQ-6).

Cites: [[Providers]], [[Quota]]
