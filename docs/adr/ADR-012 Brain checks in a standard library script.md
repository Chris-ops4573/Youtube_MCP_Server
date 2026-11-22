# ADR-012 Brain checks in a standard library script

Status: Accepted

## Context
The SRS asks for three brain skills (SK-3), valid `SKILL.md` files that cite a
brain note (SK-4), skill evaluations before each stage (TQ-7), and CI that
validates both the brain notes and the skills (SRS section 6). Skills are
written instructions, so on their own nothing checks that an agent followed
them or that the notes stay consistent.

## Decision
- Put the mechanical work in one script, `scripts/brain.py`, with three commands: `check`, `search` and `new`. The skills tell the agent to run it, so the steps are the same for every agent.
- Use only the standard library. CI runs `check` before installing anything, and a plain text search is predictable and easy to test.
- The same `check` is used by CI, `local-check` and `brain-refine`, so a clean result in one place means a clean result in all three.
- `new` writes `TODO` markers on purpose, and `check` rejects them, so a half-written note cannot be merged by accident.
- Each skill has an `evals.md` of at least 3 cases (prompt and expected result). `check` makes sure the file exists. People run the cases before each stage and record results in [[Skill Evaluations]].
- The script lives in `scripts/`, not in the `ytmcp` package: it is project tooling, not part of the server.

## Consequences
- Most failure modes of the brain are caught automatically: broken links, orphan notes, bad ADRs, bad log lines, notes naming files that no longer exist, and invalid skills.
- Search is word matching, not understanding. It finds notes by their words, so a question phrased with different words may need another try. The skill tells the agent to retry with other words.
- Whether an agent follows a skill well can only be judged by a person reading its answers. The evals make that judgement repeatable but do not automate it.
- `scripts/` is not counted by the coverage gate (`--cov=src`). It is tested in `tests/test_brain.py`.
- Notes that mention a file path in `backticks` must keep it up to date, or `check` fails. That is intended.

Cites: [[Brain]], [[Testing]]
