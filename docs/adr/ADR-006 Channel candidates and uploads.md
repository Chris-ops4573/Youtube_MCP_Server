# ADR-006 Channel candidates and uploads

Status: Accepted (query and candidate search superseded by [[ADR-020 Find similar channels through their videos]])

## Context
FR-2 needs similar channels, but YouTube has no related-channels endpoint (same
limit as FR-1, see [[ADR-002 Metadata similarity]]). FR-2.2 wants recent upload
metadata in each profile, and `search.list` costs 100 units per call.

## Decision
- Find candidates with `search.list type=channel`, using the seed's top 2 keywords as the query.
- Read recent uploads from the uploads playlist (`UC...` becomes `UU...`) with `playlistItems.list` (1 unit), not from a search.
- Keep only upload **titles** in the profile.
- Never use subscriber counts for ranking (SRS 5.5).
- Reuse the FR-1 TF-IDF code through one shared helper.
- Cache channel searches (1 h) and upload titles (6 h) in the existing SQLite cache.

## Consequences
- One request costs 118 units (about 80 a day), most of it the single search.
- A real test showed the query must not contain the title or topics: the title returns the seed itself, and YouTube returns topics in a changing order, which broke caching and gave 0 results. The query now uses keywords only.
- Quality depends on the seed having keywords; channels without them fall back to the title and are flagged `low_confidence`.
- `playlistItems.list` costs 1 unit (re-check in the Quota Calculator, TBD-8).

Cites: [[Channels]], [[Quota]], [[Cache]]
