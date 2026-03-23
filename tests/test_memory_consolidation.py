from __future__ import annotations

import json
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import afs.cli.core as cli_core_module
from afs.cli.core import memory_consolidate_command
from afs.history import append_history_event
from afs.manager import AFSManager
from afs.memory_consolidation import consolidate_history_to_memory
from afs.models import MountType
from afs.schema import AFSConfig, DirectoryConfig, GeneralConfig, default_directory_configs


def _remap_directories(**overrides: str) -> list[DirectoryConfig]:
    directories: list[DirectoryConfig] = []
    for directory in default_directory_configs():
        name = (
            overrides.get(directory.role.value, directory.name)
            if directory.role
            else directory.name
        )
        directories.append(
            DirectoryConfig(
                name=name,
                policy=directory.policy,
                description=directory.description,
                role=directory.role,
            )
        )
    return directories


def _build_context(
    tmp_path: Path,
    *,
    directories: list[DirectoryConfig] | None = None,
) -> tuple[AFSConfig, Path]:
    context_root = tmp_path / ".context"
    config = AFSConfig(
        general=GeneralConfig(
            context_root=context_root,
        ),
        directories=directories or default_directory_configs(),
    )
    manager = AFSManager(config=config)
    project_path = tmp_path / "project"
    project_path.mkdir()
    manager.ensure(path=project_path, context_root=context_root)
    return config, context_root


def test_consolidate_history_to_memory_writes_entries_and_markdown(tmp_path: Path) -> None:
    directories = _remap_directories(history="ledger", memory="brain", scratchpad="notes")
    config, context_root = _build_context(tmp_path, directories=directories)
    history_root = context_root / "ledger"
    base = datetime.now(timezone.utc).replace(microsecond=0)

    append_history_event(
        history_root,
        "fs",
        "afs.context_fs",
        op="write",
        context_root=context_root,
        metadata={
            "mount_type": "scratchpad",
            "relative_path": "state.md",
            "context_path": str(context_root),
        },
        timestamp=(base + timedelta(seconds=60)).isoformat(),
        event_id="evt-001",
    )
    append_history_event(
        history_root,
        "context",
        "afs.manager",
        op="mount",
        context_root=context_root,
        metadata={
            "mount_type": "knowledge",
            "alias": "docs",
            "context_path": str(context_root),
        },
        timestamp=(base + timedelta(seconds=120)).isoformat(),
        event_id="evt-002",
    )

    result = consolidate_history_to_memory(context_root, config=config)

    assert result.entries_written == 1
    assert result.markdown_written == 1
    assert result.consolidated_events >= 2
    assert result.entries_path == context_root / "brain" / "entries.jsonl"
    assert result.checkpoint_path == context_root / "notes" / "afs_agents" / "history_memory_checkpoint.json"

    entries = [
        json.loads(line)
        for line in result.entries_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["source"] == "history.consolidation"
    assert "history-consolidated" in entry["tags"]
    assert entry["_metadata"]["event_types"]["fs"] == 1
    assert entry["_metadata"]["event_types"]["context"] >= 1
    assert "scratchpad/state.md" in entry["output"]
    assert result.markdown_paths[0].exists()


def test_consolidation_checkpoint_skips_old_events(tmp_path: Path) -> None:
    config, context_root = _build_context(tmp_path)
    history_root = context_root / MountType.HISTORY.value
    base = datetime.now(timezone.utc).replace(microsecond=0)

    append_history_event(
        history_root,
        "fs",
        "afs.context_fs",
        op="write",
        context_root=context_root,
        metadata={"mount_type": "scratchpad", "relative_path": "note.md"},
        timestamp=(base + timedelta(seconds=60)).isoformat(),
        event_id="evt-001",
    )

    first = consolidate_history_to_memory(
        context_root,
        config=config,
        write_markdown=False,
    )
    second = consolidate_history_to_memory(
        context_root,
        config=config,
        write_markdown=False,
    )

    append_history_event(
        history_root,
        "review",
        "afs.cli.review",
        op="approve",
        context_root=context_root,
        metadata={"category": "docs", "filename": "design.md"},
        timestamp=(base + timedelta(seconds=120)).isoformat(),
        event_id="evt-002",
    )
    third = consolidate_history_to_memory(
        context_root,
        config=config,
        write_markdown=False,
    )

    entries = [
        json.loads(line)
        for line in (context_root / "memory" / "entries.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert first.entries_written == 1
    assert second.entries_written == 0
    assert "no new events" in second.notes
    assert third.entries_written == 1
    assert len(entries) == 2


def test_memory_consolidate_command_outputs_json(tmp_path: Path, monkeypatch, capsys) -> None:
    config, context_root = _build_context(tmp_path)
    history_root = context_root / "history"
    base = datetime.now(timezone.utc).replace(microsecond=0)
    append_history_event(
        history_root,
        "hook",
        "afs.grounding_hooks",
        op="before_context_read",
        context_root=context_root,
        metadata={"status": "ok"},
        timestamp=(base + timedelta(seconds=60)).isoformat(),
        event_id="evt-001",
    )

    manager = AFSManager(config=config)
    monkeypatch.setattr(cli_core_module, "load_manager", lambda _config_path=None: manager)

    exit_code = memory_consolidate_command(
        Namespace(
            config=None,
            path=None,
            context_root=context_root,
            context_dir=None,
            max_events=None,
            max_events_per_entry=None,
            event_types=None,
            no_markdown=True,
            json=True,
        )
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["entries_written"] == 1
    assert payload["markdown_written"] == 0
    assert payload["memory_root"] == str(context_root / "memory")
