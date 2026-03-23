---
name: mcp-server
triggers:
  - mcp
  - serve
  - tool
  - protocol
profiles:
  - general
requires:
  - afs
---

# MCP Server

AFS exposes all context operations as MCP tools over stdio JSON-RPC.

## Starting

```bash
afs mcp serve                          # start MCP server
python -m afs.mcp_server              # direct stdio server entrypoint
python -m afs.mcp_server --demo       # demo mode with sample data
python -m afs.mcp_server --verbose    # debug logging to stderr
```

## Built-in Tools

### Context
- `context.discover` — find .context directories
- `context.init` — create .context for a path
- `context.mount` — mount a directory into context
- `context.unmount` — remove a mount
- `context.index.rebuild` — rebuild the context index
- `context.query` — search indexed context
- `context.diff` — diff context state
- `context.status` — show context health
- `context.repair` — fix broken context state

### Files
- `context.list` — preferred file listing
- `context.read` — preferred file read
- `context.write` — preferred file write
- `context.delete` — preferred file delete
- `context.move` — preferred file move/rename
- `fs.*` — legacy compatibility aliases for the same file operations

### Agents
- `agent.spawn` — start a background agent
- `agent.ps` — list running agents
- `agent.stop` — stop an agent
- `agent.logs` — read agent event history

### Communication
- `hivemind.send` — send an inter-agent message
- `hivemind.read` — read hivemind messages

### Tasks
- `task.create` — create a task
- `task.list` — list tasks
- `task.claim` — claim a task
- `task.complete` — complete a task

### Review
- `review.list` — list agents awaiting review
- `review.approve` — approve an agent's work
- `review.reject` — reject an agent's work

## Claude Code Integration

Add to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "afs": {
      "command": "/Users/scawful/src/lab/afs/.venv/bin/python",
      "args": ["-m", "afs.mcp_server"],
      "env": {
        "AFS_ROOT": "/Users/scawful/src/lab/afs",
        "AFS_VENV": "/Users/scawful/src/lab/afs/.venv",
        "PYTHONPATH": "/Users/scawful/src/lab/afs/src"
      }
    }
  }
}
```

Prefer the direct Python module entrypoint for Claude Desktop. The shell wrapper
can be fine for terminal use, but Claude Desktop has been more reliable when it
launches the venv Python directly.

If Claude logs show `initialize` followed by a 60 second timeout:

- inspect `~/Library/Logs/Claude/mcp-server-afs.log`
- look for `Message from client: {"method":"initialize"...}`
- if there is no matching `Message from server` response, switch to the direct
  Python config above and restart Claude Desktop with `Cmd+Q`

A stale `context_index` warning is non-blocking and should not be treated as
the cause of an MCP startup failure.
