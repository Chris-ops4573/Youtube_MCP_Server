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
- Script: `python scripts/local_check.py`
- Steps, each reported PASS/FAIL:
  1. build - the `ytmcp` package imports
  2. lint - `ruff check .`
  3. tests - pytest with the 80% coverage gate
  4. server - starts `python -m ytmcp.server` over stdio and calls `find_similar_videos` on fixture data
- Exits with code 1 if any step fails.

Part of [[Architecture]].
