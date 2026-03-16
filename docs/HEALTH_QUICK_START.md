# Health Quick Start

Use AFS health commands to diagnose profile/context/extension issues quickly.

## One-Command Snapshot

```bash
./scripts/afs health
```

This reports:

- active profile
- context path and mount counts
- mount health: broken symlinks, duplicate sources, missing profile-managed mounts
- monorepo bridge freshness
- embedding index age summary
- extension/hook status
- MCP status

## JSON Output

```bash
./scripts/afs health --json
```

## Extended Checks

```bash
./scripts/afs health check --level basic
./scripts/afs health check --level standard
./scripts/afs health check --level comprehensive
```

## Monitor Mode

```bash
./scripts/afs health monitor --interval 60
```

## History and Trend

```bash
./scripts/afs health history --limit 10
./scripts/afs health trend --hours 24
```

## Typical Workflow

1. Run `./scripts/afs health`.
2. If profile or mounts look wrong, run `./scripts/afs profile current` and `./scripts/afs context profile-show`.
3. If `mount_health` reports broken or missing managed mounts, run `./scripts/afs services start context-warm` or rerun `context-warm` with `--repair-profile-mounts`.
4. If SQLite index health is stale, rebuild with `./scripts/afs mcp serve` plus `context.index.rebuild`, or let the `context-warm` service handle it.
5. If monorepo bridge is stale, refresh `monorepo/active_workspace.toml` via workspace switch hook.
6. If MCP tools look wrong, check `./scripts/afs mcp serve` and extension `[mcp_tools]` config.
