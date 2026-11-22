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
python -m ytmcp.server   # run the MCP server (uses test fixtures for now)
```

## Rules (from the SRS)
- All YouTube access goes through `VideoProvider` (`src/ytmcp/providers/base.py`). (SE-6)
- Tools return errors as `{"error": {"code", "message", "remediation"}}`, never stack traces or secrets. (UI-3)
- Never write to a user's YouTube account without explicit confirmation. (FR-5.5)
- No secrets or real user data in code, fixtures or logs. (5.3)
- Tests use fixtures only, no live API calls. (TQ-5)

## Brain (Obsidian vault in `docs/`)
- Read `docs/Index.md` first.
- When you change code, update the related note in `docs/Areas/` and the row in `docs/Resources/Traceability.md`.
- Add one line to `docs/Log.md` for each change.
- New design decision -> new ADR in `docs/adr/` that cites at least one note with `[[wikilink]]`.
- Link notes with `[[wikilinks]]`.
- Brain changes go in the same PR as the code.
