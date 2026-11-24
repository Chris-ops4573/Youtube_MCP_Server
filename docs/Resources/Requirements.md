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
- SI-1 all YouTube calls via VideoProvider; FixtureProvider for CI (writes: see [[Playlist]])

## Skills
- SK-1 video-to-playlist, SK-2 local-check, SK-3 brain-ingest/refine/query, SK-4 every skill has SKILL.md and cites a note

## Process
- SE-1 to SE-7 SRS, design docs, ADRs citing notes, plan, traceability, provider interface, docs
- SB-1 to SB-6 PARA vault with index and log, wikilinks, stage reviews, AGENTS.md, brain changes via PRs
- TQ-1 to TQ-8 unit/integration/e2e/negative tests, fixtures in CI, coverage >= 80%

## TBD items (open questions in the SRS)
| TBD | Question | Status |
|---|---|---|
| TBD-1 | Language and libraries | Decided: Python 3.11+, [[ADR-008 Python 3.11 and libraries]] |
| TBD-2 | Similarity weights | Open (Stage 3). Starting guesses, see [[Similarity]] and [[Channels]] |
| TBD-3 | Like dates for FR-4.2 | Decided: from the likes playlist, [[ADR-010 Like dates from the likes playlist]] |
| TBD-4 | HTTP transport | Decided: stdio only, [[ADR-009 Stdio transport only]] |
| TBD-5 | Non-English tokenising | Open (Stage 3) |
| TBD-6 | Quota reserve (500) and max playlist length (24 h) | Open (Stage 3). Both are assumed values; the 24 h limit is enforced in [[Playlist]] |
| TBD-7 | Team details on the SRS cover | Open |
| TBD-8 | Re-check API unit costs | Open. Needs a person to confirm, see [[Quota]] |
| TBD-9 | Transcripts for summaries | Decided: metadata only, [[ADR-011 Metadata only, no transcripts]] |

See also [[Glossary]].
