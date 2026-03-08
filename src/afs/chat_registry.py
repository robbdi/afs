"""Generic chat registry loader for profile/extension-provided model registries."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:  # pragma: no cover - py<3.11 fallback
    import tomli as tomllib  # type: ignore

from .config import load_config_model
from .profiles import resolve_active_profile
from .schema import AFSConfig


@dataclass
class ChatModel:
    """Model entry loaded from a chat registry."""

    name: str
    provider: str
    model_id: str
    role: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    parameters: dict[str, object] = field(default_factory=dict)
    system_prompt: str = ""
    base_url: str = ""
    api_key_env: str = ""
    thinking_tier: str = ""


@dataclass
class RouterRule:
    keywords: list[str]
    model: str


@dataclass
class ChatRouter:
    name: str
    description: str = ""
    strategy: str = "keyword"
    default_model: str = ""
    models: list[str] = field(default_factory=list)
    rules: list[RouterRule] = field(default_factory=list)


@dataclass
class ChatRegistry:
    models: dict[str, ChatModel] = field(default_factory=dict)
    routers: dict[str, ChatRouter] = field(default_factory=dict)
    sources: list[Path] = field(default_factory=list)

    def resolve_model(self, name: str, provider: str = "ollama") -> ChatModel:
        if name in self.models:
            return self.models[name]
        for model in self.models.values():
            if model.model_id == name:
                return model
        return ChatModel(name=name, provider=provider, model_id=name)

    def resolve_router(self, name: str) -> ChatRouter | None:
        return self.routers.get(name)

    def resolve_target(self, name: str, *, prompt: str = "", provider: str = "ollama") -> ChatModel:
        if name in self.models:
            return self.models[name]

        router = self.resolve_router(name)
        if router is not None:
            routed = self.route_prompt(router, prompt)
            if routed:
                return self.resolve_model(routed[0], provider=provider)
            if router.default_model:
                return self.resolve_model(router.default_model, provider=provider)

        return self.resolve_model(name, provider=provider)

    def route_prompt(self, router: ChatRouter, prompt: str) -> list[str]:
        prompt_lower = prompt.lower()
        if router.strategy == "ensemble":
            return list(router.models)
        for rule in router.rules:
            if any(keyword.lower() in prompt_lower for keyword in rule.keywords):
                return [rule.model]
        if router.default_model:
            return [router.default_model]
        if router.rules:
            return [router.rules[0].model]
        return []

    def to_dict(self) -> dict[str, Any]:
        return {
            "models": [
                {
                    "name": model.name,
                    "provider": model.provider,
                    "model_id": model.model_id,
                    "role": model.role,
                    "description": model.description,
                    "tags": list(model.tags),
                    "parameters": dict(model.parameters),
                    "system_prompt": model.system_prompt,
                    "base_url": model.base_url,
                    "api_key_env": model.api_key_env,
                    "thinking_tier": model.thinking_tier,
                }
                for model in self.models.values()
            ],
            "routers": [
                {
                    "name": router.name,
                    "description": router.description,
                    "strategy": router.strategy,
                    "default_model": router.default_model,
                    "models": list(router.models),
                    "rules": [
                        {"keywords": list(rule.keywords), "model": rule.model}
                        for rule in router.rules
                    ],
                }
                for router in self.routers.values()
            ],
            "sources": [str(path) for path in self.sources],
        }


def _env_registry_paths() -> list[Path]:
    values: list[Path] = []
    for name in ("AFS_CHAT_REGISTRY", "AFS_CHAT_REGISTRIES"):
        raw = os.environ.get(name, "").strip()
        if not raw:
            continue
        for item in raw.split(os.pathsep):
            if item.strip():
                values.append(Path(item).expanduser().resolve())
    return values


def _candidate_registry_files(path: Path) -> list[Path]:
    resolved = path.expanduser().resolve()
    if resolved.is_file():
        return [resolved]
    if not resolved.exists():
        return []
    candidates = [
        resolved / "chat_registry.toml",
        resolved / "registry.toml",
    ]
    return [candidate for candidate in candidates if candidate.exists()]


def resolve_chat_registry_paths(
    *,
    config: AFSConfig | None = None,
    config_path: Path | None = None,
    profile_name: str | None = None,
    registry_paths: list[Path] | None = None,
) -> list[Path]:
    """Resolve concrete chat registry files from env, profile config, or explicit paths."""
    candidates: list[Path] = []

    if registry_paths:
        for path in registry_paths:
            candidates.extend(_candidate_registry_files(path))
    else:
        candidates.extend(_env_registry_paths())
        resolved_config = config or load_config_model(config_path=config_path, merge_user=True)
        profile = resolve_active_profile(resolved_config, profile_name=profile_name)
        for path in profile.model_registries:
            candidates.extend(_candidate_registry_files(path))

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        marker = str(candidate)
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(candidate)
    return unique


def load_chat_registry(
    *,
    config: AFSConfig | None = None,
    config_path: Path | None = None,
    profile_name: str | None = None,
    registry_paths: list[Path] | None = None,
) -> ChatRegistry:
    """Load and merge one or more chat registries."""
    registry = ChatRegistry()
    for path in resolve_chat_registry_paths(
        config=config,
        config_path=config_path,
        profile_name=profile_name,
        registry_paths=registry_paths,
    ):
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
        registry.sources.append(path)

        for model in payload.get("models", []):
            if not isinstance(model, dict):
                continue
            name = str(model.get("name", "")).strip()
            provider = str(model.get("provider", "ollama")).strip() or "ollama"
            model_id = str(model.get("model_id", name)).strip()
            if not name or not model_id:
                continue
            parameters = model.get("parameters") or model.get("options") or {}
            if not isinstance(parameters, dict):
                parameters = {}
            tags = model.get("tags") or []
            if not isinstance(tags, list):
                tags = []
            registry.models[name] = ChatModel(
                name=name,
                provider=provider,
                model_id=model_id,
                role=str(model.get("role", "") or ""),
                description=str(model.get("description", "") or ""),
                tags=[str(tag) for tag in tags if isinstance(tag, str)],
                parameters=dict(parameters),
                system_prompt=str(model.get("system_prompt", "") or ""),
                base_url=str(model.get("base_url", "") or ""),
                api_key_env=str(model.get("api_key_env", "") or ""),
                thinking_tier=str(model.get("thinking_tier", "") or ""),
            )

        for router in payload.get("routers", []):
            if not isinstance(router, dict):
                continue
            name = str(router.get("name", "")).strip()
            if not name:
                continue
            rules: list[RouterRule] = []
            for rule in router.get("rules", []) or []:
                if not isinstance(rule, dict):
                    continue
                keywords = [str(value) for value in rule.get("keywords", []) if isinstance(value, str)]
                model_name = str(rule.get("model", "")).strip()
                if keywords and model_name:
                    rules.append(RouterRule(keywords=keywords, model=model_name))
            models = router.get("models") or []
            if not isinstance(models, list):
                models = []
            registry.routers[name] = ChatRouter(
                name=name,
                description=str(router.get("description", "") or ""),
                strategy=str(router.get("strategy", "keyword") or "keyword"),
                default_model=str(router.get("default_model", "") or ""),
                models=[str(value) for value in models if isinstance(value, str)],
                rules=rules,
            )
    return registry
