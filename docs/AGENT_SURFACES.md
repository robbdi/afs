# Agent Surfaces (CLI + MCP)

AFS is CLI-first. The built-in MCP server is the preferred structured tool
surface for Gemini, Antigravity, and other MCP-aware clients.

## Preferred Entry Point

Use the repo wrapper during local development:

```bash
~/src/lab/afs/scripts/afs status
```

Why:

- it sets `AFS_ROOT`
- it adds repo `src/` to `PYTHONPATH`
- it avoids relying on whichever `python` happens to be first on `PATH`

Use the installed `afs` entrypoint only after `pip install -e .` into the
environment the agent actually runs in.

Help:

- `~/src/lab/afs/scripts/afs`
- `~/src/lab/afs/scripts/afs help <command>`
- `~/src/lab/afs/scripts/afs <command> --help`

## Shell Setup

For interactive shells:

```bash
source ~/src/lab/afs/scripts/afs-shell-init.sh
```

This exports:

- `AFS_ROOT`
- `AFS_CLI`
- `PATH` including `~/src/lab/afs/scripts`

## Venv Setup

Bootstrap a repo-local venv:

```bash
~/src/lab/afs/scripts/afs-venv
```

Optional extras:

```bash
AFS_VENV_EXTRAS=test ~/src/lab/afs/scripts/afs-venv
```

For non-interactive agents:

```bash
export AFS_CLI=~/src/lab/afs/scripts/afs
export AFS_VENV=~/src/lab/afs/.venv
```

## Useful Agent Commands

```bash
~/src/lab/afs/scripts/afs context discover --path ~/src
~/src/lab/afs/scripts/afs context ensure-all --path ~/src
~/src/lab/afs/scripts/afs profile current
~/src/lab/afs/scripts/afs skills list --profile work
~/src/lab/afs/scripts/afs health
```

Warm context/cache:

```bash
~/src/lab/afs/scripts/afs-warm
```

Agent contract:

- `~/.context/AFS_SPEC.md`
- `./AGENTS.md`
- `./docs/PROFILES.md`

## MCP

Run the built-in stdio MCP server:

```bash
~/src/lab/afs/scripts/afs mcp serve
```

Built-in tools:

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

Paths are scoped to:

- `~/.context`
- configured `general.context_root`
- local project `.context`

`context.init` is intended for Gemini-style project bootstrap:

- local project init when the target project is under the current working directory
- explicit `context_root` under an allowed root for centralized/shared contexts

Gemini-friendly prompts/resources are also exposed over MCP:

- prompts: `afs.context.overview`, `afs.query.search`, `afs.scratchpad.review`
- resources: `afs://contexts`, `afs://context/<path>/metadata`, `.../mounts`, `.../index`

## Gemini / Antigravity Registration

Recommended command target:

```bash
~/src/lab/afs/scripts/afs mcp serve
```

Antigravity raw config example:

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

If the client requires a Python module entrypoint instead, use a Python
environment where `afs` is installed and run `python3 -m afs.mcp_server`.
