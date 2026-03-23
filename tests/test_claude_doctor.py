from __future__ import annotations

import json
import os
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from afs.claude.doctor import inspect_claude_sessions, reap_claude_sessions
from afs.cli.claude import claude_doctor_command


def _write_jsonl(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")


def _set_age(path: Path, hours_ago: int) -> None:
    timestamp = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).timestamp()
    os.utime(path, (timestamp, timestamp))
    if path.is_dir():
        for child in path.rglob("*"):
            os.utime(child, (timestamp, timestamp))


def _make_transcript(path: Path, session_id: str) -> None:
    _write_jsonl(
        path,
        [
            {
                "sessionId": session_id,
                "timestamp": "2026-03-20T01:00:00.000Z",
                "cwd": "/repo",
                "type": "user",
                "message": {"role": "user", "content": "Hello"},
            }
        ],
    )


def _make_artifacts(path: Path) -> None:
    (path / "subagents").mkdir(parents=True, exist_ok=True)
    (path / "subagents" / "worker.jsonl").write_text("{}", encoding="utf-8")


def _make_debug(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_inspect_claude_sessions_classifies_and_summarizes_debug(tmp_path: Path) -> None:
    claude_root = tmp_path / ".claude"
    projects_root = claude_root / "projects"
    debug_root = claude_root / "debug"

    active_id = "11111111-1111-4111-8111-111111111111"
    stale_id = "22222222-2222-4222-8222-222222222222"
    protected_id = "33333333-3333-4333-8333-333333333333"
    zombie_id = "44444444-4444-4444-8444-444444444444"

    active_project = projects_root / "proj-active"
    stale_project = projects_root / "proj-stale"
    protected_project = projects_root / "proj-protected"
    zombie_project = projects_root / "proj-zombie"
    for project in (active_project, stale_project, protected_project, zombie_project):
        project.mkdir(parents=True, exist_ok=True)

    _make_transcript(active_project / f"{active_id}.jsonl", active_id)
    _make_artifacts(active_project / active_id)
    _make_debug(
        debug_root / f"{active_id}.txt",
        '\n'.join(
            [
                '2026-03-23T00:00:00Z [DEBUG] MCP server "memory": Successfully connected to stdio server in 300ms',
                "2026-03-23T00:00:00Z [ERROR] Rate limited. Please try again later.",
            ]
        ),
    )
    _set_age(active_project / f"{active_id}.jsonl", 1)
    _set_age(active_project / active_id, 1)
    _set_age(active_project / active_id / "subagents" / "worker.jsonl", 1)
    _set_age(debug_root / f"{active_id}.txt", 1)

    _make_transcript(stale_project / f"{stale_id}.jsonl", stale_id)
    _make_artifacts(stale_project / stale_id)
    _make_debug(
        debug_root / f"{stale_id}.txt",
        '\n'.join(
            [
                '2026-03-20T00:00:00Z [DEBUG] MCP server "playwright": Successfully connected to stdio server in 800ms',
                '2026-03-20T00:00:00Z [DEBUG] blocked_path="/Users/me/.claude/projects/proj-stale/memory/"',
                "2026-03-20T00:00:00Z [ERROR] notifications/cancelled ... MCP error -32001: Request timed out",
                "2026-03-20T00:00:00Z [ERROR] Error: Tool mcp__foo__bar not found",
            ]
        ),
    )
    _set_age(stale_project / f"{stale_id}.jsonl", 120)
    _set_age(stale_project / stale_id, 120)
    _set_age(stale_project / stale_id / "subagents" / "worker.jsonl", 120)
    _set_age(debug_root / f"{stale_id}.txt", 120)

    _make_transcript(protected_project / f"{protected_id}.jsonl", protected_id)
    _make_artifacts(protected_project / protected_id)
    _set_age(protected_project / f"{protected_id}.jsonl", 120)
    _set_age(protected_project / protected_id, 120)
    _set_age(protected_project / protected_id / "subagents" / "worker.jsonl", 120)
    (protected_project / "bridge-pointer.json").write_text(
        json.dumps(
            {
                "sessionId": "session_01protected",
                "environmentId": "env_01protected",
                "source": "repl",
            }
        ),
        encoding="utf-8",
    )

    _make_artifacts(zombie_project / zombie_id)
    _make_debug(debug_root / f"{zombie_id}.txt", "2026-03-20T00:00:00Z [DEBUG] orphan")
    _set_age(zombie_project / zombie_id, 120)
    _set_age(zombie_project / zombie_id / "subagents" / "worker.jsonl", 120)
    _set_age(debug_root / f"{zombie_id}.txt", 120)

    report = inspect_claude_sessions(
        claude_root=claude_root,
        active_hours=6,
        reap_after_hours=72,
        recent_debug_logs=10,
    )

    assert report.project_count == 4
    assert report.session_count == 4
    assert report.status_counts["active"] == 1
    assert report.status_counts["stale"] == 1
    assert report.status_counts["protected"] == 1
    assert report.status_counts["zombie"] == 1
    assert len(report.bridge_pointers) == 1

    sessions = {session.session_id: session for session in report.sessions}
    assert sessions[active_id].status == "active"
    assert sessions[active_id].reap_candidate is False
    assert sessions[stale_id].status == "stale"
    assert sessions[stale_id].reap_candidate is True
    assert sessions[protected_id].status == "protected"
    assert sessions[protected_id].reap_candidate is False
    assert "bridge_pointer_present" in sessions[protected_id].reasons
    assert sessions[zombie_id].status == "zombie"
    assert sessions[zombie_id].reap_candidate is True
    assert "missing_transcript" in sessions[zombie_id].reasons

    signals = report.debug_signals
    assert signals.logs_scanned == 3
    assert signals.rate_limit_errors == 1
    assert signals.permission_blocks == 1
    assert signals.timeout_errors == 1
    assert signals.missing_tool_errors == 1
    latencies = {server.server: server for server in signals.mcp_servers}
    assert latencies["memory"].average_ms == 300
    assert latencies["playwright"].max_ms == 800


def test_reap_claude_sessions_archives_only_candidates(tmp_path: Path) -> None:
    claude_root = tmp_path / ".claude"
    projects_root = claude_root / "projects"
    debug_root = claude_root / "debug"
    archive_root = tmp_path / "archive"

    stale_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    protected_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    zombie_id = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"

    stale_project = projects_root / "proj-stale"
    protected_project = projects_root / "proj-protected"
    zombie_project = projects_root / "proj-zombie"
    for project in (stale_project, protected_project, zombie_project):
        project.mkdir(parents=True, exist_ok=True)

    _make_transcript(stale_project / f"{stale_id}.jsonl", stale_id)
    _make_artifacts(stale_project / stale_id)
    _make_debug(debug_root / f"{stale_id}.txt", "stale debug")
    _set_age(stale_project / f"{stale_id}.jsonl", 120)
    _set_age(stale_project / stale_id, 120)
    _set_age(stale_project / stale_id / "subagents" / "worker.jsonl", 120)
    _set_age(debug_root / f"{stale_id}.txt", 120)

    _make_transcript(protected_project / f"{protected_id}.jsonl", protected_id)
    _make_artifacts(protected_project / protected_id)
    _set_age(protected_project / f"{protected_id}.jsonl", 120)
    _set_age(protected_project / protected_id, 120)
    _set_age(protected_project / protected_id / "subagents" / "worker.jsonl", 120)
    (protected_project / "bridge-pointer.json").write_text(
        json.dumps({"sessionId": "session_01", "environmentId": "env_01", "source": "repl"}),
        encoding="utf-8",
    )

    _make_artifacts(zombie_project / zombie_id)
    _make_debug(debug_root / f"{zombie_id}.txt", "zombie debug")
    _set_age(zombie_project / zombie_id, 120)
    _set_age(zombie_project / zombie_id / "subagents" / "worker.jsonl", 120)
    _set_age(debug_root / f"{zombie_id}.txt", 120)

    dry_run = reap_claude_sessions(
        claude_root=claude_root,
        active_hours=6,
        reap_after_hours=72,
        apply=False,
        archive_root=archive_root,
    )
    assert dry_run.candidate_count == 2
    assert dry_run.moved_count == 0
    assert (stale_project / f"{stale_id}.jsonl").exists()
    assert (zombie_project / zombie_id).exists()

    applied = reap_claude_sessions(
        claude_root=claude_root,
        active_hours=6,
        reap_after_hours=72,
        apply=True,
        archive_root=archive_root,
    )
    assert applied.candidate_count == 2
    assert applied.moved_count == 5
    assert applied.manifest_path is not None
    assert applied.manifest_path.exists()
    assert not (stale_project / f"{stale_id}.jsonl").exists()
    assert not (stale_project / stale_id).exists()
    assert not (debug_root / f"{stale_id}.txt").exists()
    assert not (zombie_project / zombie_id).exists()
    assert not (debug_root / f"{zombie_id}.txt").exists()
    assert (protected_project / f"{protected_id}.jsonl").exists()
    assert (archive_root / "projects" / "proj-stale" / f"{stale_id}.jsonl").exists()
    assert (archive_root / "projects" / "proj-stale" / stale_id).exists()
    assert (archive_root / "projects" / "proj-zombie" / zombie_id).exists()
    assert (archive_root / "debug" / f"{stale_id}.txt").exists()
    assert (archive_root / "debug" / f"{zombie_id}.txt").exists()


def test_claude_doctor_command_outputs_json(tmp_path: Path, capsys) -> None:
    claude_root = tmp_path / ".claude"
    project = claude_root / "projects" / "proj"
    debug_root = claude_root / "debug"
    session_id = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"

    project.mkdir(parents=True, exist_ok=True)
    _make_transcript(project / f"{session_id}.jsonl", session_id)
    _make_debug(debug_root / f"{session_id}.txt", "debug")

    exit_code = claude_doctor_command(
        Namespace(
            claude_root=str(claude_root),
            active_hours=6,
            reap_after_hours=72,
            recent_debug_logs=5,
            limit=10,
            json=True,
        )
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["session_count"] == 1
    assert payload["sessions"][0]["session_id"] == session_id
