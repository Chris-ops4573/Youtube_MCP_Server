# ADR-019 Leave out short clips by default

Status: Accepted

## Context
A real test of `propose_playlist` returned many 20 second Shorts for a general topic ([[ADR-014 How playlist videos are chosen]]). `min_video_minutes` fixed that, but only when the AI client remembered to pass it, so most proposals still carried short clips.

## Decision
- `min_video_minutes` defaults to **3** when it is not given.
- **0 means no minimum.** Short clips stay, and the proposal notes how many there are.
- If 3 minutes cannot fit the other settings (a total or `max_video_minutes` below 3), the default is skipped instead of reporting an error. A minimum the person gives that does not fit is still an error.
- Whole numbers from 0 up are valid; anything else is reported field by field as before.

## Consequences
- Proposals are better by default, and a person who wants short clips can say so.
- A topic that only has short videos may return fewer videos or miss the target length. The notes already say what was left out.
- The default is saved with the proposal, so the content hash covers it.

Cites: [[Playlist]], [[ADR-014 How playlist videos are chosen]]
