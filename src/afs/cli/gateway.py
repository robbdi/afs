"""Compatibility shim for legacy gateway commands now owned by afs-scawful."""

from __future__ import annotations

import argparse


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register gateway parsers from afs-scawful when available."""
    try:
        from afs_scawful.gateway_cli import register_parsers as extension_register_parsers
    except Exception as exc:  # pragma: no cover - compatibility path
        raise RuntimeError(
            "Legacy gateway commands moved to the afs-scawful extension."
        ) from exc
    extension_register_parsers(subparsers)
