# User Guide

SE-7: how to use the server, in plain steps. The exact details of each tool are in [[Tool Reference]]; the setup is also in the README at the project root.

## 1. First time
1. Install and add your API key as described in the README. `python -m ytmcp quota status` is a quick way to check the program runs.
2. For anything about your own account, sign in once: `python -m ytmcp auth login`. For creating playlists, sign in with `python -m ytmcp auth login --write` instead. A browser window opens; Google asks for permission. Your login stays in the system keyring ([[Auth]]).
3. Connect your AI client using the snippet in the README.

## 2. Things you can ask

### Find similar videos or channels
> "Find videos similar to https://www.youtube.com/watch?v=..."
> "Find channels like @fireship"

You get a ranked list with a score and the reason it scored that way. A `low_confidence` flag means the video or channel had little information, so treat the order loosely.

### Get recommendations from your own taste
> "Recommend 10 videos based on what I like"

Needs the sign-in. It reads your likes, subscriptions and playlists (read-only), and leaves out what you already liked or saved. Each result says why it was picked. With fewer than 5 likes the answer is marked low confidence ([[Recommendations]]).

### See what you like
> "What do I watch most? Compare the last 6 months with the 6 before."

Reports your top channels and categories, how many videos you liked each month, and how long your videos usually are. Only likes have dates, so the trend and comparison use likes. It cannot use watch history: YouTube does not share it ([[Engagement]]).

### Make a playlist
Example conversation:
> **You:** Make a 45 minute playlist from https://www.youtube.com/watch?v=...
> **AI:** (describes the video, finds related ones) Here is a proposal of 7 videos, 46 minutes, from 5 channels. Nothing is created yet. Shall I create it as a private playlist?
> **You:** Yes.
> **AI:** (your client asks you to confirm) ... Done: link to the private playlist.

- Nothing is created until **you** say yes, and the confirmation comes from you, not from the AI. If your client cannot ask you, the AI tells you to run `python -m ytmcp playlist confirm <proposal_id>` in a terminal, then it can create the playlist.
- Playlists are private. You can change that on YouTube. The server never edits or deletes playlists.
- A proposal lasts 15 minutes.
- Clips under 3 minutes (like Shorts) are left out unless you ask to keep them ([[ADR-019 Leave out short clips by default]]).
- If a playlist is only partly created (for example a video was deleted), the answer lists what failed. It is not retried, so nothing is duplicated; ask for a new proposal ([[Playlist]]).

## 3. Quota
YouTube allows 10,000 units a day, reset at midnight Pacific time. Searches are the expensive part (about 100 units each). Check today's use with `python -m ytmcp quota status` ([[Quota]]). A request that would go over is refused before it starts.

## 4. What an error means
| Code | What it means and what to do |
|---|---|
| `API_KEY_MISSING` | Add `YOUTUBE_API_KEY` to `.env` |
| `OAUTH_NOT_CONFIGURED` | Add the OAuth client ID and secret to `.env`, then sign in |
| `AUTH_REQUIRED` | You are not signed in, or the login expired: run `python -m ytmcp auth login` |
| `AUTH_FAILED` | Sign-in was denied or timed out, or there is no system keyring: try again |
| `WRITE_ACCESS_REQUIRED` | Your login can only read: run `python -m ytmcp auth login --write` once |
| `QUOTA_EXCEEDED` | Not enough quota left today: try tomorrow or ask for less |
| `INVALID_VIDEO_REFERENCE` / `INVALID_CHANNEL_REFERENCE` | Use a video ID or watch, youtu.be, shorts or embed link; a channel ID, @handle or channel link |
| `VIDEO_NOT_FOUND` / `CHANNEL_NOT_FOUND` | It is private, deleted or does not exist |
| `INVALID_CONSTRAINTS` / `INVALID_ARGUMENT` | One of the settings is not allowed; the message names which and why |
| `NO_VIDEOS_FOUND` | Nothing matched: change the topic or loosen the settings |
| `PROPOSAL_EXPIRED` | The proposal is older than 15 minutes: ask for a new one |
| `PROPOSAL_MISMATCH` / `PROPOSAL_NOT_FOUND` / `PROPOSAL_ALREADY_USED` | Ask for a new proposal and use its exact `proposal_id` and `content_hash` |
| `CONFIRMATION_REQUIRED` | Your client could not ask you: confirm with `python -m ytmcp playlist confirm <proposal_id>` in a terminal |
| `YOUTUBE_CHANNEL_REQUIRED` | The Google account has no YouTube channel: create one on YouTube |
| `ACCOUNT_NOT_AVAILABLE` / `PLAYLIST_WRITES_DISABLED` | The server is running on sample data (fixture mode): set `YTMCP_PROVIDER=youtube` |
| `NOT_ENOUGH_HISTORY` | There are no likes, subscriptions or playlists to work from |
| `YOUTUBE_API_ERROR` | YouTube or the network failed after retries: try again later |

The full list with where each comes from is in [[Errors]].

## 5. Problems
- **Sign-in stops working after about a week:** Google ends logins for apps in Testing mode after 7 days. Sign in again.
- **Check everything works:** `python -m ytmcp local-check` (uses sample data only, no quota).
