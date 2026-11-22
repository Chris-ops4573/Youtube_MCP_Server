# ADR-008 Python 3.11 and libraries

Status: Accepted (settles TBD-1)

## Context
The SRS assumes Python 3.11+ with the MCP SDK and leaves the language and
libraries open (TBD-1, needed by Stage 2). The server must run on Windows,
macOS and Linux (SRS 5.4), and CI runs Python 3.11 on Ubuntu.

## Decision
- **Python 3.11 is the minimum.** CI tests 3.11; development has used 3.13.
- Libraries (all in `requirements.txt`, with version limits):
  - `mcp` for the MCP server
  - `scikit-learn` for TF-IDF and cosine similarity ([[ADR-002 Metadata similarity]])
  - `python-dotenv` for `.env`
  - `keyring` for token storage ([[ADR-007 OAuth with PKCE and keyring]])
  - `tzdata` so Pacific time works on Windows ([[Quota]])
  - `pytest`, `pytest-cov`, `ruff` for development and CI
- Everything else uses the standard library: HTTP (`urllib`), database (`sqlite3`), time zones (`zoneinfo`), the local web server (`http.server`).

## Consequences
- Few dependencies, and tests replace the network with a function passed in, so no HTTP-mocking library is needed.
- New code must work on 3.11 (for example, no features added in 3.12 or later).
- CI only runs Ubuntu. Windows and macOS are not tested yet (see [[Development Plan]]).

Cites: [[Testing]], [[Requirements]]
