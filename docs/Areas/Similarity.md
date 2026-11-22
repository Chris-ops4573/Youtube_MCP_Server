# Similarity

Used by FR-1 (similar videos). File: `src/ytmcp/similarity.py`

YouTube has no related-videos endpoint, so we score from metadata
([[ADR-002 Metadata similarity]]).

Score = sum of (weight x signal), each signal is 0 to 1 (FR-1.3):

| Signal | Weight | How |
|---|---|---|
| text | 0.40 | TF-IDF cosine of title + description + tags |
| tags | 0.20 | Jaccard overlap of tags |
| category | 0.10 | same category = 1 |
| language | 0.05 | same language = 1 |
| channel | 0.10 | same channel = 1 |
| duration | 0.15 | closer durations score higher |

- Weights must sum to 1. They are starting guesses (TBD-2).
- Results exclude the seed and duplicates; ties broken by video ID (deterministic).
- `low_confidence` is true when tags are missing (FR-1.4).

Channels use the same TF-IDF helper with their own weights: see [[Channels]].

Part of [[Architecture]].
