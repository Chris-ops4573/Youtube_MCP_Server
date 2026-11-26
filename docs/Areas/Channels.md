# Channels

FR-2: find channels similar to a given channel.
Files: `src/ytmcp/services/similar_channels.py`, `src/ytmcp/similarity.py`, `src/ytmcp/tools.py`

## Input (FR-2.1)
A channel ID (`UC` + 22 characters), an `@handle`, or a `youtube.com/channel/...` / `youtube.com/@...` URL (`extract_channel_ref` in `ids.py`). A bare name or an old `/c/` URL is rejected with `INVALID_CHANNEL_REFERENCE`. Handles are looked up with `channels.list` + `forHandle`.

## Steps
1. Look up the seed channel (1 unit).
2. Get its recent upload titles from its uploads playlist (1 unit). A channel ID `UCxxx` has the playlist `UUxxx`, so this avoids a 100-unit search.
3. Build a query from **what the channel publishes**: the 3 most common topic words in its recent upload titles and keywords (`build_channel_query`, using `top_words` from [[Similarity]]). A word counts once per title, and ties are broken alphabetically.
   - Words from the channel's **name** are left out, because a name only finds channels with similar names. A name word that is also one of the channel's keywords stays, because then it names the topic ("rust" in "Rust Lab").
   - Topics are not used (too generic, e.g. "Knowledge").
   - With no topic words left, it uses the first 2 keywords, then the title.
4. `search.list` with `type=video` finds 50 videos on those words (100 units), and `videos.list` fills in their details (1 unit).
5. The channels that made those videos become the candidates, in result order, without the seed or repeats, up to 15 (`candidate_channel_ids`). `channels.list` fills in their details (1 unit).
6. Get recent upload titles for each candidate (1 unit each).
7. Score and rank (see below).

Why videos and not a channel search: `search.list type=channel` matches mostly on channel names, so it returned channels with similar names instead of similar content ([[ADR-020 Find similar channels through their videos]]).

Default search size is 15 candidates. Cost: **1 + 1 + 100 + 1 + 1 + 15 = 119 units** (checked before any call, see [[Quota]]).

## Profile and scoring (FR-2.2, FR-2.3)
A channel profile is its description, keywords, topics and recent upload titles. The **name is left out**, so two channels with similar names are not similar unless their content is.

| Signal | Weight | How |
|---|---|---|
| text | 0.60 | TF-IDF cosine of the whole profile |
| keywords | 0.25 | Jaccard overlap of keywords |
| topics | 0.15 | Jaccard overlap of topics |

- Weights sum to 1 and are guesses (TBD-2). Same TF-IDF code as [[Similarity]].
- The seed and duplicates are excluded; ties are broken by channel ID.
- Subscriber counts are **never** used in scoring (SRS 5.5), so a hidden count can't change a score. The tool shows `"hidden"` when the count is hidden.
- `low_confidence` is true when the seed or a candidate has no keywords and no topics.

## Output
`rank`, `title`, `handle`, `subscribers` (number or `"hidden"`), `score`, `url`, `score_breakdown`, `low_confidence`. Errors follow [[Errors]].

## Known limits
- **Slow when cold:** about 11 s in a real test, because the 15 upload lookups run one after another. With the cache a repeat takes about 1.5 s. Running them in parallel is a possible follow-up.
- **Result quality:** a real test on a web-development channel returned small web-dev channels with scores around 0.2. Weights and query need tuning (TBD-2).
- Topics are Wikipedia category names, not YouTube topics.

Why: [[ADR-006 Channel candidates and uploads]], [[ADR-020 Find similar channels through their videos]]. Part of [[Architecture]].
