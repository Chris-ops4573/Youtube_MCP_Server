# ADR-021 One account-reading cap for all tools

Status: Accepted

## Context
`recommend_videos` read the newest 250 likes ([[ADR-017 Recommendations from a taste profile]]), and `analyze_engagement` read 500 ([[ADR-018 Engagement analysis sources and periods]]). Each service kept its own copy of the caps, so the same account gave the two tools different histories, and nothing stopped the copies drifting further apart (D-13 in [[Defect Log]]).

## Decision
- One set of caps for every tool that reads the signed-in user's account: **500 likes, 200 subscriptions, 10 playlists**, and pages of 50.
- They live once, in `src/ytmcp/quota.py` next to the unit costs, because they exist to limit quota. Both services import them.
- 500 was chosen over 250 because it covers about a year of likes for most people, so a 12-month trend is usually complete, and it costs only 10 more units per recommendation.

## Consequences
- `recommend_videos` costs **137** units instead of 127: 5 more pages of likes and 5 more batches of video details. About 69 requests fit in a day's usable quota instead of 74. See [[Quota]].
- The taste profile also sees older likes, not only the newest ones.
- `analyze_engagement` is unchanged (still 47 units).
- Changing a cap now changes both tools, and a test checks they agree.

Cites: [[Quota]], [[Recommendations]], [[Engagement]]
