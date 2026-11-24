# ADR-018 Engagement analysis sources and periods

Status: Proposed

## Context
FR-4 asks for the top channels and categories, monthly trends that say which date field was used, duration preferences, a comparison of two periods, and a statement that watch history is never used. Only the likes playlist carries a date per item ([[ADR-010 Like dates from the likes playlist]]).

## Decision
- **Arguments:** `sources` (likes, subscriptions, playlists; default all three), `period_months` (1 to 60, default 12) and `compare` (true or false).
- **Periods:** the last N months in UTC. With compare on, the N months before are shown next to them. This is easy for an AI client to call and easy to test.
- **Trends use likes only.** Subscriptions and playlists are counted for the top lists but not trended, because they have no like date in this data. The output names the date used: the date the video was liked.
- **Caps per request:** 500 likes, 200 subscriptions and 10 playlists.
- **Cost:** 47 quota units, checked first: 1 + 10 + 4 + 1 + 10 + 10 + 10 + 1 for the channel lookup, likes pages, subscription pages, playlists, playlist items, liked video details, playlist video details and the category names.
- **Duration buckets:** under 5 minutes, 5 to 20, 20 to 60, and over 60.
- **Every result says** that it is based on likes, subscriptions and playlists only, and that YouTube does not share watch history (FR-4.4).

## Consequences
- A person with more than 500 likes gets the newest 500, and the output says so.
- An explicit pair of date ranges was rejected: it is more flexible but needs more validation and has more ways to go wrong.
- Category names need one extra call (cached).
- Status changes to Accepted when the feature is built (task F3 in [[Refactor and Feature Plan]]).

Cites: [[ADR-010 Like dates from the likes playlist]], [[Quota]]
