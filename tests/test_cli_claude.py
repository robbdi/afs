from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import afs.cli.claude as claude_cli
from afs.cli.claude import claude_setup_command
from afs.manager import AFSManager
from afs.schema import AFSConfig, GeneralConfig


def test_claude_setup_writes_to_resolved_project_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    context_root = tmp_path / "context"
    manager = AFSManager(
        config=AFSConfig(
            general=GeneralConfig(
                context_root=context_root,
            )
        )
    )
    manager.ensure(path=project_path, context_root=context_root)

    monkeypatch.setattr(claude_cli, "load_manager", lambda _config_path=None: manager)
    monkeypatch.chdir(elsewhere)

    exit_code = claude_setup_command(
        Namespace(
            config=None,
            path=str(project_path),
            context_root=str(context_root),
            context_dir=None,
            force=False,
        )
    )

    assert exit_code == 0
    assert (project_path / ".claude" / "settings.json").exists()
    assert (project_path / "CLAUDE.md").exists()
    assert not (elsewhere / ".claude" / "settings.json").exists()
    assert not (elsewhere / "CLAUDE.md").exists()


def test_claude_setup_writes_user_settings_when_requested(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    context_root = tmp_path / "context"
    settings_path = tmp_path / "home" / ".claude" / "settings.json"
    manager = AFSManager(
        config=AFSConfig(
            general=GeneralConfig(
                context_root=context_root,
            )
        )
    )
    manager.ensure(path=project_path, context_root=context_root)

    monkeypatch.setattr(claude_cli, "load_manager", lambda _config_path=None: manager)

    exit_code = claude_setup_command(
        Namespace(
            config=None,
            path=str(project_path),
            context_root=str(context_root),
            context_dir=None,
            scope="user",
            settings_path=str(settings_path),
            force=False,
        )
    )

    assert exit_code == 0
    assert settings_path.exists()
    settings = settings_path.read_text(encoding="utf-8")
    assert "AFS_CONFIG_PATH" not in settings
    assert "AFS_CONTEXT_ROOT" not in settings
    assert not (project_path / ".claude" / "settings.json").exists()
    assert not (project_path / "CLAUDE.md").exists()
