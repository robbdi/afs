"""Compatibility shim for legacy module now owned by afs-scawful.

Training utilities (ASM encoder, scoring, exporters, pipeline)
"""

from __future__ import annotations

try:
    from afs_scawful.training.codex_export import *  # type: ignore[F403]
except Exception as exc:  # pragma: no cover - compatibility path
    raise RuntimeError(
        "Module 'afs_scawful.training.codex_export' moved to the afs-scawful extension. "
        "Install afs-scawful or add it to PYTHONPATH."
    ) from exc
