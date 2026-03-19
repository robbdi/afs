from __future__ import annotations

import json
from pathlib import Path

from afs.agent_registry import AgentRegistry
from afs.agents.base import AgentResult, emit_result
from afs.cli import briefing


def test_briefing_reads_agents_from_registry(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(briefing, "PROJECTS", {})
    monkeypatch.setattr(briefing, "_fetch_halext_tasks", lambda: [])
    monkeypatch.setattr(briefing, "_latest_weekly_carryover", lambda: [])

    emit_result(
        AgentResult(
            name="context-audit",
            status="ok",
            started_at="2026-03-19T08:00:00",
            finished_at="2026-03-19T08:00:05",
            duration_seconds=5.0,
        ),
        output_path=tmp_path / "audit.json",
        force_stdout=False,
        pretty=False,
    )

    payload = briefing._build_briefing(days=1)
    assert payload["active_agents"]
    assert payload["active_agents"][0]["name"] == "context-audit"


def test_briefing_registry_loader_accepts_list_payload(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    registry = AgentRegistry()
    registry.path.parent.mkdir(parents=True, exist_ok=True)
    registry.path.write_text(
        json.dumps(
            [
                {
                    "name": "history-memory",
                    "task": "Consolidate recent history events into durable memory summaries.",
                    "status": "running",
                }
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    loaded = briefing._read_agent_registry()
    assert loaded == [
        {
            "name": "history-memory",
            "task": "Consolidate recent history events into durable memory summaries.",
            "status": "running",
        }
    ]
