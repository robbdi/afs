from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import afs.cli.core as cli_core_module
from afs.cli.core import session_pack_command
from afs.context_index import ContextSQLiteIndex
from afs.context_pack import build_context_pack, write_context_pack_artifacts
from afs.manager import AFSManager
from afs.models import MountType
from afs.schema import AFSConfig, GeneralConfig, SensitivityConfig


def _make_manager(tmp_path: Path) -> AFSManager:
    context_root = tmp_path / ".context"
    config = AFSConfig(
        general=GeneralConfig(
            context_root=context_root,
        ),
        sensitivity=SensitivityConfig(never_export=["knowledge/private/*"]),
    )
    manager = AFSManager(config=config)
    project_path = tmp_path / "project"
    project_path.mkdir()
    manager.ensure(path=project_path, context_root=context_root)
    return manager


def test_build_context_pack_respects_sensitivity_and_budget(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    context_root = manager.config.general.context_root

    scratchpad_root = manager.resolve_mount_root(context_root, MountType.SCRATCHPAD)
    scratchpad_root.mkdir(parents=True, exist_ok=True)
    (scratchpad_root / "state.md").write_text("fix service wiring", encoding="utf-8")

    memory_root = manager.resolve_mount_root(context_root, MountType.MEMORY)
    summary_root = memory_root / "history_consolidation"
    summary_root.mkdir(parents=True, exist_ok=True)
    (memory_root / "entries.jsonl").write_text(json.dumps({"id": "mem-1"}) + "\n", encoding="utf-8")
    (summary_root / "mem-1.md").write_text("previous durable memory summary", encoding="utf-8")

    knowledge_root = manager.resolve_mount_root(context_root, MountType.KNOWLEDGE)
    (knowledge_root / "public").mkdir(parents=True, exist_ok=True)
    (knowledge_root / "private").mkdir(parents=True, exist_ok=True)
    (knowledge_root / "public" / "guide.md").write_text(
        "service wiring guide for agents",
        encoding="utf-8",
    )
    (knowledge_root / "private" / "secret.md").write_text(
        "private service details",
        encoding="utf-8",
    )

    index = ContextSQLiteIndex(manager, context_root)
    index.rebuild(mount_types=[MountType.KNOWLEDGE, MountType.SCRATCHPAD], include_content=True)

    pack = build_context_pack(
        manager,
        context_root,
        query="service wiring",
        model="gemini",
        token_budget=500,
        include_content=True,
    )

    assert pack["model"] == "gemini"
    assert pack["estimated_tokens"] <= 500
    assert any(section["title"] == "Scratchpad State" for section in pack["sections"])
    assert any("guide.md" in source for source in pack["sources"])
    assert all("secret.md" not in source for source in pack["sources"])


def test_session_pack_command_outputs_json_and_writes_artifacts(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    manager = _make_manager(tmp_path)
    context_root = manager.config.general.context_root
    knowledge_root = manager.resolve_mount_root(context_root, MountType.KNOWLEDGE)
    knowledge_root.mkdir(parents=True, exist_ok=True)
    (knowledge_root / "guide.md").write_text("codex pack guide", encoding="utf-8")
    ContextSQLiteIndex(manager, context_root).rebuild(
        mount_types=[MountType.KNOWLEDGE],
        include_content=True,
    )

    monkeypatch.setattr(cli_core_module, "load_manager", lambda _config_path=None: manager)

    exit_code = session_pack_command(
        Namespace(
            config=None,
            path=None,
            context_root=context_root,
            context_dir=None,
            query="codex pack",
            model="codex",
            token_budget=400,
            include_content=False,
            max_query_results=4,
            max_embedding_results=2,
            no_write_artifacts=False,
            json=True,
        )
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["model"] == "codex"
    assert payload["artifact_paths"]["json"].endswith("session_pack_codex.json")
    assert Path(payload["artifact_paths"]["json"]).exists()
    assert Path(payload["artifact_paths"]["markdown"]).exists()


def test_session_pack_command_skips_artifact_rewrite_on_cache_hit(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    manager = _make_manager(tmp_path)
    context_root = manager.config.general.context_root
    scratchpad_root = manager.resolve_mount_root(context_root, MountType.SCRATCHPAD)
    scratchpad_root.mkdir(parents=True, exist_ok=True)
    (scratchpad_root / "state.md").write_text("cached command state", encoding="utf-8")

    monkeypatch.setattr(cli_core_module, "load_manager", lambda _config_path=None: manager)

    args = Namespace(
        config=None,
        path=None,
        context_root=context_root,
        context_dir=None,
        query="cached command",
        model="codex",
        token_budget=400,
        include_content=False,
        max_query_results=4,
        max_embedding_results=2,
        no_write_artifacts=False,
        json=True,
    )

    exit_code = session_pack_command(args)
    assert exit_code == 0
    first = json.loads(capsys.readouterr().out)
    assert first["cache"]["hit"] is False

    marker = Path(first["artifact_paths"]["json"])
    assert marker.exists()

    monkeypatch.setattr(
        "afs.context_pack.write_context_pack_artifacts",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cache hit should not rewrite artifacts")),
    )

    exit_code = session_pack_command(args)
    assert exit_code == 0
    second = json.loads(capsys.readouterr().out)
    assert second["cache"]["hit"] is True
    assert Path(second["artifact_paths"]["json"]) == marker


def test_build_context_pack_reuses_cached_artifact_when_inputs_match(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manager = _make_manager(tmp_path)
    context_root = manager.config.general.context_root
    scratchpad_root = manager.resolve_mount_root(context_root, MountType.SCRATCHPAD)
    scratchpad_root.mkdir(parents=True, exist_ok=True)
    (scratchpad_root / "state.md").write_text("cached pack state", encoding="utf-8")

    first_pack = build_context_pack(
        manager,
        context_root,
        query="cached pack",
        model="codex",
        token_budget=400,
    )
    write_context_pack_artifacts(manager, context_root, first_pack)

    monkeypatch.setattr(
        "afs.context_pack._build_sections",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cache should avoid rebuild")),
    )

    cached_pack = build_context_pack(
        manager,
        context_root,
        query="cached pack",
        model="codex",
        token_budget=400,
    )

    assert cached_pack["cache"]["hit"] is True
    assert cached_pack["artifact_paths"]["json"].endswith("session_pack_codex.json")


def test_build_context_pack_invalidates_cache_when_bootstrap_changes(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    context_root = manager.config.general.context_root
    scratchpad_root = manager.resolve_mount_root(context_root, MountType.SCRATCHPAD)
    scratchpad_root.mkdir(parents=True, exist_ok=True)
    state_path = scratchpad_root / "state.md"
    state_path.write_text("initial state", encoding="utf-8")

    first_pack = build_context_pack(
        manager,
        context_root,
        query="state drift",
        model="codex",
    )
    write_context_pack_artifacts(manager, context_root, first_pack)

    state_path.write_text("changed state", encoding="utf-8")

    second_pack = build_context_pack(
        manager,
        context_root,
        query="state drift",
        model="codex",
    )

    assert second_pack["cache"]["hit"] is False


def test_write_context_pack_artifacts_writes_files(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    context_root = manager.config.general.context_root
    pack = {
        "context_path": str(context_root),
        "project": "project",
        "profile": "default",
        "model": "generic",
        "query": "",
        "token_budget": 100,
        "estimated_tokens": 10,
        "guidance": "use this pack",
        "sections": [],
        "sources": [],
        "omitted_sections": [],
    }

    artifact_paths = write_context_pack_artifacts(manager, context_root, pack)

    assert Path(artifact_paths["json"]).exists()
    assert Path(artifact_paths["markdown"]).exists()
