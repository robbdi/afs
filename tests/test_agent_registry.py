from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from afs.agent_registry import AgentRegistry, agent_registry_path, resolve_agent_task
from afs.agents.base import AgentResult, emit_result


def test_resolve_agent_task_uses_core_agent_description() -> None:
    task = resolve_agent_task("context-warm")
    assert task.startswith("Sync workspace paths")


def test_agent_registry_updates_and_prunes_old_entries(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    registry = AgentRegistry()

    stale_time = (datetime.now() - timedelta(days=3)).isoformat()
    registry.path.parent.mkdir(parents=True, exist_ok=True)
    registry.path.write_text(
        json.dumps(
            [
                {
                    "name": "stale-agent",
                    "task": "old",
                    "status": "success",
                    "last_output_at": stale_time,
                }
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    registry.mark_started(
        name="context-warm",
        module="afs.agents.context_warm",
        task="Warm contexts",
        pid=4321,
    )
    registry.mark_result(
        name="context-warm",
        status="ok",
        task="Warm contexts",
        output_path=str(tmp_path / "context_warm.json"),
    )

    entries = registry.entries()
    assert len(entries) == 1
    entry = entries[0]
    assert entry["name"] == "context-warm"
    assert entry["status"] == "ok"
    assert entry["task"] == "Warm contexts"
    assert entry["output_path"].endswith("context_warm.json")
    assert "pid" not in entry


def test_emit_result_updates_global_agent_registry(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    output_path = tmp_path / "reports" / "context_audit.json"

    result = AgentResult(
        name="context-audit",
        status="ok",
        started_at="2026-03-19T08:00:00",
        finished_at="2026-03-19T08:00:05",
        duration_seconds=5.0,
    )

    emit_result(result, output_path=output_path, force_stdout=False, pretty=False)

    registry_data = json.loads(agent_registry_path().read_text(encoding="utf-8"))
    assert isinstance(registry_data, list)
    assert registry_data
    entry = registry_data[0]
    assert entry["name"] == "context-audit"
    assert entry["status"] == "ok"
    assert entry["task"].startswith("Audit AFS contexts")
    assert entry["output_path"] == str(output_path.resolve())
