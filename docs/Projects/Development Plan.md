# Development Plan

SE-4. What gets built, in what order, and how we work. Stage deliverables come from the SRS (section 6). Status of every requirement is in [[Traceability]].

## Stages
| Stage | Deliverables | Status |
|---|---|---|
| 1 Requirements | SRS, vault with 10+ notes, AGENTS.md, CI | done, see [[Stage 1 Review]] |
| 2 Design | Design docs, brain-refine, brain-query, local-check | in progress, see [[Stage 2 Review]] |
| 3 Build and test | Tests, video-to-playlist, defect log | not started |
| 4 Release | Live demo, release tag | not started |

## Features, in planned order
| Order | Feature | Needs | Status |
|---|---|---|---|
| 1 | FR-1 similar videos | API key | done |
| 2 | FR-7 quota and cache | none | done |
| 3 | FR-2 similar channels | API key | done |
| 4 | FR-6 OAuth sign-in | OAuth client | done (core) |
| 5 | FR-3 recommendations | FR-6 | not started |
| 6 | FR-5 playlist creation (UI-2) | FR-6, write scope | not started |
| 7 | FR-4 engagement analysis | FR-6 | not started |
| 8 | SK-1 video-to-playlist | FR-5 | not started |
| 9 | Rest of the CLI (UI-4) | none | not started |
| 10 | SK-3 brain skills, CI note and skill checks | none | not started |

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
- Before pushing, run `python scripts/local_check.py` and `git status`, so no file is left out of the commit.
- CI runs lint, tests with at least 80% coverage, and a secret scan.

## Who does what
The team has three members. Each member should author brain notes and open pull requests (SB). Fill in who owns which feature here as it is assigned:

| Feature | Owner |
|---|---|
| FR-3 | |
| FR-4 | |
| FR-5 | |
| Skills | |
