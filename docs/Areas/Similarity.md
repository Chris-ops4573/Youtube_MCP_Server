# Similarity

Used by FR-1 (similar videos) and FR-2 (similar channels). File: `src/ytmcp/similarity.py`, which holds both the video and the channel scoring.

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

## Describing one video
`describe_video(video)` returns one video's title, channel, length, the first 10 tags, category ID, language, a description shortened to 500 characters, its URL and whether it is live. It costs 1 quota unit and does no scoring. The video-to-playlist skill ([[Playlist]]) uses it to understand a video before planning a playlist. All text is cleaned and the result carries the untrusted-text notice ([[Errors]]). Code: `describe_video` in `src/ytmcp/services/similar_videos.py` and `describe_video_tool` in `src/ytmcp/tools.py`.

## Topic words
`top_words(documents, n, exclude)` returns the n most common topic words: words of 3 or more letters, without English stop words and format words such as "shorts" or "video". A word counts once per document, and ties are broken alphabetically. FR-2 uses it to build the channel search query from upload titles, and FR-3 uses it for the taste profile's top terms.

## Channels (FR-2.2, FR-2.3)
Channel scoring is in the same file and uses the same TF-IDF helper, with its own weights. A channel is described by a profile: its description, keywords, topics and the titles of its recent uploads. Its name is left out ([[ADR-020 Find similar channels through their videos]]). The whole flow (finding candidates, cost) is in [[Channels]].

| Signal | Weight | How |
|---|---|---|
| text | 0.60 | TF-IDF cosine of the whole profile |
| keywords | 0.25 | Jaccard overlap of keywords |
| topics | 0.15 | Jaccard overlap of topics |

- Weights must sum to 1. They are starting guesses (TBD-2).
- Results exclude the seed channel and duplicates; ties broken by channel ID (deterministic).
- Subscriber counts are never used for ranking (SRS 5.5), so a hidden count cannot change a score.
- `low_confidence` is true when the seed or a candidate has no keywords and no topics.

## Taste profile for recommendations (FR-3.2)
The same file also scores videos against a taste profile built from the user's likes and subscriptions. The weights are text 0.60, category 0.20 and channel 0.20 (starting guesses, TBD-2). The whole flow, the reasons and the cost are in [[Recommendations]].

Part of [[Architecture]].
