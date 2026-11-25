# Skill Evaluations

TQ-7: every skill is evaluated before each stage. This note holds the results. The cases are in each skill's `evals.md`:
`.claude/skills/<skill>/evals.md`. The skills and the checker are described in [[Brain]]; why it works this way is [[ADR-012 Brain checks in a standard library script]].

## How to evaluate
1. Work on a throwaway copy of the repo, so notes are not changed by accident.
2. Start a fresh Claude Code session. For each case, give the **Prompt** and compare what happens with **Expect**.
3. A person marks each case pass or fail and writes one line in the table below. Do not mark a case as passed for the agent.
4. A skill with a failed case must be fixed (the skill or the script) and run again before the stage starts.

Two kinds of cases:
- **Automatic:** the checker, the search and note creation are tested by `tests/test_brain.py`, which runs in CI.
- **By a person:** whether an agent follows the skill and answers well. Only a person reading the answers can judge that.

## Results
| Stage | Date | Skill | Cases | Run by | Result | Notes |
|---|---|---|---|---|---|---|
| 2 | 2026-11-23 | brain-query | 1 to 5 | Claude, on a throwaway copy | Pass for the steps the script and notes control | Cases 1 to 3: the search found the right notes and they contain the expected facts (118 units; single-user and HTTP needs auth; keyring only and AUTH_REQUIRED). Case 4 showed a weakness: the search still listed unrelated notes. Fixed: it now prints which words of the question appear in no note. Case 5 is automatic. **A person still has to read real answers.** |
| 2 | 2026-11-23 | brain-refine | 1 to 5 | Claude, on a throwaway copy | Pass for the checker | Cases 1 to 3: each planted mistake (broken link, ADR without Cites, a clean vault) gave the right message and was cleared by the fix, with no edits when clean. Case 4: the unfinished note was flagged. Also caught a missing path and a bad log line. **A person must check that the agent asks instead of inventing text.** |
| 2 | 2026-11-23 | brain-ingest | 1, 2, 5 | Claude, on a throwaway copy | Pass for the script | Case 1: next number ADR-013, Index and Log updated, the check blocked it until filled in. Case 2: search found the Auth note, so a Glossary line was added and no new note was created. **Cases 3 and 4 (asks before archiving, no invented reasons) need a person.** |
| 2 | 2026-11-23 | local-check | 1 to 3 | Claude, on a throwaway copy | Pass | An unused import gave FAIL on lint only; a broken test gave FAIL on tests; the other steps still ran. Case 4 holds by design (`YTMCP_PROVIDER=fixture` is forced in the script) but quota use was not measured. |
| 3 | 2026-11-26 | brain-query | 1 to 5 | Claude ran the cases on a throwaway copy; Chris read the transcripts and judged them | Pass | Cases 1 to 3 and 5 pass. Case 4 as written was faulty: its question's words had ended up in a note (this table), so the search could not report them as missing. The question was replaced by one about a technology the notes never mention, which gave the expected "not covered" answer. Also seen: with a full sentence as the query the expected note was 5th, not 1st (it is 1st for "why stdio only"). |
| 3 | 2026-11-26 | brain-ingest | 1 to 5 | same | Pass | New decision note numbered correctly with a real Context, Decision, Consequences and a Cites line; a glossary entry was added to an existing note instead of making a new one; the skill asks before moving to the Archive and before inventing a reason. The script's automatic Log line names the git user, not "Chris" (cosmetic). |
| 3 | 2026-11-26 | brain-refine | 1 to 5 | same | Pass | A broken link and an ADR without Cites were each reported and fixed with no other note changed; a clean vault needed no edits and no Log line; an unfinished note was reported, not filled with invented text. |
| 3 | 2026-11-26 | local-check | 1 to 4 | same | Pass | PASS on a clean copy with no files changed; an unused import gave FAIL on lint only; a broken assert gave FAIL on tests while the other steps still ran; with an API key present only fixtures are used. No real key was tried, so no real request was observed either way. |
| 3 | 2026-11-26 | video-to-playlist | 3 | Chris, with a real client (Claude Code in VS Code) and a real account | Pass | The client cannot ask the user a question, so the server answered with the terminal route. The AI did not confirm for the user. Chris ran `python -m ytmcp playlist confirm` in a real terminal, typed yes, and the private playlist was created. A second run with "30 minutes, English only, no video longer than 10 minutes" gave 30 min, 10 min and English settings and a 33 minute playlist of 5 videos. |
| 3 | 2026-11-26 | video-to-playlist | 2 | Chris, with a real client (Claude Code in VS Code) and a real account | Pass | When shown the proposal the user said no: nothing was created and `create_playlist` was not called. |
| 3 | 2026-11-26 | video-to-playlist | 1 | not run | Not run | Needs a client that asks the user a question: Claude Code in VS Code does not, so it cannot be tried with it. |
| 3 | 2026-11-26 | video-to-playlist | 4, 5 | Claude, on fixtures only | Not judged by a person | Case 4: a bad link gave INVALID_VIDEO_REFERENCE with the message and the fix. Case 5 (asks for a length) needs a real session. |

## Where this stands
- Every case that a script or a command decides has been run, and a person has judged the results of the brain skills and local-check.
- The cases that need a real client are only partly done: see the video-to-playlist rows. The client in use cannot ask the user a question, so that route stays untried. The decline case passed. Cases 4 and 5 were only run by the assistant (case 4 on fixtures).
- Every playlist made during the real tests was created only after a person confirmed it in a terminal. The test playlists still have to be deleted on YouTube by the person.
- An observation from the real run (not a defect in the server): the starting video can appear in its own playlist, filling most of its length. The skill could leave it out, or say so; this has not been changed.
- This evaluation was run by the same assistant that wrote the skills, and a person judged the written results, so it is a check, not an independent review (the SRS asks for a human review of AI-generated work, section 5.5).
