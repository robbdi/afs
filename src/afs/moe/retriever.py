"""Compatibility shim for legacy MoE module now owned by afs-scawful."""

from __future__ import annotations

try:
    from afs_scawful.moe.retriever import *  # type: ignore[F403]
except Exception as exc:  # pragma: no cover - compatibility path
    raise RuntimeError(
        "Legacy MoE module 'retriever' moved to the afs-scawful extension."
    ) from exc
