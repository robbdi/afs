from __future__ import annotations

from pathlib import Path

from afs.config import load_config, load_config_model


def test_load_config_merges_workspace_registry(tmp_path, monkeypatch) -> None:
    context_root = tmp_path / "context"
    context_root.mkdir()
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()

    registry_path = context_root / "workspaces.toml"
    registry_path.write_text(
        "[[workspaces]]\n"
        f"path = \"{workspace_dir}\"\n"
        "description = \"Example\"\n",
        encoding="utf-8",
    )

    config_path = tmp_path / "afs.toml"
    config_path.write_text(
        f"[general]\ncontext_root = \"{context_root}\"\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    data = load_config(merge_user=False)
    workspaces = data["general"]["workspace_directories"]
    assert workspaces
    assert Path(workspaces[0]["path"]).resolve() == workspace_dir.resolve()


def test_load_config_model_uses_explicit_path(tmp_path) -> None:
    context_root = tmp_path / "context"
    config_path = tmp_path / "custom.toml"
    config_path.write_text(
        f"[general]\ncontext_root = \"{context_root}\"\n",
        encoding="utf-8",
    )

    model = load_config_model(config_path=config_path, merge_user=False)
    assert model.general.context_root == context_root.resolve()


def test_load_config_model_parses_profiles_extensions_hooks(tmp_path) -> None:
    config_path = tmp_path / "profiles.toml"
    config_path.write_text(
        "[extensions]\n"
        "enabled_extensions = [\"afs_google\"]\n"
        f"extension_dirs = [\"{tmp_path / 'extensions'}\"]\n\n"
        "[profiles]\n"
        "active_profile = \"work\"\n"
        "auto_apply = true\n\n"
        "[profiles.work]\n"
        "knowledge_mounts = [\"~/Journal/logs\"]\n"
        "skill_roots = [\"~/skills\"]\n"
        "model_registries = [\"~/registry/chat_registry.toml\"]\n"
        "enabled_extensions = [\"afs_google\"]\n"
        "policies = [\"no_zelda\"]\n\n"
        "[hooks]\n"
        "before_context_read = [\"scripts/hooks/read.sh\"]\n",
        encoding="utf-8",
    )

    model = load_config_model(config_path=config_path, merge_user=False)
    assert model.extensions.enabled_extensions == ["afs_google"]
    assert model.profiles.active_profile == "work"
    assert "work" in model.profiles.profiles
    work = model.profiles.profiles["work"]
    assert work.policies == ["no_zelda"]
    assert model.hooks.before_context_read == ["scripts/hooks/read.sh"]
