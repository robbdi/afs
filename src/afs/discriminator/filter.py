"""Compatibility shim for legacy module now owned by afs-scawful.

ASM-ELECTRA discriminator for assembly quality
"""

from __future__ import annotations

try:
    from afs_scawful.discriminator.filter import *  # type: ignore[F403]
except Exception as exc:  # pragma: no cover - compatibility path
    raise RuntimeError(
        "Module 'afs_scawful.discriminator.filter' moved to the afs-scawful extension. "
        "Install afs-scawful or add it to PYTHONPATH."
    ) from exc
