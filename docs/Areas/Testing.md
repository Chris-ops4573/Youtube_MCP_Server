# Testing

How we check the project works.

## Tests
- `pytest` runs unit and tool tests in `tests/`.
- Tests use fixtures only (`tests/fixtures/*.json` via `FixtureProvider`), no live API calls (TQ-5). See [[Providers]].
- Coverage must be at least 80% (SRS 5.4). CI fails below that (`--cov-fail-under=80`).

## CI (`.github/workflows/ci.yml`)
Runs on every PR to `main`: ruff lint, pytest with the coverage gate, gitleaks secret scan.

## local-check skill (SK-2)
- Skill: `.claude/skills/local-check/SKILL.md`
- Script: `python scripts/local_check.py` (or `python -m ytmcp local-check`, which runs it)
- Steps, each reported PASS/FAIL:
  1. build - the `ytmcp` package imports
  2. lint - `ruff check .`
  3. brain - `python scripts/brain.py check` validates the notes and skills (see [[Brain]])
  4. tests - pytest with the 80% coverage gate
  5. server - starts `python -m ytmcp.server` over stdio and calls `find_similar_videos`, `describe_video`, `find_similar_channels` and `propose_playlist` on fixture data (never `create_playlist`, and with a throwaway database), and checks that `recommend_videos` and `analyze_engagement` are registered (they are not called: they need a real account)
- Exits with code 1 if any step fails.

Part of [[Architecture]].
