from __future__ import annotations

from pathlib import Path

from afs.manager import AFSManager
from afs.models import MountType
from afs.schema import AFSConfig, GeneralConfig, ProfileConfig, ProfilesConfig


def _make_manager(tmp_path: Path) -> AFSManager:
    context_root = tmp_path / "context"
    general = GeneralConfig(
        context_root=context_root,
        agent_workspaces_dir=context_root / "workspaces",
    )
    return AFSManager(config=AFSConfig(general=general))


def _clear_profile_env(monkeypatch) -> None:  # noqa: ANN001
    for name in (
        "AFS_PROFILE",
        "AFS_ENABLED_EXTENSIONS",
        "AFS_KNOWLEDGE_MOUNTS",
        "AFS_SKILL_ROOTS",
        "AFS_MODEL_REGISTRIES",
        "AFS_POLICIES",
    ):
        monkeypatch.delenv(name, raising=False)


def test_ensure_creates_context_and_metadata(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    project_path = tmp_path / "project"
    project_path.mkdir()

    context = manager.ensure(path=project_path, context_root=tmp_path / "context")

    assert context.path.exists()
    assert (context.path / "metadata.json").exists()
    assert (context.path / "memory").exists()
    assert (context.path / "knowledge").exists()


def test_ensure_with_link_creates_symlink(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    project_path = tmp_path / "project"
    project_path.mkdir()
    context_root = tmp_path / "context"

    manager.ensure(path=project_path, context_root=context_root, link_context=True)

    link_path = project_path / ".context"
    assert link_path.is_symlink()
    assert link_path.resolve() == context_root.resolve()


def test_mount_and_unmount(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    project_path = tmp_path / "project"
    project_path.mkdir()
    context_root = tmp_path / "context"

    context = manager.ensure(path=project_path, context_root=context_root)

    source_dir = tmp_path / "source"
    source_dir.mkdir()

    mount = manager.mount(
        source_dir,
        MountType.KNOWLEDGE,
        context_path=context.path,
    )

    mount_path = context.path / "knowledge" / mount.name
    assert mount_path.is_symlink()
    assert mount_path.resolve() == source_dir.resolve()

    removed = manager.unmount(mount.name, MountType.KNOWLEDGE, context_path=context.path)
    assert removed
    assert not mount_path.exists()


def test_mount_rejects_nested_alias_and_duplicate_source(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    project_path = tmp_path / "project"
    project_path.mkdir()
    context = manager.ensure(path=project_path, context_root=tmp_path / "context")

    source_dir = tmp_path / "source"
    source_dir.mkdir()

    manager.mount(source_dir, MountType.KNOWLEDGE, alias="docs", context_path=context.path)

    try:
        manager.mount(source_dir, MountType.KNOWLEDGE, alias="docs-copy", context_path=context.path)
    except FileExistsError:
        pass
    else:
        raise AssertionError("expected duplicate source mount to fail")

    try:
        manager.mount(
            tmp_path,
            MountType.KNOWLEDGE,
            alias="nested/docs",
            context_path=context.path,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("expected nested alias mount to fail")


def test_context_health_reports_broken_and_profile_mount_issues(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _clear_profile_env(monkeypatch)
    knowledge_src = tmp_path / "knowledge-src"
    knowledge_src.mkdir()

    context_root = tmp_path / "context"
    general = GeneralConfig(
        context_root=context_root,
        agent_workspaces_dir=context_root / "workspaces",
    )
    profiles = ProfilesConfig(
        active_profile="work",
        auto_apply=True,
        profiles={
            "work": ProfileConfig(
                knowledge_mounts=[knowledge_src, tmp_path / "missing-src"],
            )
        },
    )
    manager = AFSManager(config=AFSConfig(general=general, profiles=profiles))

    project_path = tmp_path / "project"
    project_path.mkdir()
    context = manager.ensure(path=project_path, context_root=context_root, profile="work")

    broken_mount = manager.mount(
        knowledge_src,
        MountType.TOOLS,
        alias="temp-tool",
        context_path=context.path,
    )
    mount_path = context.path / "tools" / broken_mount.name
    knowledge_src.rmdir()

    health = manager.context_health(context.path, profile_name="work")

    assert health["healthy"] is False
    assert any(entry["name"] == "temp-tool" for entry in health["broken_mounts"])
    assert len(health["profile"]["missing_sources"]) == 2
    assert "restore or update missing profile source paths" in health["suggested_actions"]
    assert mount_path.is_symlink()
