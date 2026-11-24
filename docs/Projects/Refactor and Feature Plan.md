# Refactor and Feature Plan

The plan for cleaning up the source code and finishing the remaining SRS features. It is written so a smaller model can follow it task by task without guessing, and so the team can explain every part in a viva. The final design is explained on one page in [[Architecture Overview]]. Decisions are recorded in [[ADR-015 Simple module layout and one-way imports]], [[ADR-016 One AccountProvider for the signed-in user]], [[ADR-017 Recommendations from a taste profile]] and [[ADR-018 Engagement analysis sources and periods]]. How we work (branches, pull requests, commit messages) is in [[Development Plan]].

## Why
The code works: 648 tests pass at 96.95% coverage, and all four MCP tools have been tried against real YouTube. But the source grew feature by feature and has become busy, and the remaining SRS features (FR-3, FR-4, SK-1, the rest of UI-4 and the SE-7 documents) are not built. The goal is the simplest layout that follows our guidelines, with one clear job per file, and then the missing features on top of it. **Prefer deleting over adding.**

## Answered questions
| Question | Decision |
|---|---|
| How far should the cleanup go? | Moderate: fix the wrong-direction imports, and merge a few files. No new layers. |
| Rename cache.py? | Yes: database.py, and the class Cache becomes Database. It also holds the quota count and the proposals. |
| How should FR-3 and FR-4 read the user's account? | One AccountProvider interface for everything done as the signed-in user. |
| Which optional SRS items get tasks? | FR-4 only. Scheduled live tests, Windows and macOS CI, and automated performance checks are known limitations. |
| Should min_video_minutes have a default? | Yes: 3 minutes. The value 0 turns it off. |
| How much does FR-3 read per request? | 250 likes, 200 subscriptions and 10 playlists (127 quota units). |
| How are FR-4 periods given? | period_months (the last N months) plus compare (the N months before). |
| What does the implementer do with git? | Only commit. The user pushes, opens and merges the pull request, then says "continue". |

## Working rules for whoever implements this
1. Do **one task** at a time. Then stop, give the user the push command, and wait for "continue".
2. Start each task from fresh main: `git checkout main && git pull --ff-only origin main && git checkout -b <branch>`.
3. Before committing, run all of these: `ruff check .`, `python scripts/brain.py check`, `python scripts/local_check.py`, and `git status` (nothing important left untracked).
4. Commit with exactly the message given for the task. **No AI attribution and no Co-Authored-By line** (the user's standing rule).
5. Refactor tasks (R1 to R6) must not change behavior: only import lines in tests may change, the test count stays the same (except R6, which deletes the empty smoke test), and coverage stays at or above 80%.
6. Follow AGENTS.md: every pull request updates the related Areas note, the Traceability rows and one Log line, plus an ADR where the task names one.
7. Notes may never contain the word `TODO` outside code formatting (the brain check fails). Code-formatted file paths that contain a slash must exist (the brain check fails otherwise). Write future or deleted paths without code formatting, or as a bare file name such as `config.py`.
8. If the code and these documents disagree, stop and tell the user. Do not pick one.

## Audit: what each module does today
| Module | What it does |
|---|---|
| server.py | Registers the 4 MCP tools, asks the user to confirm a playlist (elicitation), **and** builds all the objects (wiring) |
| cli.py | The `auth login`, `status`, `logout` and `playlist confirm` commands; also builds the auth service and the proposal store |
| __main__.py | Runs cli.main |
| cache.py | The one SQLite file: cache tables, the quota ledger, the proposals table, and `default_cache_path()` |
| quota.py | API unit costs and the daily budget |
| models.py | `Video` and `Channel` |
| errors.py | Every error, with its code and remediation |
| ids.py | Video and channel references (IDs, URLs, handles) |
| durations.py | ISO 8601 durations to seconds |
| similarity.py | Video scoring (TF-IDF plus other signals) |
| channel_similarity.py | Channel scoring (imports helpers from similarity.py) |
| playlist_planner.py | Validates playlist settings and chooses videos (pure) |
| proposals.py | The Proposal model, the content hash, and ProposalStore |
| services: similar_videos, similar_channels, playlists | The steps of FR-1, FR-2 and FR-5. The package __init__ re-exports names |
| tools: similar_videos, similar_channels, playlists | Formatting for the AI client. The package __init__ re-exports names |
| providers: base | The VideoProvider and PlaylistWriter interfaces |
| providers: youtube | Live reads with the API key (retried) |
| providers: playlists | Live writes with the user's login (never retried) |
| providers: caching | The cache wrapper |
| providers: fixture | Sample data for tests |
| auth (oauth, pkce, loopback, tokens, service) | Google sign-in and token storage. Cohesive: keep as it is |

## Audit: findings
**Dead code.** There is almost none. The only unused functions are framework callbacks (the MCP tool functions and the HTTP handler methods). The one pointless file is tests/test_smoke.py, which only asserts `True`.

**Imports that point the wrong way.**
- server.py lazily imports cli.py (to build the auth service).
- The channel and playlist tool files import shared helpers (`error_response`, `format_duration`, `video_url`, `MAX_TOP_N`) from the video tool file.
- Configuration (`default_cache_path`) lives in cache.py.

**Files that do several jobs.**
- server.py: registration, plus wiring, plus the elicitation question.
- cache.py: the cache, plus the quota ledger, plus the proposals. The name is misleading.

**Overlap.**
- Two scoring files, where one imports helpers from the other.
- The playlist writer module copies `API_URL`, `QUOTA_REASONS` and the error-reason helper from the YouTube reader module.
- Two re-export `__init__.py` files give two import paths for each name.
- playlist_planner.py, proposals.py and the playlists service are **not** duplicates: they are the rules, the storage and the steps. Keep them.

**Documents that disagree with the code** (fixed in task R6):
1. The Architecture and Design Components notes say server.py "registers tools, nothing else".
2. The Architecture note omits every playlist module, describes the CLI as auth-only, and lists ADRs only up to 007.
3. AGENTS.md, the Requirements note (SI-1) and ADR-001 say all YouTube access goes through VideoProvider, but writes use PlaylistWriter.
4. The Traceability note: the SE-3 row says "ADR-001 to ADR-011" (there are 14 at the time of writing); the FR-7.1 row omits the channel and playlist services; the UI-4 row says "auth part only".
5. AGENTS.md lists cache expiry without the 6 hour upload titles.
6. The Development Plan says Stage 3 is "not started", although FR-5 (Stage 3 work) is built.

**Intentional deviation** (already in [[ADR-013 Playlist creation needs a person's confirmation]]): writes are never retried, which narrows SRS 3.4.

**SRS status.**
| Status | Requirements |
|---|---|
| Done | FR-1, FR-2, FR-5, FR-6, FR-7, UI-1, UI-2, UI-3, SK-2, SK-3, SK-4, SE-2 to SE-6, SB, TQ-1, TQ-4, TQ-6, TQ-7 |
| Partial | UI-4 (auth and playlist confirm only), TQ-2 and TQ-3 (FR-1, FR-2, FR-5 only), SE-7 (no README, user guide or changelog), TBD-2, TBD-6, TBD-7, TBD-8 |
| Missing | FR-3, FR-4, SK-1, TQ-8 (defect log), the Stage 3 and Stage 4 reviews, the release |
| Out of scope by decision | TQ-5 scheduled live tests, 5.4 Windows and macOS CI, 5.1 automated performance checks |

## Target structure
Imports only point **down** this list.

```
server.py   cli.py        entry points (server never imports cli;
   \         /            cli imports server only inside its serve command)
   config.py              reads .env and builds the objects for both entry points; imports neither
tools.py                  (server only) argument checks, result formatting, error dictionaries
services/                 similar_videos, similar_channels, playlists, recommendations, engagement
similarity.py  playlist_planner.py  proposals.py  quota.py     pure logic and storage helpers
providers/ (base, youtube, caching, fixture)   auth/          YouTube and Google access
database.py               the one SQLite file: cache tables, quota count, proposals (all the SQL)
models.py  errors.py  ids.py  durations.py                     import nothing from the layers above
```

Two interfaces live in providers: base.py: **VideoProvider** for public data (API key) and **AccountProvider** for the signed-in user's data (login).

## Mapping: current file to target
| Current | Target |
|---|---|
| server.py | server.py keeps create_server, ask_user, ConfirmPlaylist and main. The builders move to config.py |
| cli.py | cli.py. build_auth_service and build_store move to config.py |
| (none) | config.py (new) |
| cache.py | database.py with the class Database. default_cache_path moves to config.py |
| similarity.py and channel_similarity.py | similarity.py |
| the tools package (4 files) | tools.py |
| providers: playlists | merged into providers: youtube |
| services: __init__ | empty (re-exports removed) |
| tests/test_smoke.py | deleted |
| tests/test_cache.py | tests/test_database.py |
| tests/test_playlist_writer.py | tests/test_youtube_account.py (in task F1) |
| every other file | unchanged |

## Tasks
Each task is one branch and one pull request. Order: documentation first, then the refactor, then features, then the closing documents.

| ID | Branch | Depends on |
|---|---|---|
| D0 | docs/refactor-plan | nothing (this note) |
| R1 | fix/config-wiring | D0 |
| R2 | fix/tools-module | R1 |
| R3 | fix/similarity-module | R2 |
| R4 | fix/youtube-provider-module | R1 |
| R5 | fix/database-rename | R1, R4 |
| R6 | fix/cleanup-and-doc-sync | R2, R3, R5 |
| F1 | feat/account-provider | R4, R5 |
| F2 | feat/recommendations | F1 |
| F3 | feat/engagement | F1 |
| F4 | feat/video-to-playlist | R6 |
| F5 | feat/cli-commands | R5 |
| D1 | docs/defect-log | D0 |
| D2 | docs/release-docs | F5 |
| D3 | docs/stage-3-review | everything else |

Acceptance for every R and F task: tests pass (R tasks with only import lines changed, F tasks with new tests added), coverage stays at or above 80%, `python scripts/local_check.py` passes, `python scripts/brain.py check` passes, and the notes named in the task are updated in the same pull request.

### D0: write this plan into the brain
Branch docs/refactor-plan. Commit: `docs: add refactor and feature plan`. No change under src/ or tests/.
- Create this note, [[Architecture Overview]], and ADR-015 to ADR-018.
- Update the Index and the Log.
- Acceptance: the brain check passes, local_check passes, and `git diff --stat main` lists only files under docs/.

### R1: move object wiring into config.py
Branch fix/config-wiring. Commit: `refactor: move object wiring into config.py`.
1. Create src/ytmcp/config.py with a docstring saying it reads settings and builds objects for server.py and cli.py and imports neither. Move these in verbatim:
   - `default_cache_path` (from cache.py)
   - `_default_fixtures_dir`, renamed `default_fixtures_dir`
   - `build_provider`
   - `_access_token`, renamed `access_token`, now calling this module's `build_auth_service` with no lazy import
   - `Services` and `build_services` (from server.py)
   - `build_auth_service` and `build_store` (from cli.py)
2. server.py: `main()` uses `config.build_services`. Delete the moved code and the now-unused imports. Keep `create_server`, `ask_user` and `ConfirmPlaylist`.
3. cli.py: import `build_auth_service` and `build_store` from config.
4. cache.py: remove `default_cache_path` and any unused imports.
5. Tests, import lines only: test_server.py takes `build_provider` from config; test_playlist_server.py takes `build_services` from config, uses `config.access_token` instead of `server_module._access_token`, and monkeypatches `ytmcp.config.build_auth_service`. Search the tests for any other use.
- Acceptance: 648 tests pass; neither server.py nor config.py imports cli (`grep -n "cli" src/ytmcp/server.py src/ytmcp/config.py`); `python -m ytmcp.server` starts (local_check step 5).
- Notes: the Architecture and Design Components tables (add a config.py row, and change server.py to "registers tools and asks the user"), and the Log.

### R2: merge the tools package into tools.py
Branch fix/tools-module. Commit: `refactor: merge the tools package into tools.py`.
1. Create src/ytmcp/tools.py. Copy the bodies verbatim into four sections:
   1. Shared: `MAX_TOP_N`, `video_url`, `channel_url`, `playlist_url`, `format_duration`, `error_response`.
   2. Videos: `format_results`, `similar_videos_tool`.
   3. Channels: `format_channel_results`, `similar_channels_tool`.
   4. Playlists: `Answer`, `AskUser`, `UNTRUSTED_NOTICE`, `_error`, `format_proposal`, `propose_playlist_tool`, `confirmation_message`, `format_created`, `create_playlist_tool`.
2. Run `git rm -r src/ytmcp/tools`, then delete any leftover `__pycache__` folders, so the old package cannot shadow the new module.
3. server.py: `from ytmcp.tools.playlists import Answer` becomes `from ytmcp.tools import Answer`. In tests/test_playlist_tools.py, `UNTRUSTED_NOTICE` comes from `ytmcp.tools`.
- Acceptance: all tests pass; `python -c "import sys; sys.path.insert(0,'src'); import ytmcp.tools as t; print(t.__file__)"` prints a path ending in tools.py.
- Notes: replace every code-formatted path into the old tools package (the brain check lists them) in Traceability (UI-1, UI-3, FR-2.3, FR-5.1, FR-5.5, UI-2), Architecture, Design Components, Errors, Playlist and Channels. Add a Log line.

### R3: merge channel scoring into similarity.py
Branch fix/similarity-module. Commit: `refactor: merge channel scoring into similarity.py`.
1. Append the whole of channel_similarity.py to similarity.py under the heading comment `# --- channels (FR-2.2, FR-2.3) ---`. Drop the imports that are now local, and update the module docstring.
2. Delete channel_similarity.py. Update the imports in services: similar_channels, tools.py and tests/test_channel_similarity.py.
- Notes: Similarity (add a channels section), Channels (the Files line), Traceability (FR-2.2 and FR-2.3), the Architecture and Design Components rows, and the Log.

### R4: keep all YouTube HTTP code in providers: youtube
Branch fix/youtube-provider-module. Commit: `refactor: keep all YouTube HTTP code in providers/youtube.py`.
1. Move `PostJson`, `urllib_post_json` and `YouTubePlaylistWriter` into providers: youtube.
2. Use the existing `_error_reason`, `API_URL` and `QUOTA_REASONS` there, and delete the writer's copies.
3. Rename `TIMEOUT_SECONDS` to `READ_TIMEOUT_SECONDS` (10) and add `WRITE_TIMEOUT_SECONDS` (15), so behavior is identical. Search the tests for `TIMEOUT_SECONDS`.
4. Update the module docstring: reads use the API key and are retried; writes use the login and are never retried.
5. Delete providers: playlists. Update the imports in config.py, tests/test_playlist_writer.py and tests/test_playlist_server.py.
- Notes: Providers, Playlist (the Files line), Traceability (FR-5.6, FR-6.1, SRS 5.2), and the Log.

### R5: rename cache.py to database.py
Branch fix/database-rename. Commit: `refactor: rename cache.py to database.py`.
1. `git mv src/ytmcp/cache.py src/ytmcp/database.py` and `git mv tests/test_cache.py tests/test_database.py`.
2. Rename the class `Cache` to `Database`. Find every use with `grep -rnw "Cache" src tests` (whole word, so `CachingProvider` and variables named cache are untouched). Replace `ytmcp.cache` with `ytmcp.database`.
3. **Keep the parameter and attribute names** (`cache=` on QuotaTracker and CachingProvider, `self._cache`), so no test logic changes.
4. In conftest.py, the `close_caches` fixture imports `ytmcp.database` and patches `Database.__init__`.
5. server.py: the default store uses `Database(":memory:")`.
- Notes: Cache (file and class names), Design Data, Design Classes, Quota, Playlist ("Where proposals live"), Traceability (FR-7.1, FR-7.2, FR-5.4), Architecture and Design Components, and the Log.

### R6: remove the barrel, the smoke test, and the documents that disagree
Branch fix/cleanup-and-doc-sync. Commits: `refactor: remove re-export barrel and empty smoke test`, then `docs: fix notes that disagree with the code`.
1. Delete tests/test_smoke.py.
2. Reduce services: __init__ to a docstring only. tools.py and the tests test_similar_videos.py, test_similar_channels.py and test_caching_provider.py import from the concrete services modules.
3. Fix the six disagreements listed in the audit:
   - AGENTS.md rule SE-6: "through the provider interfaces in providers: base: VideoProvider (public data, API key) and PlaylistWriter (the user's account, login)".
   - AGENTS.md cache expiry: add "6 h upload titles".
   - Traceability: the SE-3 row says "every ADR is listed in the [[Index]]"; the FR-7.1 row adds the similar_channels and playlists services; the UI-4 row says "auth and playlist confirm".
   - Development Plan: Stage 3 becomes "in progress (FR-5 built)".
   - Architecture: a short final layer table plus a link to [[Architecture Overview]].
   - Requirements, SI-1: append "(writes: see [[Playlist]])".
   - The Providers note explains the second interface. ADRs are history: do not edit ADR-001.
- Acceptance: 647 tests (one fewer: the smoke test).

### F1: AccountProvider, with reads
Branch feat/account-provider. Commits: `refactor: rename PlaylistWriter to AccountProvider`, then `feat: read likes, subscriptions and playlists with the user's login`. See [[ADR-016 One AccountProvider for the signed-in user]].
1. Renames (behavior identical):
   - `PlaylistWriter` becomes `AccountProvider` (base.py).
   - `YouTubePlaylistWriter` becomes `YouTubeAccount`.
   - The `writer` parameter or attribute becomes `account` in the playlists service, tools.py, server.py and config.py (`Services.writer` becomes `Services.account`).
   - In tests/fake_playlists.py, `FakeWriter` becomes `FakeAccount`.
   - `git mv tests/test_playlist_writer.py tests/test_youtube_account.py`.
2. models.py: add `LikedVideo(video_id: str, liked_at: str)` and `Subscription(channel_id: str, title: str, subscribed_at: str | None)`.
3. Add abstract methods to AccountProvider:
   - `liked_videos(limit) -> list[LikedVideo]`, newest first
   - `subscriptions(limit) -> list[Subscription]`
   - `playlist_video_ids(max_playlists) -> set[str]`
4. YouTubeAccount reads. The token comes from `get_token(SCOPE_READONLY)`; an AuthRequiredError passes through unchanged and becomes AUTH_REQUIRED.
   - Likes: `channels.list part=contentDetails mine=true` (1 unit) gives `relatedPlaylists.likes`; if it is missing, return an empty list. Then `playlistItems.list part=snippet,contentDetails maxResults=50`, following `pageToken` until `limit` is reached (1 unit per page). The video ID is `contentDetails.videoId` and the date is `snippet.publishedAt`. Skip "Private video" and "Deleted video".
   - Subscriptions: `subscriptions.list part=snippet mine=true maxResults=50` with paging. The channel ID is `snippet.resourceId.channelId`.
   - Playlists: `playlists.list part=id mine=true maxResults=min(max_playlists,50)` (1 unit), then one `playlistItems.list part=contentDetails maxResults=50` per playlist (1 unit each).
5. Add an optional `headers=None` argument to `urllib_fetch` (default behavior unchanged).
6. Extract the retry loop of YouTubeProvider into a module function `_get_with_retries(fetch, url, method, quota, sleep)` used by both. YouTubeProvider's behavior must stay identical: the existing tests prove it.
7. COSTS: add `"subscriptions.list": 1` and `"playlists.list": 1`, and update tests/test_quota.py.
- Tests: paging with `nextPageToken`; the limit is respected; private and deleted items are skipped; no likes playlist; the read scope is requested; AUTH_REQUIRED passes through; a 503 read is retried; quota is counted per page.
- Notes: Providers, Auth, Design Classes, Design Components, Playlist wording, AGENTS.md rule SE-6 (now AccountProvider), Quota, a new Traceability row for reading the account (FR-3.1), and the Log. Set ADR-016's status as accepted.

### F2: FR-3 recommendations
Branch feat/recommendations. Commit: `feat: add recommend_videos tool (FR-3)`. See [[ADR-017 Recommendations from a taste profile]].
- New: services: recommendations; in similarity.py `TasteProfile`, `build_taste_profile`, `rank_for_profile` and `DEFAULT_TASTE_WEIGHTS = {"text": 0.6, "category": 0.2, "channel": 0.2}`; in tools.py `recommend_videos_tool`; in server.py the tool `recommend_videos(top_n: int = 10)`; in errors.py `AccountUnavailableError` (code ACCOUNT_NOT_AVAILABLE, used in fixture mode where there is no account) and `NotEnoughHistoryError` (code NOT_ENOUGH_HISTORY).
- Constants: `LIKES_CAP=250`, `SUBSCRIPTIONS_CAP=200`, `PLAYLISTS_CAP=10`, `SEARCH_SIZE=50`, `TOP_TERMS=3`, `MIN_LIKES_FOR_CONFIDENCE=5`.
- `estimate_cost()` = 1 (channels) + 5 (likes pages) + 4 (subscription pages) + 1 (playlists) + 10 (playlist items) + 5 (liked video details) + 100 (search) + 1 (candidate details) = **127 units**.
- Steps:
  1. `provider.ensure_budget(127)` before any call. The quota is shared with the account through config.
  2. Read the user's likes, subscriptions and playlist video IDs.
  3. If there are no likes and no subscriptions, raise NOT_ENOUGH_HISTORY.
  4. `provider.get_videos(liked ids)` (this uses the cache).
  5. Build the taste profile: `text` is the liked titles plus tags; `top_terms` are the 3 most common words of 3 or more letters from titles and tags, excluding sklearn's `ENGLISH_STOP_WORDS`, with ties broken alphabetically (if there are no liked videos, use subscription titles); `category_share` maps category_id to its share of likes; `channel_ids` are the liked channels plus the subscribed channels.
  6. `search_videos(" ".join(top_terms), 50)`.
  7. Drop videos that are liked, already in a playlist, or duplicates (FR-3.3).
  8. Score = 0.6 x TF-IDF cosine (profile text against candidate) + 0.2 x category share + 0.2 x (1 if the channel is in the profile). Sort by score descending, then by ID.
  9. One reason per result, the first that applies: "From a channel you like or subscribe to: X"; "Matches your interests: a, b" (top terms found in the title); "In a category you like often (N% of your likes)" (when the share is 0.2 or more); "Similar to videos you liked".
  10. `low_confidence` is true when there are fewer than 5 likes.
- Tool output: `results` (rank, title, channel, duration, score, url, reason, score_breakdown), `based_on` (likes, subscriptions, playlists_checked), `low_confidence`. Errors go through `error_response`; no account gives ACCOUNT_NOT_AVAILABLE.
- Tests: exclusions and every reason branch; the budget check happens before any account call (FakeAccount records calls); AUTH_REQUIRED and NOT_ENOUGH_HISTORY; the caps are passed exactly; stop words are excluded; deterministic order; the tool output shape; the server tool list and local_check expect `recommend_videos` (local_check only checks that it is registered and does not call it).
- Notes: a new Recommendations area note, ADR-017 set to accepted, Traceability (FR-3.1 to FR-3.3), Quota, Design Sequences (a new diagram), Design Components, the Index and the Log.

### F3: FR-4 engagement analysis
Branch feat/engagement. Commit: `feat: add analyze_engagement tool (FR-4)`. See [[ADR-018 Engagement analysis sources and periods]].
- New: services: engagement (pure statistics functions plus the steps); `VideoProvider.category_names(region="US") -> dict[str, str]` (YouTubeProvider: `videoCategories.list part=snippet regionCode`, 1 unit; CachingProvider: pass through; FixtureProvider: reads an optional tests/fixtures/categories.json, otherwise returns an empty dictionary); COSTS gets `"videoCategories.list": 1`; in tools.py `analyze_engagement_tool`; in server.py the tool `analyze_engagement(sources: list[str] | None = None, period_months: int = 12, compare: bool = False)`.
- Arguments: `sources` is a subset of likes, subscriptions and playlists (default: all three). `period_months` is 1 to 60. Invalid arguments give INVALID_ARGUMENT with `fields`, and no API call is made.
- Caps: 500 likes, 200 subscriptions, 10 playlists. Estimate = 1 + 10 + 4 + 1 + 10 + 10 (liked details) + 10 (playlist video details) + 1 (categories) = **47 units**, checked first.
- Pure functions:
  - `top_counts(names, n=10)` returns a list of name, count and share; the share is rounded to 3 places; ties are ordered by name.
  - `monthly_trend(liked, months, now)`: the last N UTC months, zero-filled, from `liked_at`.
  - `duration_buckets(videos)`: under 5 min (below 300 s), 5 to 20 min (below 1200 s), 20 to 60 min (below 3600 s), over 60 min.
  - `compare_periods`: the last N months against the N before, using only liked videos inside each window.
- Output: `sources`, `period_months`, `top_channels`, `top_categories` (names from `category_names`), `monthly_trend` with a `date_field` of "date liked (snippet.publishedAt of the likes playlist)", `duration_preferences`, `comparison` (only when compare is true), `totals`, and a `note` of "Based on your likes, subscriptions and playlists only. YouTube does not share watch history." (FR-4.4).
- Tests: shares and ties; zero-filled months and month boundaries; bucket edges at 300, 1200 and 3600 seconds; the compare windows; the note is present; invalid arguments make no API call; the budget is checked first; ACCOUNT_NOT_AVAILABLE and AUTH_REQUIRED; category names are used; the server tool list.
- Notes: a new Engagement area note, ADR-018 set to accepted, Traceability (FR-4.1 to FR-4.4), Quota, the Design notes, the Index and the Log.

### F4: video-to-playlist
Branch feat/video-to-playlist. Three commits.
1. `feat: default min_video_minutes to 3`
   - `validate_constraints`: when `min_video_minutes` is not given, use 3 if it is no more than `total_minutes` and no more than `max_video_minutes` (when that is set); otherwise use none. Accept **0 as "no minimum"** (the validation range becomes 0 to total).
   - The short-clip warning now appears only when 0 was given. Update the tool docstring.
   - Update the tests whose expected behavior changes on purpose: the default-None and warning tests in test_playlist_planner.py and test_playlist_tools.py (the `mixed()` cases) pass `min_video_minutes=0` where they expect clips.
   - A new decision record, ADR-019 "Leave out short clips by default".
2. `feat: add describe_video tool`
   - In the similar_videos service: `describe_video(provider, video_ref) -> Video` extracts the ID, calls `ensure_budget(1)`, calls `get_videos`, and raises VIDEO_NOT_FOUND if it is missing.
   - tools.py: `describe_video_tool` returns title, channel, duration, the first 10 tags, category_id, language, description (`clean_text`, at most 500 characters), url and is_live, plus `UNTRUSTED_NOTICE`. Register it in server.py.
   - local_check: add it to `EXPECTED_TOOLS` and call it with the fixture ID `aaaaaaaaaaa`.
3. `feat: add video-to-playlist skill (SK-1)`
   - Create .claude/skills/video-to-playlist with a SKILL.md whose steps are: (1) `describe_video`, then summarise from metadata only; (2) `find_similar_videos`; (3) `propose_playlist` with the topic taken from the title and tags, asking the user for the length if they have not given one, then show the proposal and ask; (4) `create_playlist`, where the server asks the user (with the terminal fallback) and the skill never confirms for the user; (5) a short analysis of the number of videos, the total against the requested length, the channel mix and what was left out. It ends with `Brain note: [[Playlist]]`.
   - An evals.md with at least 3 cases: the happy path, the user declines, a client without elicitation, and an invalid URL.
   - Skill Evaluations gets a Stage 3 row, "not yet run by a person".
- Notes: Playlist, Brain (now 5 skills), Testing (local_check), Traceability (SK-1), and the Log.

### F5: the rest of the CLI (UI-4)
Branch feat/cli-commands. Commit: `feat: add quota status, serve and local-check commands (UI-4)`.
- `python -m ytmcp quota status`: today's date in Pacific time, the units used of 10,000, the reserve, the units left, and the time until midnight Pacific. It reads the ledger through `QuotaTracker(cache=Database(default_cache_path()))`. The clock is injectable. Note that it only counts calls made by this server.
- `python -m ytmcp serve`: inside the handler, `from ytmcp import server`, then `server.main()`.
- `python -m ytmcp local-check`: runs `[sys.executable, "scripts/local_check.py"]` from the repo root and returns its exit code. If the script is missing, print a clear error and exit with 1. The runner is injectable.
- Tests: each command, using a temporary database, a fixed clock and patched callables.
- Notes: Traceability (UI-4 done), Testing, Quota, Auth (the command list), the Development Plan (item 9), and the Log.

### D1: defect log (TQ-8)
Branch docs/defect-log (any time after D0). Commit: `docs: add defect log`.
Create a Defect Log note under Projects with the columns ID, date, how it was found, what was wrong, the fix, and the regression test. Rows:
1. local_check used `result.isError`, but MCP 2.x calls it `is_error`.
2. The channel topic order changed between calls, which broke the cache and gave 0 results. Test `test_query_is_stable_when_topic_order_changes`.
3. The channel search query included the title. Test `test_build_channel_query_uses_only_top_keywords`.
4. The OAuth client was in a different Cloud project (an environment problem, no test: see the Auth setup steps).
5. A commit was missing its tests and the keyring requirement, so CI coverage fell to 67.89% (a process fix: run `git status` before pushing).
6. A second `playlist confirm` asked again and then failed. Test `test_confirming_twice_just_says_it_is_already_confirmed_and_does_not_ask_again`.
7. The unknown-language note counted videos that were not selected. Test `test_known_wrong_language_is_dropped_but_unknown_is_kept_and_mentioned`.
8. The confirm command opened the database before checking for a terminal. Test `test_a_refused_run_does_not_even_open_the_database`.
9. The brain search listed unrelated notes for a question the notes could not answer. The `test_unmatched_terms_*` tests.
10. Playlist proposals were full of Shorts. The `min_video_minutes` tests.
Add a rule to the Development Plan: every new defect gets a row and a regression test. Update the Index and the Log.

### D2: release documents (SE-7)
Branch docs/release-docs (after F5). Commit: `docs: add README, user guide, tool reference and changelog`.
- README.md: what the project is; setup (virtual environment, requirements, .env with the API key and the OAuth client, `auth login` and `auth login --write`); the MCP client configuration snippet (a .mcp.json file whose command is `.venv/bin/python -m ytmcp.server` with `PYTHONPATH=src`); example prompts for each tool; the CLI commands; local-check; where the documents are.
- A User Guide note under Resources: plain steps, example conversations, and what each error means (link [[Errors]]).
- A Tool Reference note under Resources: for each tool its purpose, its arguments with ranges, its output fields, its errors, its quota cost, and whether it reads or writes.
- CHANGELOG.md: a 1.0.0 "Added" list built from the Log, plus an Unreleased section.
- Update the Index, the Log, and Traceability (SE-7).

### D3: Stage 3 review and release checklist
Branch docs/stage-3-review (last). Commit: `docs: add Stage 3 review and release checklist`.
- A Stage 3 Review note under Projects: the deliverables (tests, video-to-playlist, defect log), the status of each FR, the known limitations, and the skill evaluation status.
- A Stage 4 checklist: a live demo script, and the tag `v1.0.0`, which **the user** creates and pushes.
- Update the Development Plan stage statuses, the Index and the Log.

## Known limitations
- **Not built, by the user's choice:** scheduled live tests (TQ-5), Windows and macOS CI (5.4), and automated performance checks (5.1). Manual real measurements so far: FR-1 cold about 2.4 s and warm about 1.3 s; FR-2 cold about 11 s; playlist proposals about 1.4 s.
- **Open TBDs:** TBD-2 (the similarity weights are untuned), TBD-5 (stop words are English only), and TBD-7 and TBD-8, which need a person.
- FR-1 can return near-duplicate re-uploads of the same video.
- The quota pre-check assumes full cost even when the answer is cached.
- A client that answers the confirmation question automatically looks like a person to the server.
- The newer 2026 MCP protocol cannot ask mid-call, so it always uses the terminal confirmation.
- The terminal confirmation has not been tried in a real terminal.

## How each kind of task is verified
- **D tasks:** the brain check passes, local_check passes (5 steps), and `git diff --stat main` lists only files under docs/ (plus README.md and CHANGELOG.md in D2).
- **R tasks:** the same test count (R6 has one fewer), coverage of at least 80%, local_check and the brain check pass, and only import lines change in tests.
- **F tasks:** the new tests pass, coverage stays at or above 80%, local_check passes (the tool lists are updated), and the brain check passes.
- **Real-API checks** are optional and need the user's go-ahead (they use quota and the real account): F2 recommendations, F3 engagement and F4 describe_video.
