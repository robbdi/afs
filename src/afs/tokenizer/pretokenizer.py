"""Compatibility shim for legacy module now owned by afs-scawful.

65816 assembly tokenizer (semantic opcodes/addresses)
"""

from __future__ import annotations

try:
    from afs_scawful.tokenizer.pretokenizer import *  # type: ignore[F403]
except Exception as exc:  # pragma: no cover - compatibility path
    raise RuntimeError(
        "Module 'afs_scawful.tokenizer.pretokenizer' moved to the afs-scawful extension. "
        "Install afs-scawful or add it to PYTHONPATH."
    ) from exc
