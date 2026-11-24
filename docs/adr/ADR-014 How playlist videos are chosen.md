# ADR-014 How playlist videos are chosen

Status: Accepted

## Context
FR-5.2 and FR-5.3 ask for videos that fit a topic and constraints, a total within
10 percent of the requested length, no duplicates, and an explanation of anything
unmet. YouTube has no "make a playlist" call, and a search costs 100 units.

## Decision
- Take **one search** of up to 50 results for the topic, in YouTube's relevance order (101 units with video details).
- Drop live or upcoming videos, videos with no usable length, videos longer than `max_video_minutes`, videos shorter than `min_video_minutes`, videos whose **known** language differs, and duplicates (FR-5.2). The minimum is an addition to the SRS's list of constraints, made after a real test returned many 20 second Shorts. It is optional and off by default.
- If the chosen videos include some under 3 minutes and no minimum was set, add a note naming `min_video_minutes`, so the AI can propose again.
- Videos with **no language information are kept** and counted in a note, because dropping them would remove most results.
- Walk the list in order and take each video that still fits under 110 percent of the target. Stop once the target is reached. Accept the result if it is between 90 and 110 percent, otherwise say how short it was (FR-5.3).
- All of this uses whole-number maths, so a video exactly on the edge (a 66 minute video for a 60 minute target) is decided correctly.
- The target must be 5 to 1440 minutes (the 24 hour limit is an assumed value: TBD-6).

## Consequences
- Fast and predictable: the same search gives the same playlist.
- Relevance order is not quality order. A real test returned many 20 second Shorts for a "tutorial" topic. `min_video_minutes` fixes that when it is used: the same request went from 4 short clips out of 7 videos to 4 proper videos. Making a minimum the default would be a one-line change.
- It is a greedy choice, not an exact best fit, so it can miss a combination that fits better.
- Narrow topics or long playlists can fall short with one search. The shortfall is reported, not hidden.

Cites: [[Playlist]], [[Quota]]
