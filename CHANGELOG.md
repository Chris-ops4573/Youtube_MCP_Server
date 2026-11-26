# Changelog

All notable changes. The dates are the days the work was done. Format follows Keep a Changelog; the project uses simple version numbers.

## Unreleased
### Changed
- `find_similar_channels` matches channels by what they publish, not by their names: the query comes from recent upload titles, candidates are the channels behind a video search, and the name is not scored. Costs 119 units instead of 118 (ADR-020).
- `recommend_videos` and `analyze_engagement` read the same number of likes (500), so `recommend_videos` costs 137 units instead of 127 (ADR-021).
- `recommend_videos` leaves out live videos and videos under 3 minutes by default (`min_video_minutes`, 0 = any length), flags each weak result, and explains a low-confidence answer in `confidence_note`.
- `analyze_engagement` splits its report into `all_data` (everything read) and `period` (only likes dated in the period), each with a `covers` sentence. The top-level `totals`, `top_channels`, `top_categories`, `duration_preferences` and `monthly_trend` fields moved into these parts.

## 1.0.0
### Added
- **Similar videos** (`find_similar_videos`, FR-1): ranked videos scored from titles, descriptions, tags, category, language, channel and length. Accepts an ID or a watch, youtu.be, shorts or embed URL.
- **Describe a video** (`describe_video`): title, channel, length, tags, language and a shortened description for 1 quota unit.
- **Similar channels** (`find_similar_channels`, FR-2): accepts a channel ID, @handle or URL; scores channels from their keywords, topics and recent uploads.
- **Playlists** (`propose_playlist` and `create_playlist`, FR-5): plan a playlist of a given length, then create it as a **private** playlist only after a person confirms (the client asks the user, or `python -m ytmcp playlist confirm`). Writes are never retried. Clips under 3 minutes are left out unless asked for.
- **Recommendations** (`recommend_videos`, FR-3): a taste profile from your likes, subscriptions and playlists, with a reason for each result.
- **Engagement analysis** (`analyze_engagement`, FR-4): top channels and categories, a monthly trend of likes, duration preferences and a comparison of two periods. States that watch history is not used.
- **Google sign-in** (FR-6): OAuth with PKCE; read-only by default, write access only when asked for; tokens only in the operating system keyring.
- **Quota safety** (FR-7): a daily budget checked before any API call, saved across restarts, with a 500 unit reserve.
- **Command line** (UI-4): `auth`, `playlist confirm`, `quota status`, `serve` and `local-check`.
- **Skills**: `video-to-playlist` (SK-1), `local-check` (SK-2) and `brain-query`, `brain-ingest`, `brain-refine` (SK-3), each with test cases.
- **Local cache** in SQLite (24 hours for video details, 1 hour for searches, 6 hours for upload titles) and structured errors with a code, a message and a fix.
- **Documentation**: README, user guide, tool reference, design notes, decision records (ADR-001 to ADR-019), a defect log and a requirements trace, kept as an Obsidian vault in `docs/`, checked by `python scripts/brain.py check` in CI.
- **Tests**: more than 850 tests using fixtures only, coverage above 97% (the gate is 80%), checked in CI together with lint.

### Changed
- Internal layout simplified: settings and wiring in `config.py`, one `tools.py`, one `similarity.py`, all YouTube HTTP code in `providers/youtube.py`, and `database.py` for the SQLite file. No behavior changed.
- `min_video_minutes` now defaults to 3 (0 turns it off).

### Known limits
- Not built, by decision: scheduled live-API tests, Windows and macOS CI, automated performance checks.
- Likes beyond the newest 500 (engagement) or 250 (recommendations) are not read.
- Scoring weights are starting guesses and have not been tuned.
