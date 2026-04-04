"""Tests for conversation handoff protocol (Feature 4)."""

from __future__ import annotations

import json
from pathlib import Path

from afs.handoff import HandoffPacket, HandoffStore


def test_handoff_packet_roundtrip() -> None:
    packet = HandoffPacket(
        session_id="abc123",
        agent_name="test-agent",
        timestamp="2026-03-21T12:00:00+00:00",
        accomplished=["built feature X"],
        blocked=["needs review"],
        next_steps=["deploy to staging"],
        context_snapshot={"open_files": ["main.py"]},
        open_tasks=[{"id": "t1", "title": "review"}],
        metadata={"version": "1.0"},
    )
    d = packet.to_dict()
    restored = HandoffPacket.from_dict(d)
    assert restored.session_id == "abc123"
    assert restored.agent_name == "test-agent"
    assert restored.accomplished == ["built feature X"]
    assert restored.blocked == ["needs review"]
    assert restored.next_steps == ["deploy to staging"]


def test_handoff_store_create_and_read(tmp_path: Path) -> None:
    ctx = tmp_path / ".context"
    ctx.mkdir()
    (ctx / "scratchpad").mkdir()
    store = HandoffStore(ctx)

    packet = store.create(
        agent_name="agent-a",
        accomplished=["task 1"],
        blocked=["blocked on review"],
        next_steps=["deploy"],
    )
    assert packet.agent_name == "agent-a"
    assert len(packet.session_id) > 0

    # Read latest
    latest = store.read()
    assert latest is not None
    assert latest.session_id == packet.session_id
    assert latest.accomplished == ["task 1"]


def test_handoff_store_read_by_session_id(tmp_path: Path) -> None:
    ctx = tmp_path / ".context"
    ctx.mkdir()
    (ctx / "scratchpad").mkdir()
    store = HandoffStore(ctx)

    p1 = store.create(agent_name="a", accomplished=["first"])
    p2 = store.create(agent_name="a", accomplished=["second"])

    read1 = store.read(session_id=p1.session_id)
    assert read1 is not None
    assert read1.accomplished == ["first"]

    read2 = store.read(session_id=p2.session_id)
    assert read2 is not None
    assert read2.accomplished == ["second"]


def test_handoff_store_list(tmp_path: Path) -> None:
    ctx = tmp_path / ".context"
    ctx.mkdir()
    (ctx / "scratchpad").mkdir()
    store = HandoffStore(ctx)

    store.create(agent_name="a", accomplished=["first"])
    store.create(agent_name="b", accomplished=["second"])
    store.create(agent_name="c", accomplished=["third"])

    packets = store.list(limit=2)
    assert len(packets) == 2
    # Most recent first
    assert packets[0].accomplished == ["third"]
    assert packets[1].accomplished == ["second"]


def test_handoff_store_read_empty(tmp_path: Path) -> None:
    ctx = tmp_path / ".context"
    ctx.mkdir()
    (ctx / "scratchpad").mkdir()
    store = HandoffStore(ctx)
    assert store.read() is None


def test_handoff_manifest_persistence(tmp_path: Path) -> None:
    ctx = tmp_path / ".context"
    ctx.mkdir()
    (ctx / "scratchpad").mkdir()
    store = HandoffStore(ctx)

    store.create(agent_name="a", session_id="s1")
    store.create(agent_name="a", session_id="s2")

    manifest_path = ctx / "scratchpad" / "handoffs" / "_manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest == ["s1", "s2"]


# --- New fields and methods ---


def test_handoff_packet_target_agent_roundtrip() -> None:
    packet = HandoffPacket(
        session_id="t1",
        agent_name="source-agent",
        timestamp="2026-04-02T00:00:00+00:00",
        target_agent="dest-agent",
        priority="high",
        schema_version="2",
    )
    d = packet.to_dict()
    assert d["target_agent"] == "dest-agent"
    assert d["priority"] == "high"
    assert d["schema_version"] == "2"

    restored = HandoffPacket.from_dict(d)
    assert restored.target_agent == "dest-agent"
    assert restored.priority == "high"
    assert restored.schema_version == "2"


def test_handoff_packet_no_target_agent() -> None:
    """target_agent is optional and defaults to None."""
    packet = HandoffPacket(
        session_id="t2",
        agent_name="agent-a",
        timestamp="2026-04-02T00:00:00+00:00",
    )
    d = packet.to_dict()
    assert "target_agent" not in d  # omitted when None
    assert d["priority"] == "normal"

    restored = HandoffPacket.from_dict(d)
    assert restored.target_agent is None
    assert restored.priority == "normal"


def test_handoff_packet_backward_compat() -> None:
    """Packets from schema v1 (without new fields) should deserialize safely."""
    old_data = {
        "session_id": "old1",
        "agent_name": "legacy",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "accomplished": ["something"],
    }
    packet = HandoffPacket.from_dict(old_data)
    assert packet.target_agent is None
    assert packet.priority == "normal"
    assert packet.schema_version == "1"  # not present → defaults to "1"
    assert packet.acknowledged_by == []


def test_handoff_store_create_with_target(tmp_path: Path) -> None:
    ctx = tmp_path / ".context"
    ctx.mkdir()
    (ctx / "scratchpad").mkdir()
    store = HandoffStore(ctx)

    packet = store.create(
        agent_name="producer",
        target_agent="consumer",
        priority="high",
        accomplished=["built artifact"],
    )
    assert packet.target_agent == "consumer"
    assert packet.priority == "high"
    assert packet.schema_version == "2"

    # Verify persistence
    read_back = store.read(session_id=packet.session_id)
    assert read_back is not None
    assert read_back.target_agent == "consumer"
    assert read_back.priority == "high"


def test_handoff_pending_for_agent(tmp_path: Path) -> None:
    ctx = tmp_path / ".context"
    ctx.mkdir()
    (ctx / "scratchpad").mkdir()
    store = HandoffStore(ctx)

    store.create(agent_name="a", target_agent="b", accomplished=["work 1"])
    store.create(agent_name="a", target_agent="c", accomplished=["work 2"])
    store.create(agent_name="a", target_agent="b", accomplished=["work 3"])

    pending_b = store.pending_for_agent("b")
    assert len(pending_b) == 2
    # Should be newest first (before priority sort, both are "normal")
    assert pending_b[0].accomplished == ["work 3"]
    assert pending_b[1].accomplished == ["work 1"]

    pending_c = store.pending_for_agent("c")
    assert len(pending_c) == 1
    assert pending_c[0].accomplished == ["work 2"]

    # No pending for non-targeted agent
    assert store.pending_for_agent("d") == []


def test_handoff_pending_priority_ordering(tmp_path: Path) -> None:
    ctx = tmp_path / ".context"
    ctx.mkdir()
    (ctx / "scratchpad").mkdir()
    store = HandoffStore(ctx)

    store.create(agent_name="a", target_agent="b", priority="low", accomplished=["low"])
    store.create(agent_name="a", target_agent="b", priority="critical", accomplished=["critical"])
    store.create(agent_name="a", target_agent="b", priority="normal", accomplished=["normal"])

    pending = store.pending_for_agent("b")
    assert len(pending) == 3
    assert pending[0].priority == "critical"
    assert pending[1].priority == "normal"
    assert pending[2].priority == "low"


def test_handoff_acknowledge(tmp_path: Path) -> None:
    ctx = tmp_path / ".context"
    ctx.mkdir()
    (ctx / "scratchpad").mkdir()
    store = HandoffStore(ctx)

    packet = store.create(agent_name="a", target_agent="b", accomplished=["done"])

    # Before acknowledge, packet is pending
    assert len(store.pending_for_agent("b")) == 1

    result = store.acknowledge(packet.session_id, "b")
    assert result is True

    # After acknowledge, no longer pending
    assert len(store.pending_for_agent("b")) == 0

    # Verify persisted
    read_back = store.read(session_id=packet.session_id)
    assert read_back is not None
    assert "b" in read_back.acknowledged_by


def test_handoff_acknowledge_idempotent(tmp_path: Path) -> None:
    ctx = tmp_path / ".context"
    ctx.mkdir()
    (ctx / "scratchpad").mkdir()
    store = HandoffStore(ctx)

    packet = store.create(agent_name="a", target_agent="b")
    assert store.acknowledge(packet.session_id, "b") is True
    assert store.acknowledge(packet.session_id, "b") is True

    read_back = store.read(session_id=packet.session_id)
    assert read_back.acknowledged_by.count("b") == 1


def test_handoff_acknowledge_nonexistent(tmp_path: Path) -> None:
    ctx = tmp_path / ".context"
    ctx.mkdir()
    (ctx / "scratchpad").mkdir()
    store = HandoffStore(ctx)
    assert store.acknowledge("nonexistent", "b") is False


def test_handoff_pending_excludes_no_target(tmp_path: Path) -> None:
    """Packets without a target_agent should not appear in pending_for_agent."""
    ctx = tmp_path / ".context"
    ctx.mkdir()
    (ctx / "scratchpad").mkdir()
    store = HandoffStore(ctx)

    store.create(agent_name="a", accomplished=["no target"])
    assert store.pending_for_agent("a") == []
    assert store.pending_for_agent("") == []
