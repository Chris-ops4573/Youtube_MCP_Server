# ADR-009 Stdio transport only

Status: Accepted (settles TBD-4)

## Context
The SRS says transport to the AI client is stdio by default and leaves HTTP
open (TBD-4, needed by Stage 2).

## Decision
Release 1.0 supports **stdio only**. The AI client starts the server as a
local process (`python -m ytmcp.server`).

## Consequences
- The server is single-user by design: one person's YouTube API key, Google login, OS keyring and cache. An HTTP server would need its own authentication and per-user token handling, which is a large security risk for little gain.
- Only local MCP clients can use it. Hosting it for others is out of scope.
- Revisit only if the project needs remote use, and then add authentication first.

Cites: [[Design Components]], [[Auth]]
