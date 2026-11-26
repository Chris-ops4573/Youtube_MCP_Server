# ADR-020 Find similar channels through their videos

Status: Accepted

## Context
Real use of `find_similar_channels` showed results that matched the seed channel's **name** instead of what it publishes (D-12 in [[Defect Log]]). Three parts of [[ADR-006 Channel candidates and uploads]] favoured names:
- The query was the seed's first 2 keywords, and creators often use their brand name as a keyword.
- `search.list type=channel` matches mostly on channel titles.
- The channel title was part of the profile text that is scored.

## Decision
- The query is the 3 most common topic words in the seed's recent upload titles and keywords (`top_words` in [[Similarity]]). Words from the channel's name are left out, unless the same word is also one of its keywords (then it names the topic). The old keyword and title query stays as the fallback.
- Candidates come from a **video** search: `search.list type=video` for 50 videos, and the channels that made them, without the seed or repeats, up to the search size (15).
- The channel's name is no longer part of the scored profile. Description, keywords, topics and recent upload titles remain.
- `search_channels` is removed from the providers because nothing uses it.

## Consequences
- Candidates publish videos on the same topics, whatever their names.
- One request costs 119 units instead of 118 (one `videos.list` call for the found videos). See [[Quota]].
- A channel whose name is its only topic word (for example a channel called "Rust" with no keywords) loses that word from the query. Its upload titles usually name the topic anyway.
- The channel searches in the cache are gone. FR-2 reuses the video searches.
- Supersedes the candidate search and query parts of [[ADR-006 Channel candidates and uploads]]. The uploads playlist part still holds.

Cites: [[Channels]], [[Similarity]], [[ADR-006 Channel candidates and uploads]]
