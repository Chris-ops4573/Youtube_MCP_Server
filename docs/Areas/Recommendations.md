# Recommendations

FR-3: videos you might like, worked out from your own YouTube likes, subscriptions and playlists.
Files: `src/ytmcp/services/recommendations.py` (the steps), `src/ytmcp/similarity.py` (the taste profile and the scoring), `src/ytmcp/tools.py` (what the AI client sees)

## The tool
`recommend_videos(top_n, min_video_minutes)` with `top_n` from 1 to 50 (default 10) and `min_video_minutes` 0 or more (left out = 3, the same default as `propose_playlist`; 0 = any length; anything else is `INVALID_ARGUMENT` before any call). It needs you to be signed in (`python -m ytmcp auth login`, read-only is enough: [[Auth]]). It only reads. In fixture mode there is no account, so it answers `ACCOUNT_NOT_AVAILABLE`.

## Steps
1. **Check the budget first.** The request costs 137 units. If that does not fit in what is left today, it stops before a single call ([[Quota]]).
2. **Read your account** with the account provider ([[Providers]]): up to 500 likes (newest first), 200 subscriptions, and the videos in up to 10 of your playlists. These caps are shared with [[Engagement]] and live in `src/ytmcp/quota.py` ([[ADR-021 One account-reading cap for all tools]]). If you have no likes and no subscriptions, it stops with `NOT_ENOUGH_HISTORY` before reading the playlists.
3. **Get the details** of the liked videos (title, tags, category, channel), which the cache serves when it can.
4. **Build a taste profile** (below).
5. **Search once** with the profile's top words, 50 results.
6. **Leave out** videos you already liked, videos already in one of your playlists, and duplicates (FR-3.3). Then leave out live videos and videos shorter than `min_video_minutes` (default 3), so Shorts do not fill the list.
7. **Score and rank** the rest, and give each one a short reason.

## The taste profile (FR-3.2)
| Part | How it is made |
|---|---|
| Text | The titles and tags of your liked videos. With no likes, your subscription titles instead |
| Top words | The 3 words found in the most liked videos, 3 letters or more. A word counts **once per video**, so a few videos with long repeated tag lists cannot dominate. Common English words and format words (`shorts`, `video`, `edit`, `official` and similar) are left out. Ties are broken alphabetically. They become the search query |
| Category shares | Each category's share of your likes |
| Channels | The channels of your liked videos, plus the channels you subscribe to |

## The score
Score = sum of (weight x signal), each signal from 0 to 1. The weights are starting guesses (TBD-2).

| Signal | Weight | How |
|---|---|---|
| text | 0.60 | TF-IDF cosine between the profile text and the candidate's title, description and tags |
| category | 0.20 | the candidate's category share in your likes |
| channel | 0.20 | 1 if the candidate is from a channel you liked or subscribe to |

Ties are broken by video ID, so the same input always gives the same order.

## The reason (FR-3.3)
One short reason per result, the first that applies:
1. "From a channel you like or subscribe to: X"
2. "Matches your interests: a, b" (the top words found as whole words in the title)
3. "In a category you like often (N% of your likes)" (when the share is 20% or more)
4. "Similar to videos you liked"

## What the tool returns
- `results`: rank, title, channel, duration, score, url, reason, score_breakdown.
- `based_on`: how many likes, subscriptions and playlist videos were read. **Only counts**: the tool never returns what you liked.
- Each result also has `low_confidence`: true when its score is below **0.25** (`LOW_SCORE`, a starting guess, TBD-2).
- `low_confidence` for the whole answer is true, and `confidence_note` says why, when any of these hold:
  - fewer than 5 likes were read
  - no videos were left after the filters
  - the best score is below 0.25
- `min_video_minutes`: the minimum that was used. `left_out_short`: how many live or too-short videos were left out.

## Cost: 137 units
| Call | Units |
|---|---|
| find the likes playlist | 1 |
| likes (10 pages of 50) | 10 |
| subscriptions (4 pages of 50) | 4 |
| your playlists | 1 |
| one page per playlist (10) | 10 |
| liked video details (10 batches of 50) | 10 |
| the search | 100 |
| details of the search results | 1 |

About 69 requests fit in a day's usable quota. Repeats are cheaper because the cache answers the video details and the search.

## Errors
| Code | When |
|---|---|
| `ACCOUNT_NOT_AVAILABLE` | fixture mode, so no account |
| `AUTH_REQUIRED` | not signed in, or the login expired |
| `NOT_ENOUGH_HISTORY` | no likes and no subscriptions, or no usable words in them |
| `QUOTA_EXCEEDED` | 137 units do not fit in what is left today |
| `INVALID_ARGUMENT` | `top_n` is not 1 to 50, or `min_video_minutes` is not a whole number 0 or more (with `fields`) |

## Known limits
- The weights are untuned (TBD-2) and the search uses only 3 words, so a varied taste is under-represented.
- Likes beyond the newest 500 are not read, and only the first 50 videos of each of 10 playlists are.
- The tool reports `playlist_videos` (how many distinct videos were found in your playlists), not the number of playlists, because the account interface returns only the video IDs.
- The minimum length filters after the one search of 50, so a topic with mostly Shorts can leave only a few results. `left_out_short` shows how many were dropped.
- Tested with fakes and over the real MCP protocol, and **tried on a real account** (see below).

## Tried on a real account (2026-11-24)
Read-only, through the real server: 250 likes, 142 subscriptions and 43 playlist videos were read in about 10 seconds, and the server counted 123 units (the cap was 250 likes and the ceiling 127 then: fewer playlists than the cap were read). The first run gave poor results: the top words were a format word and a name repeated in the tags of a few videos. That is why a word now counts once per video and format words are ignored. The second run matched the account's broad interests, with 10 results from 10 different channels, and each reason was accurate.

Why: [[ADR-017 Recommendations from a taste profile]], [[ADR-021 One account-reading cap for all tools]]. Part of [[Architecture]].
