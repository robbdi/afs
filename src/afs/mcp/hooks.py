"""Built-in MCP tool hooks for sensitivity enforcement and audit logging."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any


def sensitivity_pre_hook(arguments: dict[str, Any], manager: Any) -> dict[str, Any]:
    """Block tool calls that touch paths matching sensitivity rules.

    Checks ``never_index`` and ``never_export`` patterns from
    ``SensitivityConfig`` against the path/mount_type/alias arguments.
    Raises ``PermissionError`` if a match is found.
    """
    sensitivity = manager.config.sensitivity
    blocked_patterns = sensitivity.never_index + sensitivity.never_export
    if not blocked_patterns:
        return arguments

    # Collect path-like values from arguments
    path_values: list[str] = []
    for key in ("path", "source", "destination", "alias", "relative_path"):
        val = arguments.get(key)
        if isinstance(val, str) and val.strip():
            path_values.append(val.strip())

    # Check mount_type + alias compound path
    mount_type = arguments.get("mount_type", "")
    alias = arguments.get("alias", "")
    if isinstance(mount_type, str) and isinstance(alias, str) and alias.strip():
        path_values.append(f"{mount_type}/{alias}")

    for pattern in blocked_patterns:
        for path_val in path_values:
            if fnmatch.fnmatch(path_val, pattern) or fnmatch.fnmatch(
                Path(path_val).name, pattern
            ):
                raise PermissionError(
                    f"Blocked by sensitivity rule: path '{path_val}' "
                    f"matches pattern '{pattern}'"
                )

    return arguments


# Names of tools that should have the sensitivity pre-hook applied.
SENSITIVITY_TOOL_NAMES = frozenset({
    "fs.read",
    "fs.write",
    "fs.delete",
    "fs.move",
    "fs.list",
    "context.read",
    "context.write",
    "context.delete",
    "context.move",
    "context.list",
    "context.query",
    "embeddings.index",
})
