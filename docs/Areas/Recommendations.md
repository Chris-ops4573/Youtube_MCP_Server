# Recommendations

FR-3: videos you might like, worked out from your own YouTube likes, subscriptions and playlists.
Files: `src/ytmcp/services/recommendations.py` (the steps), `src/ytmcp/similarity.py` (the taste profile and the scoring), `src/ytmcp/tools.py` (what the AI client sees)

## The tool
`recommend_videos(top_n)` with `top_n` from 1 to 50 (default 10). It needs you to be signed in (`python -m ytmcp auth login`, read-only is enough: [[Auth]]). It only reads. In fixture mode there is no account, so it answers `ACCOUNT_NOT_AVAILABLE`.

## Steps
1. **Check the budget first.** The request costs 127 units. If that does not fit in what is left today, it stops before a single call ([[Quota]]).
2. **Read your account** with the account provider ([[Providers]]): up to 250 likes (newest first), 200 subscriptions, and the videos in up to 10 of your playlists. If you have no likes and no subscriptions, it stops with `NOT_ENOUGH_HISTORY` before reading the playlists.
3. **Get the details** of the liked videos (title, tags, category, channel), which the cache serves when it can.
4. **Build a taste profile** (below).
5. **Search once** with the profile's top words, 50 results.
6. **Leave out** videos you already liked, videos already in one of your playlists, and duplicates (FR-3.3).
7. **Score and rank** the rest, and give each one a short reason.

## The taste profile (FR-3.2)
| Part | How it is made |
|---|---|
| Text | The titles and tags of your liked videos. With no likes, your subscription titles instead |
| Top words | The 3 most common words of 3 letters or more in that text, leaving out common English words. Ties are broken alphabetically. They become the search query |
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
- `low_confidence`: true with fewer than 5 likes.

## Cost: 127 units
| Call | Units |
|---|---|
| find the likes playlist | 1 |
| likes (5 pages of 50) | 5 |
| subscriptions (4 pages of 50) | 4 |
| your playlists | 1 |
| one page per playlist (10) | 10 |
| liked video details (5 batches of 50) | 5 |
| the search | 100 |
| details of the search results | 1 |

About 74 requests fit in a day's usable quota. Repeats are cheaper because the cache answers the video details and the search.

## Errors
| Code | When |
|---|---|
| `ACCOUNT_NOT_AVAILABLE` | fixture mode, so no account |
| `AUTH_REQUIRED` | not signed in, or the login expired |
| `NOT_ENOUGH_HISTORY` | no likes and no subscriptions, or no usable words in them |
| `QUOTA_EXCEEDED` | 127 units do not fit in what is left today |
| `INVALID_ARGUMENT` | `top_n` is not 1 to 50 |

## Known limits
- The weights are untuned (TBD-2) and the search uses only 3 words, so a varied taste is under-represented.
- Likes beyond the newest 250 are not read, and only the first 50 videos of each of 10 playlists are.
- The tool reports `playlist_videos` (how many distinct videos were found in your playlists), not the number of playlists, because the account interface returns only the video IDs.
- Tested with fakes and over the real MCP protocol. **It has not been tried against a real account yet.**

Why: [[ADR-017 Recommendations from a taste profile]]. Part of [[Architecture]].
