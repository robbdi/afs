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
- `fs.list`
- `context.discover`
- `context.mount`

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
