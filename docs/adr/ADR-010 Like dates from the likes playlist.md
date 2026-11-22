# ADR-010 Like dates from the likes playlist

Status: Accepted (settles TBD-3)

## Context
FR-4.2 needs monthly trends and says to name the date field used. TBD-3 asked
whether the API gives the date a video was liked, or whether a stand-in is needed.

## Decision
Read likes through the user's **likes playlist** instead of `videos.list` with
`myRating=like`:
1. `channels.list` with `mine=true` and `part=contentDetails` gives `relatedPlaylists.likes`.
2. `playlistItems.list` on that playlist returns liked videos, newest first, 50 per call (1 unit each).
3. `snippet.publishedAt` is the date the video was liked. `contentDetails.videoPublishedAt` is the date the video was uploaded.

This was tested on 2026-11-23 on a real account with thousands of likes: the playlist was
readable with the read-only scope and both dates were present.

## Consequences
- FR-4.2 can use real like dates. The report should say it used "date liked" (FR-4.2).
- The same call is the cheapest way to page through likes. Reading about 4,000 likes would take about 80 units, so FR-3.1 and FR-4 should cap how many they read.
- Video details (category, tags, duration) still need `videos.list` in batches of 50.
- Un-liking and re-liking a video changes its date.
- **Watch history is not available.** The response has no watch history playlist, which matches SRS 1.4 and FR-4.4.
- Dates for subscriptions and playlist items also exist in the API (`publishedAt`), but only likes were tested.

Cites: [[Auth]], [[Quota]]
