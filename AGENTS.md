# AGENTS.md

Instructions for AI coding agents working in this repo.

## Project
YouTube Video Intelligence MCP Server. An AI client calls our MCP tools; the
server uses YouTube Data API v3 (official API only). Full spec:
`docs/requirements/` (SRS). Requirement IDs (FR-1, UI-3, SE-6, ...) are listed
in `docs/Resources/Requirements.md`.

## Commands
```bash
source .venv/bin/activate
pip install -r requirements.txt
pytest            # run tests
ruff check .      # lint
cp .env.example .env    # then add your YOUTUBE_API_KEY
python -m ytmcp.server   # run the MCP server (YTMCP_PROVIDER=fixture for sample data)
python scripts/local_check.py   # SK-2: build, lint, tests, server check
```

## Rules (from the SRS)
- All YouTube access goes through `VideoProvider` (`src/ytmcp/providers/base.py`). (SE-6)
- Tools return errors as `{"error": {"code", "message", "remediation"}}`, never stack traces or secrets. (UI-3)
- Never write to a user's YouTube account without explicit confirmation. (FR-5.5)
- No secrets or real user data in code, fixtures or logs. Never commit `.env`. (5.3)
- Cached data expires (24 h metadata, 1 h searches); never store secrets or user data in the cache. (SRS 6)
- Check quota with `provider.ensure_budget(...)` before any API calls. (FR-7.1)
- Tests use fixtures only, no live API calls. (TQ-5)
- Test coverage stays at or above 80%. (SRS 5.4)

## Brain (Obsidian vault in `docs/`)
- Read `docs/Index.md` first.
- When you change code, update the related note in `docs/Areas/` and the row in `docs/Resources/Traceability.md`.
- Add one line to `docs/Log.md` for each change.
- New design decision -> new ADR in `docs/adr/` that cites at least one note with `[[wikilink]]`.
- Link notes with `[[wikilinks]]`.
- Brain changes go in the same PR as the code.
