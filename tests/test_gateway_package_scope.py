from __future__ import annotations

from afs.gateway import BackendConfig, BackendManager, ChatRequest


def test_gateway_package_exports_generic_backend_surfaces() -> None:
    manager = BackendManager(backends=[])

    assert isinstance(manager, BackendManager)
    assert BackendConfig is not None
    assert ChatRequest is not None
