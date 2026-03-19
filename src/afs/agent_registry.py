"""Global agent activity registry used by briefings and handoff tools."""

from __future__ import annotations

import importlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:  # pragma: no cover - platform specific
    import fcntl
except ImportError:  # pragma: no cover - platform specific
    fcntl = None

ACTIVE_AGENT_STATES = {"running", "awaiting_review"}
RECENT_AGENT_WINDOW = timedelta(hours=24)


def agent_registry_path() -> Path:
    """Return the global registry path used by session briefings."""
    env_value = os.environ.get("AFS_AGENT_REGISTRY_PATH", "").strip()
    if env_value:
        return Path(env_value).expanduser().resolve()
    return (Path.home() / ".afs" / "agent_registry.json").expanduser().resolve()


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.replace(tzinfo=None)
    return parsed


def _latest_timestamp(entry: dict[str, Any]) -> datetime | None:
    for key in ("last_output_at", "finished_at", "updated_at", "started_at"):
        parsed = _parse_timestamp(str(entry.get(key, "") or ""))
        if parsed is not None:
            return parsed
    return None


def _sort_key(entry: dict[str, Any]) -> tuple[int, float]:
    status = str(entry.get("status", ""))
    timestamp = _latest_timestamp(entry)
    return (
        1 if status in ACTIVE_AGENT_STATES else 0,
        timestamp.timestamp() if timestamp is not None else 0.0,
    )


def resolve_agent_task(
    name: str,
    *,
    module: str = "",
    description: str = "",
) -> str:
    """Resolve a human-readable task description for an agent."""
    if description.strip():
        return description.strip()

    try:
        from .agents import get_agent

        spec = get_agent(name)
        if spec and spec.description.strip():
            return spec.description.strip()
    except Exception:
        pass

    if module.strip():
        try:
            loaded = importlib.import_module(module)
        except Exception:
            loaded = None
        if loaded is not None:
            module_description = getattr(loaded, "AGENT_DESCRIPTION", "")
            if isinstance(module_description, str) and module_description.strip():
                return module_description.strip()

    return name.strip()


class AgentRegistry:
    """Persist a compact list of active and recently completed agents."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = (path or agent_registry_path()).expanduser().resolve()
        self._lock_path = self.path.with_suffix(".lock")

    @contextmanager
    def _locked_entries(self) -> Iterator[list[dict[str, Any]]]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock_path.open("a+", encoding="utf-8") as lock_file:
            if fcntl is not None:  # pragma: no branch - simple platform guard
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            entries = self._read_unlocked()
            try:
                yield entries
            finally:
                self._write_unlocked(entries)
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _read_unlocked(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    def _write_unlocked(self, entries: list[dict[str, Any]]) -> None:
        filtered = self._prune(entries)
        filtered.sort(key=_sort_key, reverse=True)
        text = json.dumps(filtered, indent=2) + "\n"
        tmp_path = self.path.with_suffix(".tmp")
        tmp_path.write_text(text, encoding="utf-8")
        tmp_path.replace(self.path)

    def _prune(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cutoff = datetime.now() - RECENT_AGENT_WINDOW
        kept: list[dict[str, Any]] = []
        for entry in entries:
            status = str(entry.get("status", ""))
            if status in ACTIVE_AGENT_STATES:
                kept.append(entry)
                continue
            latest = _latest_timestamp(entry)
            if latest is not None and latest >= cutoff:
                kept.append(entry)
        return kept

    def entries(self) -> list[dict[str, Any]]:
        return self._read_unlocked()

    def get(self, name: str, *, context_root: str = "") -> dict[str, Any] | None:
        entries = self._read_unlocked()
        entry = self._find_entry(entries, name=name, context_root=context_root)
        if entry is None:
            return None
        return dict(entry)

    def _find_entry(
        self,
        entries: list[dict[str, Any]],
        *,
        name: str,
        context_root: str = "",
    ) -> dict[str, Any] | None:
        for entry in entries:
            if str(entry.get("name", "")) != name:
                continue
            existing_context = str(entry.get("context_root", "") or "")
            if context_root and existing_context and existing_context != context_root:
                continue
            return entry
        return None

    def update(
        self,
        *,
        name: str,
        status: str,
        task: str = "",
        module: str = "",
        context_root: str = "",
        started_at: str = "",
        finished_at: str = "",
        last_output_at: str = "",
        output_path: str = "",
        last_error: str = "",
        pid: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._locked_entries() as entries:
            entry = self._find_entry(entries, name=name, context_root=context_root)
            if entry is None:
                entry = {"name": name}
                entries.append(entry)

            resolved_task = task.strip() or str(entry.get("task", "") or "")
            if not resolved_task:
                resolved_task = resolve_agent_task(name, module=module)

            entry["name"] = name
            entry["task"] = resolved_task
            entry["status"] = status
            entry["module"] = module or str(entry.get("module", "") or "")
            if context_root:
                entry["context_root"] = context_root
            if started_at:
                entry["started_at"] = started_at
            if finished_at:
                entry["finished_at"] = finished_at
            if last_output_at:
                entry["last_output_at"] = last_output_at
            elif finished_at:
                entry["last_output_at"] = finished_at
            if output_path:
                entry["output_path"] = output_path
            if last_error:
                entry["last_error"] = last_error
            elif status not in {"failed", "error"}:
                entry.pop("last_error", None)
            if pid is not None and status in ACTIVE_AGENT_STATES:
                entry["pid"] = pid
            elif status not in ACTIVE_AGENT_STATES:
                entry.pop("pid", None)
            if metadata:
                existing_metadata = entry.get("metadata")
                merged_metadata = dict(existing_metadata) if isinstance(existing_metadata, dict) else {}
                merged_metadata.update(metadata)
                entry["metadata"] = merged_metadata
            entry["updated_at"] = datetime.now().isoformat()
            return dict(entry)

    def mark_started(
        self,
        *,
        name: str,
        module: str = "",
        task: str = "",
        context_root: str = "",
        started_at: str = "",
        pid: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.update(
            name=name,
            status="running",
            task=task,
            module=module,
            context_root=context_root,
            started_at=started_at or datetime.now().isoformat(),
            pid=pid,
            metadata=metadata,
        )

    def mark_result(
        self,
        *,
        name: str,
        status: str,
        module: str = "",
        task: str = "",
        context_root: str = "",
        started_at: str = "",
        finished_at: str = "",
        output_path: str = "",
        last_error: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        finished_value = finished_at or datetime.now().isoformat()
        return self.update(
            name=name,
            status=status,
            task=task,
            module=module,
            context_root=context_root,
            started_at=started_at,
            finished_at=finished_value,
            last_output_at=finished_value,
            output_path=output_path,
            last_error=last_error,
            metadata=metadata,
        )
