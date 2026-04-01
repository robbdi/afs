from __future__ import annotations

from afs.model_prompts import build_model_system_prompt


def test_build_model_system_prompt_includes_session_state_summary() -> None:
    prompt = build_model_system_prompt(
        base_prompt="Base behavior.",
        session_state={
            "project": "afs",
            "profile": "default",
            "scratchpad": {
                "state_text": "Investigating MCP registry split.",
                "deferred_text": "Follow up on prompt packing.",
            },
            "diff": {"available": True, "total_changes": 7},
            "memory": {
                "memory_manifest": [
                    {"topic": "tag:mcp", "entry_count": 3, "latest": "2026-04-01T00:00:00Z"},
                    {"topic": "domain:session", "entry_count": 2, "latest": "2026-03-31T00:00:00Z"},
                ]
            },
            "tasks": {"total": 2, "counts": {"pending": 2}},
            "handoff": {"available": True, "next_steps": ["Ship the MCP refactor."]},
        },
    )

    assert "Base behavior." in prompt
    assert "## Session Context" in prompt
    assert "Project: afs (profile: default)" in prompt
    assert "Scratchpad state: Investigating MCP registry split." in prompt
    assert "Deferred: Follow up on prompt packing." in prompt
    assert "Recent changes: 7 files changed" in prompt
    assert "Memory topics: tag:mcp, domain:session" in prompt
    assert "Tasks: 2 (pending=2)" in prompt
    assert "Last session next steps:" in prompt
    assert "- Ship the MCP refactor." in prompt


def test_build_model_system_prompt_budget_drops_dynamic_sections_first() -> None:
    prompt = build_model_system_prompt(
        base_prompt="Base behavior.",
        session_state={
            "project": "afs",
            "profile": "default",
            "scratchpad": {"state_text": "x" * 1200},
        },
        token_budget=8,
    )

    assert "Base behavior." in prompt
    assert "## Session Context" not in prompt
