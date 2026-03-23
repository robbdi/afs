# VSCode Extension Review Guardrails

Use this checklist for incoming AFS VSCode extension changes (Antigravity/Cursor context injection and MCP integration).

## Review Goals

- Keep extension behavior aligned with core AFS MCP contracts.
- Prevent duplicated logic for context discovery and mount resolution.
- Enforce baseline engineering quality before merge.

## Required Checks Per PR

1. Contract alignment:
   - Extension MCP calls use tool names and argument schemas from `docs/MCP_SERVER.md`.
   - Any MCP schema change in core AFS includes matching extension updates in the same PR (or linked PR).
2. Context safety:
   - No direct filesystem traversal outside AFS-allowed roots for context injection.
   - Context writes flow through supported MCP tools where possible (`context.write`, `context.move`, `context.delete`, with `fs.*` aliases only for compatibility).
3. Reliability:
   - Explicit timeout, retry, and error handling for MCP server startup and reconnects.
   - User-facing errors include actionable remediation (missing command, bad path, auth failure).
4. Code quality:
   - No hardcoded machine-specific paths.
   - No dead code or commented-out experimental blocks.
   - New modules include focused tests for failure modes.
5. Security:
   - No shell command execution from untrusted context payloads.
   - Any command invocation uses explicit allowlisted binaries/args.

## Drift Watchlist

- `src/afs/mcp_server.py` tool names/input schema.
- `docs/MCP_SERVER.md` examples and defaults.
- `src/afs/schema.py` `context_index` defaults (`auto_index`, limits, DB location).

If drift is detected, either:

1. Update extension implementation to current core contracts, or
2. Land an explicit contract update in core first, then adapt extension.

## Suggested Reviewer Split

1. Core reviewer: validates MCP/API contract and path safety.
2. Extension reviewer: validates VSCode UX, startup behavior, and test coverage.
3. Integrator reviewer: validates Antigravity/Cursor usage and context injection end-to-end.
