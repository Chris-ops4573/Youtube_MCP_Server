# Development Plan

SE-4. What gets built, in what order, and how we work. Stage deliverables come from the SRS (section 6). Status of every requirement is in [[Traceability]].

## Stages
| Stage | Deliverables | Status |
|---|---|---|
| 1 Requirements | SRS, vault with 10+ notes, AGENTS.md, CI | done, see [[Stage 1 Review]] |
| 2 Design | Design docs, brain-refine, brain-query, local-check | built; the TBD-8 cost check and the skill evaluations were finished in Stage 3, see [[Stage 2 Review]] and [[Stage 3 Review]] |
| 3 Build and test | Tests, video-to-playlist, defect log | built; waiting on a person to judge the skill evals, see [[Stage 3 Review]] |
| 4 Release | Live demo, release tag | checklist written, see [[Stage 4 Checklist]]; the tag is created by a person |

## Features, in planned order
| Order | Feature | Needs | Status |
|---|---|---|---|
| 1 | FR-1 similar videos | API key | done |
| 2 | FR-7 quota and cache | none | done |
| 3 | FR-2 similar channels | API key | done |
| 4 | FR-6 OAuth sign-in | OAuth client | done (core) |
| 5 | FR-3 recommendations | FR-6 | built and tried on a real account |
| 6 | FR-5 playlist creation (UI-2) | FR-6, write scope | built and tested for real |
| 7 | FR-4 engagement analysis | FR-6 | built and tried on a real account |
| 8 | SK-1 video-to-playlist | FR-5 | built; run with a real client (terminal confirmation and decline pass); one eval needs a client that asks the user |
| 9 | Rest of the CLI (UI-4) | none | built |
| 10 | SK-3 brain skills, CI note and skill checks | none | done |

FR-5 is the riskiest (the server must enforce confirmation before any write), so it gets the most review and negative tests. See [[Design Sequences]].

## Branching strategy
- `main` always passes CI. Nobody pushes to it directly.
- **One branch per feature**, made from an up-to-date `main`:
  - `feat/<name>` for code, for example `feat/oauth-core`
  - `docs/<name>` for documentation only, for example `docs/stage-2-design`
  - `fix/<name>` for bug fixes
- Open a **pull request** into `main`. CI must be green and another team member should review it before merging.
- Delete nothing that was merged without asking the team.

## Every pull request
- Short, standard commit messages, for example `feat: add similar channels tool`, `docs: add design notes`, `test: add auth tests`.
- Code, tests and brain changes go together in the same PR (see AGENTS.md).
- Before pushing, run `python scripts/local_check.py` (it includes the brain check) and `git status`, so no file is left out of the commit.
- CI runs lint, the brain and skills check, tests with at least 80% coverage, and a secret scan.
- Every new defect gets a row in [[Defect Log]] and a regression test (TQ-8).

