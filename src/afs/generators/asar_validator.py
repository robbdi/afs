"""Compatibility shim for legacy module now owned by afs-scawful.

Domain-specific generators (ASM augment, ASAR, curriculum, knowledge)
"""

from __future__ import annotations

try:
    from afs_scawful.generators.asar_validator import *  # type: ignore[F403]
except Exception as exc:  # pragma: no cover - compatibility path
    raise RuntimeError(
        "Module 'afs_scawful.generators.asar_validator' moved to the afs-scawful extension. "
        "Install afs-scawful or add it to PYTHONPATH."
    ) from exc
