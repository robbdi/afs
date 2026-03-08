"""Compatibility shim for the legacy gateway server now owned by afs-scawful."""

from __future__ import annotations

PERSONAS = {}
app = None
_IMPORT_ERROR: Exception | None = None

try:  # pragma: no cover - exercised via extension tests
    from afs_scawful.gateway_server import PERSONAS, app, run_server
except Exception as exc:  # pragma: no cover - compatibility path
    _IMPORT_ERROR = exc

    def run_server(*_args, **_kwargs):
        raise RuntimeError(
            "Legacy gateway server moved to the afs-scawful extension."
        ) from _IMPORT_ERROR
