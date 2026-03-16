# AFS MCP Server

AFS provides a lightweight stdio MCP server for context operations.

## Run

```bash
~/src/lab/afs/scripts/afs mcp serve
# or, from an environment where `afs` is installed
afs mcp serve
# or
python3 -m afs.mcp_server
```

## Gemini CLI Registration

```bash
gemini mcp add afs /Users/scawful/src/lab/afs/scripts/afs mcp serve
```

If Gemini is running inside an environment where `afs` is already installed,
`python3 -m afs.mcp_server` also works.

## Antigravity Custom Config

In Antigravity, open `MCP Servers -> Manage MCP Servers -> View raw config`, then add:

```json
{
  "mcpServers": {
    "afs": {
      "command": "/Users/scawful/src/lab/afs/scripts/afs",
      "args": ["mcp", "serve"]
    }
  }
}
```

## Tools

- `fs.read`
- `fs.write`
- `fs.delete`
- `fs.move`
- `fs.list`
- `context.discover`
- `context.init`
- `context.mount`
- `context.unmount`
- `context.index.rebuild`
- `context.query`

`context.query` uses a SQLite index with FTS ranking when available, and falls
back to `LIKE` matching if FTS is unavailable on the host SQLite build.
`fs.write`, `fs.delete`, and `fs.move` attempt incremental index sync so query
results stay fresh without a full rebuild. With `auto_index=true` (default),
`context.query` also auto-refreshes when it detects stale file-level snapshots
(count/mtime mismatch).

Index behavior can be tuned in `afs.toml`:

```toml
[context_index]
enabled = true
db_filename = "context_index.sqlite3"
auto_index = true
auto_refresh = true
include_content = true
max_file_size_bytes = 262144
max_content_chars = 12000
```

Extensions can register additional tools via `extension.toml`:

```toml
[mcp_tools]
module = "afs_google.mcp_tools"
factory = "register_mcp_tools"
```

Path operations are scoped to:

- `~/.context`
- configured `general.context_root`
- local project `.context` under the current working directory

## Example Call Shape

`tools/call` expects:

```json
{
  "name": "fs.read",
  "arguments": {
    "path": "~/.context/scratchpad/notes.md"
  }
}
```

Rebuild and query the SQLite context index:

```json
{
  "name": "context.query",
  "arguments": {
    "context_path": "~/.context",
    "mount_types": ["scratchpad", "knowledge"],
    "query": "Gemini",
    "limit": 20,
    "auto_index": true
  }
}
```
