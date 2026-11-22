# Requirements

Short list of SRS IDs. Full text: `docs/requirements/` (SRS .docx).
Progress is tracked in [[Traceability]].

## Functional
- FR-1 Similar videos (High)
  - FR-1.1 accept ID or watch/youtu.be/shorts/embed URL
  - FR-1.2 find candidates with search.list, enrich with videos.list
  - FR-1.3 score with TF-IDF + tags, category, language, duration
  - FR-1.4 top N (default 10), no seed, score breakdown, low-confidence flag
- FR-2 Similar channels (High)
- FR-3 Recommendations from likes, subscriptions, playlists (High)
- FR-4 Engagement analysis (Medium)
- FR-5 Playlist creation, only after confirmation (High)
- FR-6 OAuth with PKCE, tokens in OS keyring (High)
- FR-7 Quota tracking and SQLite cache (High)

## Interfaces
- UI-1 results show rank, title, channel, duration, score, URL
- UI-2 playlist proposal shows videos and totals, asks to confirm
- UI-3 errors: code, message, remediation; no stack traces or secrets
- UI-4 CLI: auth, quota status, serve, local-check
- SI-1 all YouTube calls via VideoProvider; FixtureProvider for CI

## Skills
- SK-1 video-to-playlist, SK-2 local-check, SK-3 brain-ingest/refine/query, SK-4 every skill has SKILL.md and cites a note

## Process
- SE-1 to SE-7 SRS, design docs, ADRs citing notes, plan, traceability, provider interface, docs
- SB-1 to SB-6 PARA vault with index and log, wikilinks, stage reviews, AGENTS.md, brain changes via PRs
- TQ-1 to TQ-8 unit/integration/e2e/negative tests, fixtures in CI, coverage >= 80%

## Open (TBD)
- TBD-1 language (assumed Python 3.11+), TBD-2 similarity weights, TBD-3 like dates,
  TBD-4 HTTP transport, TBD-5 non-English tokenising, TBD-6 quota reserve / max playlist,
  TBD-7 team details, TBD-8 re-check quota costs, TBD-9 transcripts for summaries

See also [[Glossary]].
