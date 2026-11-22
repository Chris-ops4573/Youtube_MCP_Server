---
name: local-check
description: Check the project works locally - build, lint, run tests with the 80% coverage gate, start the MCP server and call find_similar_videos - and report pass or fail per step. Use before opening a PR or when asked to check that everything works.
---

# local-check (SK-2)

Runs the SK-2 steps from the SRS and reports PASS or FAIL for each one.

## Steps
1. From the repo root, run:
   ```bash
   source .venv/bin/activate
   python scripts/local_check.py
   ```
2. Report the PASS/FAIL line for each step to the user:
   - **build**: the `ytmcp` package imports
   - **lint**: `ruff check .`
   - **tests**: `pytest` with coverage of at least 80% (TQ, SRS 5.4)
   - **server**: starts `python -m ytmcp.server` over stdio and calls the read-only `find_similar_videos` and `find_similar_channels` tools on fixture data
3. If a step fails, show its output and suggest a fix. Do not change code unless the user asks.

Uses fixtures only, no live YouTube calls and no quota (TQ-5).

Brain note: [[Testing]] (`docs/Areas/Testing.md`)
