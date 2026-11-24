# Errors

Tools never show stack traces. Errors look like this (UI-3):

```json
{"error": {"code": "...", "message": "...", "remediation": "..."}}
```

| Code | When |
|---|---|
| `INVALID_ARGUMENT` | `top_n` not between 1 and 50 |
| `INVALID_VIDEO_REFERENCE` | not a valid video ID or URL |
| `VIDEO_NOT_FOUND` | video is private, deleted or missing |
| `INVALID_CHANNEL_REFERENCE` | not a valid channel ID, @handle or channel URL |
| `CHANNEL_NOT_FOUND` | channel does not exist |
| `OAUTH_NOT_CONFIGURED` | no `YTMCP_OAUTH_CLIENT_ID` set - see [[Auth]] |
| `AUTH_REQUIRED` | not signed in, or the Google login expired |
| `AUTH_FAILED` | sign-in denied, timed out, rejected, or no OS keyring |
| `API_KEY_MISSING` | no `YOUTUBE_API_KEY` set |
| `QUOTA_EXCEEDED` | not enough daily quota left (checked before any call) - see [[Quota]] |
| `YOUTUBE_API_ERROR` | API error or network failure after retries (writes are never retried) |
| `INVALID_CONSTRAINTS` | playlist settings are not valid; the error also has `fields`, one reason per field - see [[Playlist]] |
| `NO_VIDEOS_FOUND` | no video matched the topic and settings |
| `PROPOSAL_NOT_FOUND` / `PROPOSAL_EXPIRED` | the proposal does not exist / is older than 15 minutes |
| `PROPOSAL_MISMATCH` | the `content_hash` does not match the saved proposal |
| `PROPOSAL_ALREADY_USED` | the proposal was already created, failed or was declined |
| `CONFIRMATION_REQUIRED` | a person has not confirmed; the fix is the terminal command |
| `WRITE_ACCESS_REQUIRED` | the login has no write permission: `python -m ytmcp auth login --write` |
| `YOUTUBE_CHANNEL_REQUIRED` | the Google account has no YouTube channel |
| `PLAYLIST_WRITES_DISABLED` | fixture mode: no real playlists |

Each error class in `errors.py` has its own `code` and `remediation`.

Files: `src/ytmcp/errors.py`, `src/ytmcp/tools/similar_videos.py`

Why: [[ADR-003 Structured errors]]. Part of [[Architecture]].
