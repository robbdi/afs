"""Claude Code integration helpers for AFS."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def generate_claude_settings(
    project_path: Path,
    config: Any = None,
    *,
    config_path: Path | None = None,
    include_project_context: bool = True,
) -> dict[str, Any]:
    """Build the mcpServers.afs entry for Claude Code settings."""
    resolved_project = project_path.expanduser().resolve()
    env = _build_claude_runtime_env()
    if include_project_context:
        resolved_config_path = config_path or _find_project_config(resolved_project)
        if resolved_config_path is not None:
            env["AFS_CONFIG_PATH"] = str(resolved_config_path)
            env["AFS_PREFER_REPO_CONFIG"] = "1"
        if config is not None:
            context_root = getattr(getattr(config, "general", None), "context_root", None)
            if context_root:
                env["AFS_CONTEXT_ROOT"] = str(context_root)

    entry: dict[str, Any] = {
        "command": sys.executable,
        "args": ["-m", "afs.mcp_server"],
    }
    if env:
        entry["env"] = env
    return {"mcpServers": {"afs": entry}}


def default_claude_user_settings_path(home: Path | None = None) -> Path:
    """Return the default user-level Claude settings path."""
    home_dir = (home or Path.home()).expanduser()
    return home_dir / ".claude" / "settings.json"


def merge_claude_settings(existing: dict[str, Any], afs_entry: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge AFS MCP entry into existing Claude settings, preserving other servers."""
    merged = dict(existing)
    mcp_key = "mcpServers"
    if mcp_key not in merged:
        merged[mcp_key] = {}
    if not isinstance(merged[mcp_key], dict):
        merged[mcp_key] = {}
    else:
        merged[mcp_key] = dict(merged[mcp_key])
    merged[mcp_key]["afs"] = afs_entry.get(mcp_key, {}).get("afs", {})
    return merged


def generate_claude_md(project_name: str, context_path: str) -> str:
    """Generate project CLAUDE.md content with AFS bootstrap instructions."""
    return f"""# Claude Workspace Bootstrap

Use AFS (Agent File System) for context management in this project.

## Session Startup

Before major work:
1. Run `afs session bootstrap --json` or use the MCP prompt `afs.session.bootstrap`.
2. Read scratchpad state/deferred notes.
3. Check queued tasks and recent hivemind messages.
4. Use `context.query` before asking for already-known context.

## Context

- Project: {project_name}
- Context path: {context_path}

## Session Recovery

If Claude notices MCP sluggishness, session tool timeouts, repeated missing-tool errors, or obvious stale-session buildup:
1. Run `afs claude doctor --json` first to inspect session counts, bridge protection, and recent debug signals.
2. If cleanup is needed, run `afs claude reap --limit 20` as a dry-run before making changes.
3. Claude may run `afs claude reap --limit 20 --apply` to archive stale or zombie sessions in bounded batches.
4. Never reap `protected` sessions or any project with an active `bridge-pointer.json`.
5. Re-run `afs claude doctor --json` after each batch and stop once the blocking condition clears.

## Handoff Protocol

Before ending a session:
1. Use `handoff.create` to record accomplished work, blockers, and next steps.
2. Update scratchpad state if needed.
3. The next session's bootstrap will include the handoff automatically.
"""


def generate_hooks_config() -> dict[str, Any]:
    """Generate Claude Code hooks entry for logging tool calls to AFS history."""
    return {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "*",
                    "command": f"{sys.executable} -m afs events tail --limit 1 --json",
                }
            ]
        }
    }


def _find_project_config(project_path: Path) -> Path | None:
    search_root = project_path if project_path.is_dir() else project_path.parent
    for candidate in [search_root, *search_root.parents]:
        config_path = candidate / "afs.toml"
        if config_path.exists():
            return config_path
    return None


def _build_claude_runtime_env() -> dict[str, str]:
    env: dict[str, str] = {}
    repo_root = _discover_afs_repo_root()
    if repo_root is None:
        return env

    env["AFS_ROOT"] = str(repo_root)
    venv_dir = repo_root / ".venv"
    if venv_dir.exists():
        env["AFS_VENV"] = str(venv_dir)

    src_dir = repo_root / "src"
    if src_dir.exists():
        env["PYTHONPATH"] = str(src_dir)

    return env


def _discover_afs_repo_root() -> Path | None:
    module_path = Path(__file__).resolve()
    for candidate in module_path.parents:
        if (candidate / "scripts" / "afs").exists() and (candidate / "src" / "afs").exists():
            return candidate
    return None
