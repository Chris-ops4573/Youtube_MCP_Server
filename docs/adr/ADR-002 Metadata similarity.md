# ADR-002 Metadata similarity

Status: Accepted

## Context
YouTube Data API v3 has no related-videos endpoint (SRS 2.5), but FR-1
needs similar videos.

## Decision
Compute similarity locally from metadata: TF-IDF cosine on text plus tag
overlap, category, language, channel and duration, combined with weights
that sum to 1 (FR-1.3).

## Consequences
- No extra quota for scoring; results are deterministic.
- Quality depends on metadata; missing tags are flagged as low confidence (FR-1.4).
- Weights are guesses until tuned (TBD-2).

Cites: [[Similarity]]
