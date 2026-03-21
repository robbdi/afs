# ROADMAP

## Current State

AFS now has a usable core operator loop:

- repo-local and shared `.context` roots
- typed mount roles with remapping support
- profile and extension loading
- SQLite-backed context indexing and query
- MCP tools/prompts/resources for Gemini, Codex, Claude, and other clients
- background maintenance agents (`context-warm`, `context-watch`, `agent-supervisor`, `history-memory`)
- session bootstrap, task queue, hivemind, review, and durable memory consolidation
- `afs doctor` for operator-facing diagnostics and repair

## Priority Next

1. Real service installation and lifecycle management
   `launchd` and `systemd` adapters still mainly render units. AFS should be
   able to install, enable, disable, tail logs, and reconcile services without
   dropping to raw system commands.

2. MCP/server refactor
   `src/afs/mcp_server.py` is too large. Split transport, built-in tools,
   prompts/resources, extension loading, and diagnostics into separate modules.

3. Model-aware context pack builder
   Build context packets for Gemini/Claude/Codex with token budgeting,
   deduplication, retrieval ranking, and citations instead of relying only on
   raw bootstrap plus manual query steps.

4. Better agent observability
   Extend `afs status` / `afs health` to show what agents produced, what is
   awaiting review, what is stale, and whether clients are actually using the
   bootstrap/status/diff workflow.

5. Stronger sensitivity controls
   Add explicit path-level rules for "never index", "never embed", and "never
   export", especially for governed work roots such as `/google`.

## Maintenance Rules

- Prefer tightening the operational core over adding more surface area.
- New public surfaces should reuse existing context/path/policy resolution.
- Docs should describe the current operator workflow, not a historical one.
