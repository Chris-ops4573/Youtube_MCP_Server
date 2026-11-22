# ADR-011 Metadata only, no transcripts

Status: Accepted (settles TBD-9)

## Context
SK-1 summarises a video, and TBD-9 asked whether summaries should use
transcripts. The SRS plan is metadata only.

## Decision
Summaries and all scoring use **metadata only**: title, description, tags,
category, language, duration, channel details and recent upload titles.

## Consequences
- The official API only gives caption text for videos the signed-in user owns, so transcripts of other people's videos could only come from scraping, which the SRS rules out (1.4, 5.5).
- Summaries are shallower than a transcript-based summary, and weak when a video has a short description and no tags. Those results are flagged `low_confidence` (FR-1.4).
- Non-English metadata is still an open item (TBD-5, Stage 3).

Cites: [[Similarity]], [[Requirements]]
