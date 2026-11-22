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
| 2 | 2026-11-23 | brain-query | 1 to 5 | Claude, on a throwaway copy | Pass for the steps the script and notes control | Cases 1 to 3: the search found the right notes and they contain the expected facts (118 units; single-user and HTTP needs auth; keyring only and AUTH_REQUIRED). Case 4 showed a weakness: the search still listed unrelated notes. Fixed: it now prints `Not found in any note: deployed, kubernetes`. Case 5 is automatic. **A person still has to read real answers.** |
| 2 | 2026-11-23 | brain-refine | 1 to 5 | Claude, on a throwaway copy | Pass for the checker | Cases 1 to 3: each planted mistake (broken link, ADR without Cites, a clean vault) gave the right message and was cleared by the fix, with no edits when clean. Case 4: the unfinished note was flagged. Also caught a missing path and a bad log line. **A person must check that the agent asks instead of inventing text.** |
| 2 | 2026-11-23 | brain-ingest | 1, 2, 5 | Claude, on a throwaway copy | Pass for the script | Case 1: next number ADR-013, Index and Log updated, the check blocked it until filled in. Case 2: search found the Auth note, so a Glossary line was added and no new note was created. **Cases 3 and 4 (asks before archiving, no invented reasons) need a person.** |
| 2 | 2026-11-23 | local-check | 1 to 3 | Claude, on a throwaway copy | Pass | An unused import gave FAIL on lint only; a broken test gave FAIL on tests; the other steps still ran. Case 4 holds by design (`YTMCP_PROVIDER=fixture` is forced in the script) but quota use was not measured. |

## Before Stage 3 starts
- Cases marked "needs a person" have not been judged by anyone yet. Run them in a fresh session and update this table.
- This evaluation was done by the same assistant that wrote the skills, so it is a self-check, not an independent review (the SRS says a human reviews every AI-generated change, section 5.5).
