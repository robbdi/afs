"""Generate a draft response using a configured chat model or router."""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from ..chat_registry import load_chat_registry
from ..gateway.backends import BackendManager
from .base import (
    AgentResult,
    build_base_parser,
    configure_logging,
    emit_result,
    now_iso,
)

AGENT_NAME = "scribe-draft"
AGENT_DESCRIPTION = "Draft responses using a configured chat registry model."


def build_parser() -> argparse.ArgumentParser:
    parser = build_base_parser("Draft responses using a configured chat registry model.")
    parser.add_argument("--prompt", help="Prompt to send.")
    parser.add_argument("--model", default="scribe", help="Model alias or router name to use.")
    parser.add_argument("--model-id", help="Override backend model ID.")
    parser.add_argument("--profile", help="Profile name override for registry resolution.")
    parser.add_argument("--registry", action="append", help="Explicit registry file or directory.")
    parser.add_argument("--output-text", help="Write response to this file.")
    return parser


async def _chat(
    prompt: str,
    model: str,
    model_id: str | None,
    *,
    config_path: str | None,
    profile_name: str | None,
    registry_paths: list[str] | None,
) -> dict:
    async with BackendManager() as manager:
        if not manager.active:
            return {"error": "No backend available"}

        registry = load_chat_registry(
            config_path=Path(config_path).expanduser() if config_path else None,
            profile_name=profile_name,
            registry_paths=[Path(path).expanduser() for path in registry_paths or []] or None,
        )
        target = registry.resolve_target(model, prompt=prompt)

        resolved_model = model_id or target.model_id
        messages = [{"role": "user", "content": prompt}]
        if target.system_prompt:
            messages.insert(0, {"role": "system", "content": target.system_prompt})

        response = await manager.chat(model=resolved_model, messages=messages)
        content = response.get("message", {}).get("content", "")
        return {
            "backend": manager.active.name if manager.active else None,
            "model_id": resolved_model,
            "provider": target.provider,
            "registry_sources": [str(path) for path in registry.sources],
            "response": content,
        }


def run(args: argparse.Namespace) -> int:
    configure_logging(args.quiet)
    prompt = args.prompt
    if not prompt:
        prompt = sys.stdin.read().strip()
    if not prompt:
        print("No prompt provided")
        return 1

    started_at = now_iso()
    start = time.monotonic()
    payload = asyncio.run(
        _chat(
            prompt,
            args.model,
            args.model_id,
            config_path=args.config,
            profile_name=args.profile,
            registry_paths=args.registry,
        )
    )
    duration = time.monotonic() - start

    output_text_path = None
    if args.output_text:
        output_text_path = Path(args.output_text).expanduser().resolve()
        output_text_path.parent.mkdir(parents=True, exist_ok=True)
        output_text_path.write_text(payload.get("response", ""), encoding="utf-8")

    result = AgentResult(
        name=AGENT_NAME,
        status="ok" if payload.get("response") else "error",
        started_at=started_at,
        finished_at=now_iso(),
        duration_seconds=duration,
        metrics={},
        notes=[payload["error"]] if payload.get("error") else [],
        payload={
            "model": args.model,
            "model_id": payload.get("model_id"),
            "provider": payload.get("provider"),
            "backend": payload.get("backend"),
            "registry_sources": payload.get("registry_sources"),
            "prompt": prompt,
            "response": payload.get("response"),
            "output_text": str(output_text_path) if output_text_path else None,
        },
    )

    emit_result(
        result,
        output_path=Path(args.output) if args.output else None,
        force_stdout=args.stdout,
        pretty=args.pretty,
    )
    return 0 if result.status == "ok" else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
