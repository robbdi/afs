from __future__ import annotations

import time
from pathlib import Path

import pytest

from afs.manager import AFSManager
from afs.mcp_server import _handle_request
from afs.schema import AFSConfig, GeneralConfig


def _make_manager(tmp_path: Path) -> AFSManager:
    context_root = tmp_path / "context"
    context_root.mkdir(parents=True)
    (context_root / "scratchpad").mkdir()
    general = GeneralConfig(
        context_root=context_root,
    )
    return AFSManager(config=AFSConfig(general=general))


@pytest.mark.slow
def test_context_query_auto_refresh_benchmark_smoke(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    context_root = manager.config.general.context_root
    scratchpad = context_root / "scratchpad"

    for index in range(300):
        (scratchpad / f"note_{index:04d}.md").write_text(
            f"benchmark corpus line {index}\nquery-marker-{index % 11}\n",
            encoding="utf-8",
        )

    rebuild_start = time.perf_counter()
    rebuild_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 20,
            "method": "tools/call",
            "params": {
                "name": "context.index.rebuild",
                "arguments": {
                    "context_path": str(context_root),
                    "mount_types": ["scratchpad"],
                },
            },
        },
        manager,
    )
    rebuild_seconds = time.perf_counter() - rebuild_start
    assert rebuild_response is not None
    assert rebuild_response["result"]["structuredContent"]["rows_written"] >= 300

    query_start = time.perf_counter()
    query_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 21,
            "method": "tools/call",
            "params": {
                "name": "context.query",
                "arguments": {
                    "context_path": str(context_root),
                    "mount_types": ["scratchpad"],
                    "query": "query-marker-3",
                    "limit": 40,
                    "auto_index": False,
                },
            },
        },
        manager,
    )
    query_seconds = time.perf_counter() - query_start
    assert query_response is not None
    assert query_response["result"]["structuredContent"]["count"] > 0

    (scratchpad / "note_0001.md").write_text("refresh-marker-from-external-write", encoding="utf-8")

    refresh_start = time.perf_counter()
    refresh_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 22,
            "method": "tools/call",
            "params": {
                "name": "context.query",
                "arguments": {
                    "context_path": str(context_root),
                    "mount_types": ["scratchpad"],
                    "query": "refresh-marker-from-external-write",
                    "auto_index": True,
                    "auto_refresh": True,
                },
            },
        },
        manager,
    )
    refresh_seconds = time.perf_counter() - refresh_start
    assert refresh_response is not None
    structured = refresh_response["result"]["structuredContent"]
    assert structured["count"] >= 1
    assert "index_rebuild" in structured
    assert refresh_seconds < max(10.0, (rebuild_seconds * 4.0) + 0.5)

    assert rebuild_seconds >= 0.0
    assert query_seconds >= 0.0
