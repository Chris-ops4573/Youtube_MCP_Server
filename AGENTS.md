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
python -m ytmcp auth login|status|logout   # Google sign-in (FR-6)
python scripts/brain.py check|search "words"|new adr "Title"   # the brain (notes + skills)
python scripts/local_check.py   # SK-2: build, lint, tests, server check
```

## Rules (from the SRS)
- All YouTube access goes through the provider interfaces in `src/ytmcp/providers/base.py`: VideoProvider (public data, API key) and PlaylistWriter (the user's account, login). (SE-6)
- Tools return errors as `{"error": {"code", "message", "remediation"}}`, never stack traces or secrets. (UI-3)
- Never write to a user's YouTube account without explicit confirmation. (FR-5.5) Only `create_playlist` writes, only after a person confirms (the client asks the user, or `python -m ytmcp playlist confirm <id>`). Never add an argument or any other way for the AI to confirm, never retry a write, never edit or delete, and create playlists private.
- No secrets or real user data in code, fixtures or logs. Never commit `.env`. (5.3)
- Cached data expires (24 h metadata, 1 h searches, 6 h upload titles); never store secrets or user data in the cache. (SRS 6)
- Google login tokens live only in the OS keyring. Never print, log, store in files/DB/cache, or put them in errors. (FR-6.2, 5.3)
- Ask for read-only access by default; write access only at the first confirmed playlist creation. (FR-6.1)
- Check quota with `provider.ensure_budget(...)` before any API calls. (FR-7.1)
- Tests use fixtures only, no live API calls. (TQ-5)
- Test coverage stays at or above 80%. (SRS 5.4)

## Brain (Obsidian vault in `docs/`)
- Read `docs/Index.md` first. Skills: `brain-query` (ask), `brain-ingest` (add), `brain-refine` (fix). See `docs/Areas/Brain.md`.
- `python scripts/brain.py check` must pass: CI runs it. Notes may not contain `TODO`.
- When you change code, update the related note in `docs/Areas/` and the row in `docs/Resources/Traceability.md`.
- If you change how the parts connect (new class, table, service or flow), update the diagrams in the `docs/Areas/Design *.md` notes too.
- Add one line to `docs/Log.md` for each change.
- New design decision -> new ADR in `docs/adr/` that cites at least one note with `[[wikilink]]`.
- Link notes with `[[wikilinks]]`.
- Brain changes go in the same PR as the code.
