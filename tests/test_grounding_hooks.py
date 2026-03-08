from __future__ import annotations

import pytest

from afs.grounding_hooks import run_grounding_hooks
from afs.schema import AFSConfig, ProfileConfig, ProfilesConfig


def _work_config() -> AFSConfig:
    return AFSConfig(
        profiles=ProfilesConfig(
            active_profile="work",
            auto_apply=True,
            profiles={
                "work": ProfileConfig(policies=["no_zelda"]),
            },
        )
    )


def test_no_zelda_policy_blocks_agent_dispatch() -> None:
    with pytest.raises(PermissionError):
        run_grounding_hooks(
            event="before_agent_dispatch",
            payload={"summary": "Debug Zelda dungeon issue"},
            config=_work_config(),
        )


def test_no_zelda_policy_allows_work_dispatch() -> None:
    run_grounding_hooks(
        event="before_agent_dispatch",
        payload={"summary": "Review Gemini CLI MCP integration"},
        config=_work_config(),
    )
