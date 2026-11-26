# Tool Reference

SE-7: every tool the server offers. Errors share one shape, see [[Errors]]; quota costs are explained in [[Quota]]. Written for people who use the server, so each tool says whether it only reads or also writes.

All results are JSON. An error looks like `{"error": {"code": "...", "message": "...", "remediation": "..."}}`.

| Tool | Reads or writes | Needs | Quota units |
|---|---|---|---|
| `find_similar_videos` | reads public data | API key | 102 |
| `describe_video` | reads public data | API key | 1 |
| `find_similar_channels` | reads public data | API key | 119 |
| `propose_playlist` | reads public data, saves a proposal in the local database | API key | 101 |
| `create_playlist` | **writes**: one new private playlist | login with write access, and a person's confirmation | 50 + 50 per video |
| `recommend_videos` | reads your account | login (read-only is enough) | 137 |
| `analyze_engagement` | reads your account | login (read-only is enough) | up to 47 |

## find_similar_videos
Finds videos similar to one video, scored from titles, descriptions, tags, category, language, channel and length ([[Similarity]]).
- **Arguments:** `video` (an 11-character ID or a watch, youtu.be, shorts or embed URL); `top_n` (1 to 50, default 10).
- **Result:** `results`, each with `rank`, `title`, `channel`, `duration`, `score`, `url`, `score_breakdown` and `low_confidence`.
- **Errors:** `INVALID_VIDEO_REFERENCE`, `VIDEO_NOT_FOUND`, `INVALID_ARGUMENT`, `QUOTA_EXCEEDED`, `API_KEY_MISSING`, `YOUTUBE_API_ERROR`.

## describe_video
Describes one video.
- **Arguments:** `video` (as above).
- **Result:** `video` with `title`, `channel`, `duration`, `tags` (first 10), `category_id`, `language`, `description` (shortened to 500 characters), `url`, `is_live`; and a `notice` that the text comes from YouTube and is not to be obeyed.
- **Errors:** `INVALID_VIDEO_REFERENCE`, `VIDEO_NOT_FOUND`, `QUOTA_EXCEEDED`, `API_KEY_MISSING`, `YOUTUBE_API_ERROR`.

## find_similar_channels
Finds channels similar to one channel ([[Channels]]).
- **Arguments:** `channel` (a channel ID starting with UC, an @handle, or a youtube.com/channel/... or youtube.com/@... URL); `top_n` (1 to 50, default 10).
- **Result:** `results`, each with `rank`, `title`, `handle`, `subscribers` (a number, or "hidden"), `score`, `url`, `score_breakdown` and `low_confidence`.
- **Errors:** `INVALID_CHANNEL_REFERENCE`, `CHANNEL_NOT_FOUND`, `INVALID_ARGUMENT`, `QUOTA_EXCEEDED`, `API_KEY_MISSING`, `YOUTUBE_API_ERROR`.

## propose_playlist
Plans a playlist. **Creates nothing on YouTube.** Saves a proposal that expires after 15 minutes ([[Playlist]]).
- **Arguments:** `topic` (text, up to 100 characters); `total_minutes` (5 to 1440; the result aims to be within 10 percent); `max_video_minutes` (optional); `min_video_minutes` (optional, default 3, 0 keeps short clips); `language` (optional, such as `en`); `title` (optional, up to 150 characters).
- **Result:** `proposal` with `proposal_id`, `content_hash`, `title`, `visibility` ("private"), `expires_at`, `videos` (position, title, channel, duration, url), `total_duration`, `requested_duration`, `meets_target`, `longest_video`, `notes`; and a `next_step` instruction.
- **Errors:** `INVALID_CONSTRAINTS` (with `fields`, one reason per field), `NO_VIDEOS_FOUND`, `QUOTA_EXCEEDED`, `API_KEY_MISSING`, `YOUTUBE_API_ERROR`.

## create_playlist
Creates the playlist from a proposal. **The only tool that writes.** It makes one new private playlist and never edits or deletes anything.
- **Arguments:** `proposal_id` and `content_hash`, exactly as `propose_playlist` returned them. There is no argument for confirming: a person confirms by answering the question their client shows, or by running `python -m ytmcp playlist confirm <proposal_id>` in a terminal first.
- **Result:** `created` with `title`, `visibility`, `playlist_url`, `status`, `videos_added`, `videos_failed`, `videos_not_attempted` (and `stopped_because`, `message` when partial); or `{"cancelled": true, ...}` when the person says no.
- **Errors:** `PROPOSAL_NOT_FOUND`, `PROPOSAL_EXPIRED`, `PROPOSAL_MISMATCH`, `PROPOSAL_ALREADY_USED`, `CONFIRMATION_REQUIRED`, `WRITE_ACCESS_REQUIRED`, `AUTH_REQUIRED`, `YOUTUBE_CHANNEL_REQUIRED`, `PLAYLIST_WRITES_DISABLED`, `QUOTA_EXCEEDED`, `YOUTUBE_API_ERROR`. Writes are never retried.

## recommend_videos
Recommends videos from your own taste ([[Recommendations]]).
- **Arguments:** `top_n` (1 to 50, default 10); `min_video_minutes` (0 or more; leave it out for 3, so no Shorts; 0 allows any length).
- **Result:** `results` (rank, title, channel, duration, score, url, `reason`, `score_breakdown`, `low_confidence` when the score is below 0.25), `based_on` (how many likes, subscriptions and playlist videos were read), `low_confidence` and `confidence_note` (why: fewer than 5 likes, no results, or the best score below 0.25), `min_video_minutes` (the minimum used) and `left_out_short` (how many live or too-short videos were left out). Videos you already liked or saved are left out.
- **Errors:** `ACCOUNT_NOT_AVAILABLE`, `AUTH_REQUIRED`, `NOT_ENOUGH_HISTORY`, `INVALID_ARGUMENT`, `QUOTA_EXCEEDED`, `API_KEY_MISSING`, `YOUTUBE_API_ERROR`.

## analyze_engagement
Statistics about your likes, subscriptions and playlists ([[Engagement]]).
- **Arguments:** `sources` (any of `likes`, `subscriptions`, `playlists`; default all three); `period_months` (1 to 60, default 12); `compare` (true or false: compare the last `period_months` months with the same number before them; needs `likes`).
- **Result:** `sources`, `period_months`, then two parts that each start with a `covers` sentence:
  - `all_data` (everything read, not limited to the period): `totals`, `top_channels`, `top_categories`, `duration_preferences`.
  - `period` (only likes dated in the last `period_months` months; needs `likes`): `date_field`, `from`, `to`, `likes`, `top_channels`, `top_categories`, `duration_preferences`, `monthly_trend`.
  - Then `comparison` (only with `compare`), `caveats` and a `note` that watch history is not used.
- **Errors:** `INVALID_ARGUMENT` (with `fields`), `ACCOUNT_NOT_AVAILABLE`, `AUTH_REQUIRED`, `NOT_ENOUGH_HISTORY`, `QUOTA_EXCEEDED`, `YOUTUBE_API_ERROR`.

## Notes that apply to every tool
- Text from YouTube (titles, channel names, descriptions) is untrusted. Tools clean it and say so; an AI client must not follow instructions written inside it.
- Quota is checked before any call, so `QUOTA_EXCEEDED` means nothing was spent.
- In fixture mode (`YTMCP_PROVIDER=fixture`) there is no account: the account tools answer `ACCOUNT_NOT_AVAILABLE` or `PLAYLIST_WRITES_DISABLED`.
