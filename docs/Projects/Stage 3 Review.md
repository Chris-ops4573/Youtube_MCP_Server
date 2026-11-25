# Stage 3 Review

Stage 3 = Build and test. Deliverables from the SRS (section 6): tests, video-to-playlist, defect log. The plan that guided the work is [[Refactor and Feature Plan]]; the order of features is in [[Development Plan]].

## Deliverables
- [x] Tests (TQ-1 to TQ-6): 858 tests using fixtures only, coverage 97.97% (the gate is 80%), run in CI with lint. See [[Testing]]
- [x] `video-to-playlist` skill (SK-1): `.claude/skills/video-to-playlist/`, see [[Playlist]]
- [x] The brain skills and local-check were judged by a person on 2026-11-26; the `video-to-playlist` skill was run for real (terminal confirmation and decline both pass); the case that needs a client that asks the user is not run: see [[Skill Evaluations]]
- [x] Defect log (TQ-8): [[Defect Log]]
- [x] Release documents (SE-7): README, [[User Guide]], [[Tool Reference]] and the changelog
- [x] The brain check and the skill check pass in CI (SRS section 6): see [[Brain]]

## Requirements status
| Requirement | Status |
|---|---|
| FR-1 similar videos | Built and tried on the real API: [[Similarity]] |
| FR-2 similar channels | Built and tried on the real API: [[Channels]] |
| FR-3 recommendations | Built and tried on a real account (read-only): [[Recommendations]] |
| FR-4 engagement analysis | Built and tried on a real account (read-only): [[Engagement]] |
| FR-5 playlists | Built; a real private playlist was created and read back from YouTube: [[Playlist]] |
| FR-6 sign-in | Built, read-only by default, tokens only in the keyring: [[Auth]] |
| FR-7 quota and cache | Built; a daily budget checked before every request: [[Quota]], [[Cache]] |
| UI-1 to UI-4 | Built; the five command groups are in [[Auth]] |
| SK-1 to SK-4 | Written with test cases; a person still has to judge the skills: [[Skill Evaluations]] |
| TQ-5 live tests | Out of scope by decision (see below) |

The full row-by-row trace to code and tests is in [[Traceability]].

## TBDs due in Stage 3
| TBD | Question | Result |
|---|---|---|
| TBD-2 | Similarity weights | **Open.** Starting guesses (0.4, 0.2, 0.1, 0.05, 0.1, 0.15 for videos; 0.6 text, 0.25 keywords, 0.15 topics for channels; 0.6, 0.2, 0.2 for recommendations). Real runs gave sensible results but nothing was tuned |
| TBD-5 | Non-English tokenising | **Open.** The stop words are English only |
| TBD-6 | Quota reserve and maximum playlist length | **Assumed:** a 500 unit reserve and 24 hours, both enforced |
| TBD-7 | Team details on the SRS cover | **Open.** Needs a person |
| TBD-8 | Re-check API unit costs | **Open.** Needs a person to confirm in Google's Quota Calculator: see [[Quota]] |

## Known limitations
- **Not built, by decision:** scheduled live tests (TQ-5), Windows and macOS CI (SRS 5.4) and automated performance checks (SRS 5.1). Manual real measurements so far: similar videos about 2.4 s cold and 1.3 s warm; similar channels about 11 s cold; a playlist proposal about 1.4 s.
- Near-duplicate re-uploads of the same video can both appear in similar videos.
- The quota check is cautious: it counts the full cost even when the cache could answer some of it.
- Only the newest 500 likes (engagement) or 250 likes (recommendations) are read, and the output says when that cuts off a period.
- A client that answers questions automatically looks like a person to the server, so the confirmation is only as strong as the client.
- The newer MCP protocol version has no questions to the user, so there the confirmation always uses the terminal command.
- The terminal confirmation was tried in a real terminal with a real client, which cannot ask the user a question. A client that does ask has not been tried. The decline case of the `video-to-playlist` skill passed.
- Most recommendations are Shorts when most of a person's likes are Shorts. A minimum length for recommendations is possible later; it was not asked for.

## Skill evaluation status
Four skills were first checked by the assistant that wrote them (Stage 2), and again in Stage 3 with a person reading and judging the results. `video-to-playlist` was run with a real client for the terminal route and the decline case, and both passed; its client-question case cannot be tried with that client. The SRS wants a human to review AI-generated work (section 5.5): see [[Skill Evaluations]].

## What a person must do before Stage 4
1. Try the `video-to-playlist` case that needs a client that asks the user, if one is available, or leave it written down as not tried ([[Skill Evaluations]]).
2. Confirm the API unit costs (TBD-8) and fill in the team details (TBD-7).
3. Delete the private test playlists left on YouTube from the real tests.
4. Work through [[Stage 4 Checklist]].
