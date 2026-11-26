# ADR-017 Recommendations from a taste profile

Status: Accepted (the 250-like cap and the cost of 127 units are superseded by [[ADR-021 One account-reading cap for all tools]])

## Context
FR-3 asks for recommendations built from the user's likes, subscriptions and playlists, read with the read-only scope and capped per source to limit quota. Candidates must exclude videos the user already liked or saved, and each result needs a short reason based on metadata. YouTube has no recommendation endpoint, so the ranking is computed locally, as in [[ADR-002 Metadata similarity]].

## Decision
- **Caps per request:** 250 likes, 200 subscriptions and 10 playlists.
- **Cost:** 127 quota units, checked before any call: 1 (channel lookup) + 5 (likes pages) + 4 (subscription pages) + 1 (playlists) + 10 (playlist items) + 5 (liked video details) + 100 (one search) + 1 (candidate details).
- **Taste profile:** the titles and tags of liked videos as text; the 3 words found in the most liked videos (3 letters or more; **a word counts once per video**; English stop words and format words such as "shorts" removed; ties broken alphabetically); the share of likes in each category; and the channels the user liked or subscribed to. With no likes, subscription titles are used.
- **Candidates:** one search with the top terms, 50 results. Drop videos already liked, already in a playlist, or duplicated.
- **Score:** 0.6 x text similarity + 0.2 x category share + 0.2 x same-channel. These weights are guesses, tuned later (TBD-2).
- **Reasons:** one per result, the first that applies: a liked or subscribed channel; shared interest words; a category the user likes often; otherwise similar to liked videos.
- **Low confidence** when there are fewer than 5 likes. With no likes and no subscriptions the tool answers NOT_ENOUGH_HISTORY.
- **Privacy:** the tool reports only counts about the user's data (likes, subscriptions, videos found in playlists), never the liked videos themselves.

## Consequences
- About 74 requests a day fit in the 9,500 usable units, almost all of the cost being the one search.
- Quality depends on the likes. One search with three words can under-represent a varied taste.
- **Found by a real test:** counting every occurrence let a few videos with long repeated tag lists dominate the top words, and "shorts" topped the list for an account whose likes are mostly Shorts. So a word now counts once per video and format words are ignored. The results then matched the account's broad interests and came from 10 different channels.
- If most of a person's likes are Shorts, most recommendations will be Shorts too. There is no minimum length for recommendations (a possible follow-up).
- The weights are untuned. Real examples are needed before TBD-2 can be closed.
- Built in task F2 of [[Refactor and Feature Plan]]. It is tested with fakes and over the real MCP protocol, not yet against a real account.
- The number of playlists read is not reported, only the videos found in them, because the account interface returns video IDs only.

Cites: [[Similarity]], [[Quota]], [[ADR-010 Like dates from the likes playlist]]
