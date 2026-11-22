# ADR-003 Structured errors

Status: Accepted

## Context
UI-3 says errors must give a stable code, a plain message and a remediation,
never stack traces or secrets.

## Decision
Services raise `ValueError` or `YtmcpError` (which has a `code`). The tool
layer catches them and returns `{"error": {code, message, remediation}}`.
Tool logic is plain functions, separate from the MCP SDK, so it is easy to test.

## Consequences
- The AI client always gets a predictable shape.
- Each new error type needs a code and a remediation message.

Cites: [[Errors]], [[Architecture]]
