from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import afs.cli.review as review_module
from afs.manager import AFSManager
from afs.models import MountType
from afs.schema import (
    AFSConfig,
    DirectoryConfig,
    GeneralConfig,
    WorkspaceDirectory,
    default_directory_configs,
)


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


def _make_manager(
    tmp_path: Path,
    *,
    workspace_root: Path | None = None,
    remap: dict[str, str] | None = None,
) -> AFSManager:
    general = GeneralConfig(
        context_root=tmp_path / "global-context",
        workspace_directories=(
            [WorkspaceDirectory(path=workspace_root.resolve())]
            if workspace_root is not None
            else []
        ),
    )
    config = AFSConfig(
        general=general,
        directories=_remap_directories(**(remap or {})),
    )
    return AFSManager(config=config)


def _ensure_project_context(manager: AFSManager, project_path: Path) -> Path:
    project_path.mkdir(parents=True, exist_ok=True)
    context = manager.ensure(path=project_path)
    return context.path


def _queue_review_doc(
    manager: AFSManager,
    context_path: Path,
    *,
    category: str,
    filename: str,
    content: str = "draft",
    legacy_queue: bool = False,
) -> Path:
    if legacy_queue:
        queue_root = context_path / "review"
    else:
        queue_root = manager.resolve_mount_root(context_path, MountType.SCRATCHPAD) / "review"
    category_root = queue_root / category
    category_root.mkdir(parents=True, exist_ok=True)
    target = category_root / filename
    target.write_text(content, encoding="utf-8")
    return target


def test_review_list_reads_context_local_queue(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    manager = _make_manager(tmp_path)
    project_path = tmp_path / "project"
    context_path = _ensure_project_context(manager, project_path)
    _queue_review_doc(manager, context_path, category="plans", filename="plan.md")
    _queue_review_doc(
        manager,
        context_path,
        category="automated_reports",
        filename="report.md",
    )
    monkeypatch.setattr(review_module, "load_manager", lambda _config_path=None: manager)

    exit_code = review_module.handle_list(
        Namespace(
            config=None,
            path=str(project_path),
            context_root=None,
            context_dir=None,
            json=True,
            category=None,
        )
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["context_path"] == str(context_path)
    assert payload["categories"]["plans"] == ["plan.md"]
    assert payload["categories"]["automated_reports"] == ["report.md"]


def test_review_approve_moves_plan_to_memory_reviewed(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    manager = _make_manager(tmp_path)
    project_path = tmp_path / "project"
    context_path = _ensure_project_context(manager, project_path)
    source = _queue_review_doc(manager, context_path, category="plans", filename="plan.md")
    monkeypatch.setattr(review_module, "load_manager", lambda _config_path=None: manager)

    exit_code = review_module.handle_approve(
        Namespace(
            config=None,
            path=str(project_path),
            context_root=None,
            context_dir=None,
            json=False,
            category=None,
            target="plan.md",
            filename=None,
        )
    )

    assert exit_code == 0
    capsys.readouterr()
    destination = (
        manager.resolve_mount_root(context_path, MountType.MEMORY)
        / "reviewed"
        / "plans"
        / "plan.md"
    )
    assert not source.exists()
    assert destination.read_text(encoding="utf-8") == "draft"


def test_review_reject_moves_doc_to_history_rejected(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    manager = _make_manager(tmp_path)
    project_path = tmp_path / "project"
    context_path = _ensure_project_context(manager, project_path)
    source = _queue_review_doc(
        manager,
        context_path,
        category="walkthroughs",
        filename="walkthrough.md",
    )
    monkeypatch.setattr(review_module, "load_manager", lambda _config_path=None: manager)

    exit_code = review_module.handle_reject(
        Namespace(
            config=None,
            path=str(project_path),
            context_root=None,
            context_dir=None,
            json=False,
            category=None,
            target="walkthrough.md",
            filename=None,
            reason="needs revision",
        )
    )

    assert exit_code == 0
    capsys.readouterr()
    destination = (
        manager.resolve_mount_root(context_path, MountType.HISTORY)
        / "rejected"
        / "walkthroughs"
        / "walkthrough.md"
    )
    assert not source.exists()
    assert destination.read_text(encoding="utf-8") == "draft"
    assert destination.with_name("walkthrough.md.reason.txt").read_text(encoding="utf-8") == "needs revision"


def test_review_approve_legacy_project_argument_uses_workspace_directory(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    workspace_root = tmp_path / "workspace"
    manager = _make_manager(tmp_path, workspace_root=workspace_root)
    project_path = workspace_root / "project-a"
    context_path = _ensure_project_context(manager, project_path)
    _queue_review_doc(manager, context_path, category="plans", filename="plan.md")
    monkeypatch.setattr(review_module, "load_manager", lambda _config_path=None: manager)

    exit_code = review_module.handle_approve(
        Namespace(
            config=None,
            path=None,
            context_root=None,
            context_dir=None,
            json=False,
            category=None,
            target="project-a",
            filename="plan.md",
        )
    )

    assert exit_code == 0
    capsys.readouterr()
    destination = (
        manager.resolve_mount_root(context_path, MountType.MEMORY)
        / "reviewed"
        / "plans"
        / "plan.md"
    )
    assert destination.exists()


def test_review_approve_uses_remapped_mount_roots(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    manager = _make_manager(
        tmp_path,
        remap={"scratchpad": "notes", "memory": "journal", "history": "ledger"},
    )
    project_path = tmp_path / "project"
    context_path = _ensure_project_context(manager, project_path)
    source = _queue_review_doc(manager, context_path, category="plans", filename="plan.md")
    monkeypatch.setattr(review_module, "load_manager", lambda _config_path=None: manager)

    exit_code = review_module.handle_approve(
        Namespace(
            config=None,
            path=str(project_path),
            context_root=None,
            context_dir=None,
            json=False,
            category=None,
            target="plan.md",
            filename=None,
        )
    )

    assert exit_code == 0
    capsys.readouterr()
    destination = context_path / "journal" / "reviewed" / "plans" / "plan.md"
    assert not source.exists()
    assert destination.exists()


def test_review_approve_supports_legacy_queue_root(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    manager = _make_manager(tmp_path)
    project_path = tmp_path / "project"
    context_path = _ensure_project_context(manager, project_path)
    source = _queue_review_doc(
        manager,
        context_path,
        category="plans",
        filename="legacy.md",
        legacy_queue=True,
    )
    monkeypatch.setattr(review_module, "load_manager", lambda _config_path=None: manager)

    exit_code = review_module.handle_approve(
        Namespace(
            config=None,
            path=str(project_path),
            context_root=None,
            context_dir=None,
            json=False,
            category=None,
            target="legacy.md",
            filename=None,
        )
    )

    assert exit_code == 0
    capsys.readouterr()
    destination = (
        manager.resolve_mount_root(context_path, MountType.MEMORY)
        / "reviewed"
        / "plans"
        / "legacy.md"
    )
    assert not source.exists()
    assert destination.exists()
