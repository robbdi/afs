from __future__ import annotations

from pathlib import Path

from afs.manager import AFSManager
from afs.models import MountType
from afs.profiles import resolve_active_profile
from afs.schema import (
    AFSConfig,
    ExtensionsConfig,
    GeneralConfig,
    ProfileConfig,
    ProfilesConfig,
)


def test_resolve_profile_with_extension(tmp_path: Path) -> None:
    ext_root = tmp_path / "extensions"
    extension_dir = ext_root / "afs_google_test"
    extension_dir.mkdir(parents=True)

    work_knowledge = extension_dir / "knowledge"
    work_skills = extension_dir / "skills"
    work_registry = extension_dir / "registry"
    work_knowledge.mkdir()
    work_skills.mkdir()
    work_registry.mkdir()

    (extension_dir / "extension.toml").write_text(
        "name = \"afs_google_test\"\n"
        "knowledge_mounts = [\"knowledge\"]\n"
        "skill_roots = [\"skills\"]\n"
        "model_registries = [\"registry\"]\n"
        "policies = [\"no_zelda\"]\n",
        encoding="utf-8",
    )

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
                enabled_extensions=["afs_google_test"],
            )
        },
    )
    config = AFSConfig(
        general=general,
        profiles=profiles,
        extensions=ExtensionsConfig(
            enabled_extensions=["afs_google_test"],
            extension_dirs=[ext_root],
        ),
    )

    resolved = resolve_active_profile(config)
    assert resolved.name == "work"
    assert "no_zelda" in resolved.policies
    assert work_knowledge.resolve() in resolved.knowledge_mounts
    assert work_skills.resolve() in resolved.skill_roots
    assert work_registry.resolve() in resolved.model_registries


def test_manager_applies_profile_mounts(tmp_path: Path) -> None:
    knowledge_src = tmp_path / "knowledge-src"
    skill_src = tmp_path / "skills-src"
    registry_src = tmp_path / "registry-src"
    knowledge_src.mkdir()
    skill_src.mkdir()
    registry_src.mkdir()

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
                knowledge_mounts=[knowledge_src],
                skill_roots=[skill_src],
                model_registries=[registry_src],
            )
        },
    )

    manager = AFSManager(config=AFSConfig(general=general, profiles=profiles))

    project = tmp_path / "project"
    project.mkdir()
    context = manager.ensure(path=project, context_root=context_root, profile="work")

    knowledge_mounts = context.get_mounts(MountType.KNOWLEDGE)
    tool_mounts = context.get_mounts(MountType.TOOLS)
    global_mounts = context.get_mounts(MountType.GLOBAL)

    assert any(m.name.startswith("profile-knowledge-work") for m in knowledge_mounts)
    assert any(m.name.startswith("profile-skill-work") for m in tool_mounts)
    assert any(m.name.startswith("profile-registry-work") for m in global_mounts)


def test_resolve_profile_does_not_auto_load_unrequested_extensions(tmp_path: Path) -> None:
    ext_root = tmp_path / "extensions"
    extension_dir = ext_root / "afs_google_test"
    extension_dir.mkdir(parents=True)
    (extension_dir / "knowledge").mkdir()
    (extension_dir / "extension.toml").write_text(
        "name = \"afs_google_test\"\n"
        "knowledge_mounts = [\"knowledge\"]\n",
        encoding="utf-8",
    )

    config = AFSConfig(
        general=GeneralConfig(context_root=tmp_path / "context"),
        extensions=ExtensionsConfig(extension_dirs=[ext_root], auto_discover=True),
    )

    resolved = resolve_active_profile(config)

    assert resolved.enabled_extensions == []
    assert resolved.knowledge_mounts == []
