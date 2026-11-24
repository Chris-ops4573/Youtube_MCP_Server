# Engagement

FR-4: statistics about your own YouTube likes, subscriptions and playlists.
Files: `src/ytmcp/services/engagement.py` (the statistics and the steps), `src/ytmcp/tools.py` (what the AI client sees)

## The tool
`analyze_engagement(sources, period_months, compare)`. It needs you to be signed in (read-only is enough: [[Auth]]) and only reads. In fixture mode there is no account, so it answers `ACCOUNT_NOT_AVAILABLE`.

| Argument | Meaning | Default |
|---|---|---|
| `sources` | any of `likes`, `subscriptions`, `playlists` | all three |
| `period_months` | how many recent months the monthly trend covers, 1 to 60 | 12 |
| `compare` | also compare the last `period_months` months with the same number of months before them. Needs `likes` | false |

Bad arguments are reported field by field (`INVALID_ARGUMENT` with `fields`) before anything is read.

## What it reports
| Part | What it is | Requirement |
|---|---|---|
| `top_channels` | The 10 channels that show up most. Every liked video, saved video (in a playlist) and subscription counts once for its channel. A video both liked and saved counts once. Each entry says whether you subscribe to the channel | FR-4.1 |
| `top_categories` | The 10 most common video categories, by name, with count and share | FR-4.1 |
| `monthly_trend` | Likes per month for the last `period_months` months (UTC, empty months shown as 0), and **which date was used**: the date the video was liked | FR-4.2 |
| `duration_preferences` | How the videos split by length: under 5 min, 5 to 20, 20 to 60, over 60 | FR-4.3 |
| `comparison` | Only with `compare`: the last N months next to the N months before, each with its own likes count, top 5 channels, top 5 categories and duration split | FR-4.3 |
| `totals` | How many likes, subscriptions and playlist videos were read | |
| `caveats` | Plain warnings, for example when the cap cut off the period | |
| `note` | "Based on your likes, subscriptions and playlists only. YouTube does not share watch history." | FR-4.4 |

Things to know:
- **Only likes have a date**, so the trend and the comparison use likes only. Subscriptions and playlists are counted in the top lists but not trended ([[ADR-010 Like dates from the likes playlist]]). Asking to compare without `likes` is an error.
- The period applies to the trend and the comparison. The top lists and the duration split use everything that was read.
- The tool returns only statistics: never the titles of the videos you liked.

## Steps
1. Check the arguments, then the budget (before any API call).
2. Read the chosen sources with the account provider ([[Providers]]): up to 500 likes (newest first), 200 subscriptions, and the videos in up to 10 playlists.
3. Get the details of the liked and saved videos (the cache helps), and the category names.
4. Work out the statistics. The functions that do this are pure: no API calls.

## Cost: up to 47 units
| Call | Units |
|---|---|
| find the likes playlist | 1 |
| likes (10 pages of 50) | 10 |
| subscriptions (4 pages of 50) | 4 |
| your playlists | 1 |
| one page per playlist (10) | 10 |
| liked video details (10 batches of 50) | 10 |
| saved video details (10 batches of 50) | 10 |
| category names | 1 |

The cost follows the sources you choose: 22 for likes only, 4 for subscriptions only, 22 for playlists only, 26 for likes and subscriptions. In practice it is often less, because the cap is rarely reached.

## Caveats you may see
- "Only your newest 500 likes were read (back to a date), so earlier months are incomplete." The cap cut off the period, so older months show too few likes. With `compare` the check covers twice the period.
- "Only the first 200 subscriptions were read."

## Errors
| Code | When |
|---|---|
| `INVALID_ARGUMENT` | a bad argument; `fields` says which and why |
| `ACCOUNT_NOT_AVAILABLE` | fixture mode, so no account |
| `AUTH_REQUIRED` | not signed in, or the login expired |
| `NOT_ENOUGH_HISTORY` | the chosen sources are empty |
| `QUOTA_EXCEEDED` | the cost does not fit in what is left today |

## Known limits
- Likes beyond the newest 500, and videos beyond the first 50 of each of 10 playlists, are not read.
- Category names come from YouTube's list for one region (US). An ID that is not in the list shows as "Category 99" and a video with no category as "Unknown".
- Tested with fakes and over the real MCP protocol. **It has not been tried on a real account yet.**

Why: [[ADR-018 Engagement analysis sources and periods]]. Part of [[Architecture]].
