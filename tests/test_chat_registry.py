from __future__ import annotations

from pathlib import Path

from afs.chat_registry import load_chat_registry


def test_load_chat_registry_from_profile_model_registries(tmp_path: Path) -> None:
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    (registry_dir / "chat_registry.toml").write_text(
        "[[models]]\n"
        "name = \"work-gemma\"\n"
        "provider = \"ollama\"\n"
        "model_id = \"gemma3:12b\"\n"
        "role = \"coding\"\n"
        "tags = [\"work\"]\n"
        "system_prompt = \"Use work context only.\"\n"
        "\n"
        "[[routers]]\n"
        "name = \"default\"\n"
        "strategy = \"keyword\"\n"
        "default_model = \"work-gemma\"\n",
        encoding="utf-8",
    )

    config_path = tmp_path / "afs.toml"
    config_path.write_text(
        "[profiles]\n"
        "active_profile = \"work\"\n"
        "\n"
        "[profiles.work]\n"
        f"model_registries = [\"{registry_dir}\"]\n",
        encoding="utf-8",
    )

    registry = load_chat_registry(config_path=config_path)
    model = registry.resolve_model("work-gemma")

    assert str(registry.sources[0]).endswith("chat_registry.toml")
    assert model.model_id == "gemma3:12b"
    assert model.system_prompt == "Use work context only."
    assert registry.route_prompt(registry.resolve_router("default"), "hello") == ["work-gemma"]


def test_load_chat_registry_explicit_paths_override_profile_resolution(tmp_path: Path) -> None:
    registry_file = tmp_path / "chat_registry.toml"
    registry_file.write_text(
        "[[models]]\n"
        "name = \"gemini-work\"\n"
        "provider = \"openai\"\n"
        "model_id = \"gemini-2.5-pro\"\n",
        encoding="utf-8",
    )

    registry = load_chat_registry(registry_paths=[registry_file])
    assert registry.resolve_model("gemini-work").model_id == "gemini-2.5-pro"


def test_resolve_target_supports_router_names(tmp_path: Path) -> None:
    registry_file = tmp_path / "chat_registry.toml"
    registry_file.write_text(
        "[[models]]\n"
        "name = \"gemma-work\"\n"
        "provider = \"ollama\"\n"
        "model_id = \"gemma3:12b\"\n"
        "\n"
        "[[routers]]\n"
        "name = \"work\"\n"
        "strategy = \"keyword\"\n"
        "default_model = \"gemma-work\"\n",
        encoding="utf-8",
    )

    registry = load_chat_registry(registry_paths=[registry_file])
    assert registry.resolve_target("work", prompt="summarize this").model_id == "gemma3:12b"
