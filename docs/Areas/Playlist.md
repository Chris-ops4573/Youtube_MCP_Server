# Playlist

FR-5: make a private playlist on the user's YouTube account, only after a person confirms.
Files: `src/ytmcp/playlist_planner.py` (choose videos), `src/ytmcp/proposals.py` (saved proposals), `src/ytmcp/services/playlists.py` (the steps), `src/ytmcp/providers/playlists.py` (the YouTube writer), `src/ytmcp/tools/playlists.py` (what the AI client sees)

## Two tools
| Tool | What it does | Changes YouTube? |
|---|---|---|
| `propose_playlist(topic, total_minutes, max_video_minutes, min_video_minutes, language, title)` | Finds videos and saves a **proposal** | No |
| `create_playlist(proposal_id, content_hash)` | Creates the playlist from a proposal, after a person confirms | Yes: one new private playlist |

There is no tool to edit or delete anything (SRS 5.2).

## How it works
1. **Check the settings first** (FR-5.1): every field is validated before any API call, and all problems are listed together, field by field (`INVALID_CONSTRAINTS`). `total_minutes` is 5 to 1440 (24 h, assumed: TBD-6).
2. **Find videos** with one search of up to 50 results. Cost: 101 units, checked before the search ([[Quota]]).
3. **Choose videos** (FR-5.2, FR-5.3): see [[ADR-014 How playlist videos are chosen]]. `min_video_minutes` leaves out Shorts and other short clips; if the result still has clips under 3 minutes and no minimum was set, the proposal says so in its notes, so the AI can propose again with a minimum.
4. **Save a proposal** (FR-5.4) with a random ID, a short fingerprint of its content (`content_hash`) and a **15 minute** expiry. The AI is told to show it and ask. Nothing is created yet (UI-2).
5. **A person confirms** (FR-5.5), in one of two ways:
   - **The client asks the user** (MCP elicitation): "Create the PRIVATE playlist ...?". The answer comes from the client, not from the AI.
   - **If the client cannot ask:** the user runs `python -m ytmcp playlist confirm <proposal_id>` in a terminal, types `yes`, and tells the AI to call `create_playlist` again.
6. **Create** (FR-5.6): quota check, write-permission check, then the proposal is claimed (only one caller can) and the playlist and videos are created.

Why it is built this way: [[ADR-013 Playlist creation needs a person's confirmation]]. Diagrams: [[Design Sequences]].

## What the AI cannot do
| Attempt | Result |
|---|---|
| Call `create_playlist` with a made-up ID | `PROPOSAL_NOT_FOUND` |
| Change the videos, or guess the hash | `PROPOSAL_MISMATCH` (the server uses only its saved list) |
| Create from the same proposal twice | `PROPOSAL_ALREADY_USED` (no duplicate playlists) |
| Use an old proposal | `PROPOSAL_EXPIRED` after 15 minutes |
| Approve it itself | Not possible: there is no `confirmed` argument. Without a person's yes, `CONFIRMATION_REQUIRED` |
| Write with a read-only login | `WRITE_ACCESS_REQUIRED` and the fix |

The terminal command refuses to run unless it is attached to a real terminal, so a script, or an AI that runs shell commands for you, cannot confirm for you.

## Write permission (FR-6.1)
Logins are read-only by default. Before the first playlist, run `python -m ytmcp auth login --write` once ([[Auth]]). If you forget, `create_playlist` tells you, and the proposal stays valid for its 15 minutes.

## Failures (FR-5.6, SRS 5.2)
- **Quota:** needs 50 + 50 per video, checked before anything is created. Running out midway stops the loop and reports what was and was not added.
- **One video fails** (deleted, already there): the rest continue, and the failure is listed with the reason.
- **No YouTube channel:** `YOUTUBE_CHANNEL_REQUIRED` (YouTube's `youtubeSignupRequired`).
- **Writes are never retried.** After a timeout the playlist might already exist, and a retry could make a duplicate. A failed proposal must be proposed again.
- Playlists are always created **private**. Visibility can be changed on YouTube.

## Safety with untrusted text
Video titles and channel names come from YouTube. They are cut to one short line with control characters removed, returned as data, and every proposal tells the AI never to follow instructions inside them ([[Requirements]], SRS 5.3).

## Where proposals live
In the SQLite file, in the `proposals` table, even with the cache switched off, so the terminal command and the server see the same data ([[Design Data]]). Proposals older than a day are deleted at startup.

## Tested against real YouTube (2026-11-23)
- **Proposal:** "rust programming tutorial", 60 minutes, at most 30 minutes per video, English: 14 videos totalling 1:02:52, in 1.4 s, 101 units. A wrong hash was refused. A "yes" with a read-only login was refused at the write-permission step.
- **Real creation** (after `python -m ytmcp auth login --write`): a 10 minute proposal of 6 videos (4 of them were clips under a minute: this led to `min_video_minutes`). The server asked the question, the client said yes, and the playlist was created in 8.7 s (350 units expected: 50 + 6 x 50).
- **Checked on YouTube itself:** the playlist is private, has the right title and description, and holds the same 6 videos in the same order as the proposal. Using the same proposal again was refused (`PROPOSAL_ALREADY_USED`), so no duplicate.
- **With `min_video_minutes=3`:** the same request gave 4 proper videos totalling 19:58 instead of 7 videos with 4 short clips, and 12 short clips were reported as left out. A second real playlist was created, private, and read back from YouTube with the same videos in the same order.
- **Not yet tried:** the terminal confirmation in a real terminal, and a real AI client's own question (the test client used the real protocol, but it was a test client).

## Known limits
- **Short clips:** results come in search relevance order, so a topic like "tutorial" can include 20 second Shorts. Use `min_video_minutes` (3 or more) to leave them out. It is off by default, because the SRS does not ask for it; the proposal warns when short clips are present.
- Which MCP clients can ask the question themselves is not known; the terminal path covers the rest. Under the newer 2026 protocol the server cannot ask mid-call, so it always uses the terminal path.
- A client that answers the question automatically cannot be told apart from a person ([[ADR-013 Playlist creation needs a person's confirmation]]).
- Only one search (50 candidates) is made, so very long playlists on narrow topics may fall short. The notes say so.

Part of [[Architecture]].
