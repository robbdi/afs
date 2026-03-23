"""Helpers for building reliable local MCP server launch entries."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Literal

MCPLaunchMode = Literal["python-module", "wrapper"]


def discover_afs_repo_root(module_path: Path | None = None) -> Path | None:
    """Return the local AFS repo root when running from a source checkout."""
    candidate_path = (module_path or Path(__file__).resolve()).resolve()
    for candidate in candidate_path.parents:
        if (candidate / "scripts" / "afs").exists() and (candidate / "src" / "afs").exists():
            return candidate
    return None


def build_afs_runtime_env(
    *,
    prefer_repo_config: bool = False,
    config_path: Path | None = None,
    context_root: Path | None = None,
) -> dict[str, str]:
    """Build environment variables needed by local MCP server launches."""
    env: dict[str, str] = {}
    repo_root = discover_afs_repo_root()
    if repo_root is not None:
        env["AFS_ROOT"] = str(repo_root)
        venv_dir = repo_root / ".venv"
        if venv_dir.exists():
            env["AFS_VENV"] = str(venv_dir)
        src_dir = repo_root / "src"
        if src_dir.exists():
            env["PYTHONPATH"] = str(src_dir)

    if prefer_repo_config:
        env["AFS_PREFER_REPO_CONFIG"] = "1"
    if config_path is not None:
        env["AFS_CONFIG_PATH"] = str(config_path.expanduser().resolve())
    if context_root is not None:
        env["AFS_CONTEXT_ROOT"] = str(context_root.expanduser().resolve())
    return env


def build_afs_mcp_entry(
    mode: MCPLaunchMode = "python-module",
    *,
    cwd: Path | None = None,
    prefer_repo_config: bool = False,
    config_path: Path | None = None,
    context_root: Path | None = None,
) -> dict[str, Any]:
    """Build a stdio MCP entry for local AFS usage."""
    env = build_afs_runtime_env(
        prefer_repo_config=prefer_repo_config,
        config_path=config_path,
        context_root=context_root,
    )

    entry: dict[str, Any]
    if mode == "wrapper":
        repo_root = discover_afs_repo_root()
        if repo_root is not None:
            entry = {
                "command": str(repo_root / "scripts" / "afs"),
                "args": ["mcp", "serve"],
            }
        else:
            mode = "python-module"

    if mode == "python-module":
        entry = {
            "command": sys.executable,
            "args": ["-m", "afs.mcp_server"],
        }

    if env:
        entry["env"] = env
    if cwd is not None:
        entry["cwd"] = str(cwd.expanduser().resolve())
    return entry
