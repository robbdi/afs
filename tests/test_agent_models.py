from __future__ import annotations

import asyncio
import sys
from types import ModuleType, SimpleNamespace

import pytest

from afs.agent.models import (
    GeminiBackend,
    ModelConfig,
    ModelProvider,
    resolve_gemini_cache_settings,
)


class FakePart:
    def __init__(self, text=None, function_response=None, function_call=None):
        self.text = text
        self.function_response = function_response
        self.function_call = function_call


class FakeContent:
    def __init__(self, role, parts):
        self.role = role
        self.parts = parts


class FakeFunctionResponse:
    def __init__(self, name, response):
        self.name = name
        self.response = response


class FakeTool:
    def __init__(self, function_declarations):
        self.function_declarations = function_declarations


class FakeGenerateContentConfig:
    def __init__(self, **kwargs):
        self.temperature = kwargs.get("temperature")
        self.top_p = kwargs.get("top_p")
        self.max_output_tokens = kwargs.get("max_output_tokens")
        self.system_instruction = kwargs.get("system_instruction")
        self.tools = kwargs.get("tools")
        self.cached_content = kwargs.get("cached_content")


class FakeCreateCachedContentConfig:
    def __init__(self, **kwargs):
        self.contents = kwargs.get("contents")
        self.system_instruction = kwargs.get("system_instruction")
        self.ttl = kwargs.get("ttl")
        self.display_name = kwargs.get("display_name")


class FakeResponse:
    def __init__(self, text: str, *, cached_content_tokens: int = 0):
        self.candidates = [
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[SimpleNamespace(text=text, function_call=None)]
                )
            )
        ]
        self.usage_metadata = SimpleNamespace(
            prompt_token_count=11,
            candidates_token_count=7,
            cached_content_token_count=cached_content_tokens,
            total_token_count=18 + cached_content_tokens,
        )


class FakeCaches:
    def __init__(self, *, fail_create: bool = False):
        self.fail_create = fail_create
        self.create_calls: list[dict[str, object]] = []

    def create(self, *, model, config):
        self.create_calls.append({"model": model, "config": config})
        if self.fail_create:
            raise RuntimeError("cache create failed")
        return SimpleNamespace(name=f"cached/{len(self.create_calls)}")


class FakeModels:
    def __init__(self, *, fail_on_cached: bool = False):
        self.fail_on_cached = fail_on_cached
        self.calls: list[dict[str, object]] = []

    def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self.fail_on_cached and getattr(config, "cached_content", None):
            self.fail_on_cached = False
            raise RuntimeError("cached content expired")
        cached_tokens = 24 if getattr(config, "cached_content", None) else 0
        return FakeResponse("ok", cached_content_tokens=cached_tokens)


class FakeClient:
    def __init__(self, *, fail_create: bool = False, fail_on_cached: bool = False):
        self.caches = FakeCaches(fail_create=fail_create)
        self.models = FakeModels(fail_on_cached=fail_on_cached)


def _install_fake_gemini(monkeypatch, client: FakeClient) -> None:
    fake_types = SimpleNamespace(
        Content=FakeContent,
        Part=FakePart,
        FunctionResponse=FakeFunctionResponse,
        Tool=FakeTool,
        GenerateContentConfig=FakeGenerateContentConfig,
        CreateCachedContentConfig=FakeCreateCachedContentConfig,
    )
    fake_genai = ModuleType("google.genai")
    fake_genai.Client = lambda *args, **kwargs: client
    fake_genai.types = fake_types
    fake_google = ModuleType("google")
    fake_google.genai = fake_genai
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)


def _gemini_messages() -> list[dict[str, object]]:
    return [
        {"role": "user", "content": "Large repeated context " * 50},
        {"role": "user", "content": "What changed?"},
    ]


def test_resolve_gemini_cache_settings_reads_env(monkeypatch) -> None:
    monkeypatch.setenv("AFS_GEMINI_CACHE_MODE", "try")
    monkeypatch.setenv("AFS_GEMINI_CACHE_TTL", "90s")
    monkeypatch.setenv("AFS_GEMINI_CACHE_MIN_CHARS", "123")

    settings = resolve_gemini_cache_settings(
        ModelConfig(provider=ModelProvider.GEMINI, model_id="gemini-1.5-flash-001")
    )

    assert settings.mode == "try"
    assert settings.ttl == "90s"
    assert settings.min_prefix_chars == 123


def test_gemini_backend_uses_configurable_cached_content(monkeypatch) -> None:
    client = FakeClient()
    _install_fake_gemini(monkeypatch, client)
    backend = GeminiBackend(
        ModelConfig(
            provider=ModelProvider.GEMINI,
            model_id="gemini-1.5-flash-001",
            system_prompt="System prompt",
            extra={"gemini_cache": {"mode": "try", "ttl": "120s", "min_chars": 1}},
        )
    )

    result = asyncio.run(backend.generate(_gemini_messages()))

    assert len(client.caches.create_calls) == 1
    cache_config = client.caches.create_calls[0]["config"]
    assert cache_config.ttl == "120s"
    assert cache_config.system_instruction == "System prompt"
    generate_call = client.models.calls[0]
    assert generate_call["config"].cached_content == "cached/1"
    assert len(generate_call["contents"]) == 1
    assert result.usage["cached_content_tokens"] == 24


def test_gemini_backend_falls_back_uncached_when_cache_lookup_fails(monkeypatch) -> None:
    client = FakeClient(fail_on_cached=True)
    _install_fake_gemini(monkeypatch, client)
    backend = GeminiBackend(
        ModelConfig(
            provider=ModelProvider.GEMINI,
            model_id="gemini-1.5-flash-001",
            system_prompt="System prompt",
            extra={"gemini_cache_mode": "try", "gemini_cache_min_chars": 1},
        )
    )

    asyncio.run(backend.generate(_gemini_messages()))

    assert len(client.models.calls) == 2
    assert client.models.calls[0]["config"].cached_content == "cached/1"
    assert client.models.calls[1]["config"].cached_content is None
    assert len(client.models.calls[1]["contents"]) == 2


def test_gemini_backend_required_cache_raises_on_create_failure(monkeypatch) -> None:
    client = FakeClient(fail_create=True)
    _install_fake_gemini(monkeypatch, client)
    backend = GeminiBackend(
        ModelConfig(
            provider=ModelProvider.GEMINI,
            model_id="gemini-1.5-flash-001",
            extra={"gemini_cache": {"mode": "required", "min_chars": 1}},
        )
    )

    with pytest.raises(RuntimeError, match="Gemini cache required"):
        asyncio.run(backend.generate(_gemini_messages()))
