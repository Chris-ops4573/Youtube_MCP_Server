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
| `API_KEY_MISSING` | no `YOUTUBE_API_KEY` set |
| `QUOTA_EXCEEDED` | not enough daily quota left (checked before any call) - see [[Quota]] |
| `YOUTUBE_API_ERROR` | API error or network failure after retries |

Each error class in `errors.py` has its own `code` and `remediation`.

Files: `src/ytmcp/errors.py`, `src/ytmcp/tools/similar_videos.py`

Why: [[ADR-003 Structured errors]]. Part of [[Architecture]].
