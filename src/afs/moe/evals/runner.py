"""Compatibility shim for legacy MoE evaluation runner now owned by afs-scawful."""

from __future__ import annotations

try:
    from afs_scawful.moe.evals.runner import *  # type: ignore[F403]
except Exception as exc:  # pragma: no cover - compatibility path
    raise RuntimeError(
        "Legacy MoE evaluation runner moved to the afs-scawful extension."
    ) from exc
