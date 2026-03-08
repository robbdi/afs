"""Compatibility shim for legacy module now owned by afs-scawful.

Domain-specific benchmark runners (Din, Nayru, Farore, Veran)
"""

from __future__ import annotations

try:
    from afs_scawful.benchmark.nayru import *  # type: ignore[F403]
except Exception as exc:  # pragma: no cover - compatibility path
    raise RuntimeError(
        "Module 'afs_scawful.benchmark.nayru' moved to the afs-scawful extension. "
        "Install afs-scawful or add it to PYTHONPATH."
    ) from exc
