"""Claude session health inspection and archive-only reaping helpers."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

SESSION_DIR_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
MCP_CONNECT_RE = re.compile(r'MCP server "([^"]+)": Successfully connected.* in (\d+)ms')
RATE_LIMIT_RE = re.compile(r"Rate limited\. Please try again later\.", re.IGNORECASE)
PERMISSION_BLOCK_RE = re.compile(r"blocked_path|not auto-approving", re.IGNORECASE)
TIMEOUT_RE = re.compile(r"Request timed out|timed out", re.IGNORECASE)
MISSING_TOOL_RE = re.compile(r"Tool .* not found", re.IGNORECASE)


@dataclass(frozen=True)
class ClaudeBridgePointer:
    project_slug: str
    path: Path
    session_id: str | None
    environment_id: str | None
    source: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_slug": self.project_slug,
            "path": str(self.path),
            "session_id": self.session_id,
            "environment_id": self.environment_id,
            "source": self.source,
        }


@dataclass(frozen=True)
class ClaudeMCPServerLatency:
    server: str
    count: int
    average_ms: float
    max_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "server": self.server,
            "count": self.count,
            "average_ms": round(self.average_ms, 1),
            "max_ms": self.max_ms,
        }


@dataclass(frozen=True)
class ClaudeDebugSignals:
    logs_scanned: int
    rate_limit_errors: int
    permission_blocks: int
    timeout_errors: int
    missing_tool_errors: int
    mcp_servers: tuple[ClaudeMCPServerLatency, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "logs_scanned": self.logs_scanned,
            "rate_limit_errors": self.rate_limit_errors,
            "permission_blocks": self.permission_blocks,
            "timeout_errors": self.timeout_errors,
            "missing_tool_errors": self.missing_tool_errors,
            "mcp_servers": [server.to_dict() for server in self.mcp_servers],
        }


@dataclass(frozen=True)
class ClaudeSessionHealth:
    session_id: str
    project_slug: str | None
    transcript_path: Path | None
    artifacts_dir: Path | None
    debug_log_path: Path | None
    bridge_pointer_path: Path | None
    status: str
    reasons: tuple[str, ...]
    last_activity_at: datetime | None
    last_activity_source: str | None
    age_hours: float | None
    reap_candidate: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "project_slug": self.project_slug,
            "transcript_path": str(self.transcript_path) if self.transcript_path else None,
            "artifacts_dir": str(self.artifacts_dir) if self.artifacts_dir else None,
            "debug_log_path": str(self.debug_log_path) if self.debug_log_path else None,
            "bridge_pointer_path": str(self.bridge_pointer_path) if self.bridge_pointer_path else None,
            "status": self.status,
            "reasons": list(self.reasons),
            "last_activity_at": self.last_activity_at.isoformat() if self.last_activity_at else None,
            "last_activity_source": self.last_activity_source,
            "age_hours": round(self.age_hours, 2) if self.age_hours is not None else None,
            "reap_candidate": self.reap_candidate,
        }


@dataclass(frozen=True)
class ClaudeDoctorReport:
    claude_root: Path
    projects_root: Path
    debug_root: Path
    archive_root: Path
    project_count: int
    session_count: int
    status_counts: dict[str, int]
    bridge_pointers: tuple[ClaudeBridgePointer, ...]
    sessions: tuple[ClaudeSessionHealth, ...]
    debug_signals: ClaudeDebugSignals

    def to_dict(self) -> dict[str, Any]:
        return {
            "claude_root": str(self.claude_root),
            "projects_root": str(self.projects_root),
            "debug_root": str(self.debug_root),
            "archive_root": str(self.archive_root),
            "project_count": self.project_count,
            "session_count": self.session_count,
            "status_counts": dict(self.status_counts),
            "bridge_pointers": [pointer.to_dict() for pointer in self.bridge_pointers],
            "sessions": [session.to_dict() for session in self.sessions],
            "debug_signals": self.debug_signals.to_dict(),
        }


@dataclass(frozen=True)
class ClaudeReapSummary:
    claude_root: Path
    archive_root: Path
    apply: bool
    candidate_count: int
    moved_count: int
    skipped_count: int
    manifest_path: Path | None
    sessions: tuple[ClaudeSessionHealth, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "claude_root": str(self.claude_root),
            "archive_root": str(self.archive_root),
            "apply": self.apply,
            "candidate_count": self.candidate_count,
            "moved_count": self.moved_count,
            "skipped_count": self.skipped_count,
            "manifest_path": str(self.manifest_path) if self.manifest_path else None,
            "sessions": [session.to_dict() for session in self.sessions],
        }


def inspect_claude_sessions(
    *,
    claude_root: Path | None = None,
    active_hours: int = 6,
    reap_after_hours: int = 72,
    recent_debug_logs: int = 20,
) -> ClaudeDoctorReport:
    root = (claude_root or (Path.home() / ".claude")).expanduser().resolve()
    projects_root = root / "projects"
    debug_root = root / "debug"
    archive_root = root / "archive"

    bridge_pointers = _discover_bridge_pointers(projects_root)
    session_records = _discover_session_records(
        projects_root=projects_root,
        debug_root=debug_root,
        bridge_pointers=bridge_pointers,
        active_hours=active_hours,
        reap_after_hours=reap_after_hours,
    )
    debug_signals = _inspect_debug_signals(debug_root, recent_debug_logs)

    status_counts: dict[str, int] = {}
    for session in session_records:
        status_counts[session.status] = status_counts.get(session.status, 0) + 1

    project_count = 0
    if projects_root.exists():
        project_count = sum(1 for entry in projects_root.iterdir() if entry.is_dir())

    return ClaudeDoctorReport(
        claude_root=root,
        projects_root=projects_root,
        debug_root=debug_root,
        archive_root=archive_root,
        project_count=project_count,
        session_count=len(session_records),
        status_counts=status_counts,
        bridge_pointers=tuple(sorted(bridge_pointers.values(), key=lambda item: item.project_slug)),
        sessions=tuple(session_records),
        debug_signals=debug_signals,
    )


def reap_claude_sessions(
    *,
    claude_root: Path | None = None,
    active_hours: int = 6,
    reap_after_hours: int = 72,
    recent_debug_logs: int = 20,
    apply: bool = False,
    archive_root: Path | None = None,
    limit: int | None = None,
) -> ClaudeReapSummary:
    report = inspect_claude_sessions(
        claude_root=claude_root,
        active_hours=active_hours,
        reap_after_hours=reap_after_hours,
        recent_debug_logs=recent_debug_logs,
    )
    candidates = [session for session in report.sessions if session.reap_candidate]
    candidates.sort(
        key=lambda item: (
            0 if item.status == "zombie" else 1,
            -(item.age_hours or 0.0),
            item.project_slug or "",
            item.session_id,
        )
    )
    if limit is not None and limit >= 0:
        candidates = candidates[:limit]

    archive_base = (
        archive_root.expanduser().resolve()
        if archive_root is not None
        else report.archive_root / f"claude-reap-{_now_utc().strftime('%Y%m%dT%H%M%SZ')}"
    )
    manifest_path: Path | None = None
    moved_count = 0
    skipped_count = 0

    if apply and candidates:
        archive_base.mkdir(parents=True, exist_ok=True)
        manifest: dict[str, Any] = {
            "created_at": _now_utc().isoformat(),
            "claude_root": str(report.claude_root),
            "sessions": [],
        }
        for session in candidates:
            session_payload = session.to_dict()
            moved_paths: list[dict[str, str]] = []
            for kind, source in _iter_session_paths(session):
                destination = _archive_destination(archive_base, session, source, kind)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(destination))
                moved_paths.append(
                    {
                        "kind": kind,
                        "source": str(source),
                        "destination": str(destination),
                    }
                )
                moved_count += 1
            if not moved_paths:
                skipped_count += 1
            session_payload["archived_paths"] = moved_paths
            manifest["sessions"].append(session_payload)

        manifest_path = archive_base / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return ClaudeReapSummary(
        claude_root=report.claude_root,
        archive_root=archive_base,
        apply=apply,
        candidate_count=len(candidates),
        moved_count=moved_count,
        skipped_count=skipped_count,
        manifest_path=manifest_path,
        sessions=tuple(candidates),
    )


def _discover_bridge_pointers(projects_root: Path) -> dict[str, ClaudeBridgePointer]:
    pointers: dict[str, ClaudeBridgePointer] = {}
    if not projects_root.exists():
        return pointers

    for project_dir in sorted(entry for entry in projects_root.iterdir() if entry.is_dir()):
        pointer_path = project_dir / "bridge-pointer.json"
        if not pointer_path.exists():
            continue
        try:
            payload = json.loads(pointer_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        pointers[project_dir.name] = ClaudeBridgePointer(
            project_slug=project_dir.name,
            path=pointer_path,
            session_id=_string_or_none(payload.get("sessionId")),
            environment_id=_string_or_none(payload.get("environmentId")),
            source=_string_or_none(payload.get("source")),
        )
    return pointers


def _discover_session_records(
    *,
    projects_root: Path,
    debug_root: Path,
    bridge_pointers: dict[str, ClaudeBridgePointer],
    active_hours: int,
    reap_after_hours: int,
) -> list[ClaudeSessionHealth]:
    sessions: dict[str, dict[str, Any]] = {}

    if projects_root.exists():
        for project_dir in sorted(entry for entry in projects_root.iterdir() if entry.is_dir()):
            project_slug = project_dir.name
            for transcript in sorted(project_dir.glob("*.jsonl")):
                record = sessions.setdefault(
                    transcript.stem,
                    {
                        "session_id": transcript.stem,
                        "project_slug": project_slug,
                        "transcript_path": None,
                        "artifacts_dir": None,
                        "debug_log_path": None,
                    },
                )
                record["project_slug"] = project_slug
                record["transcript_path"] = transcript

            for entry in sorted(project_dir.iterdir()):
                if not entry.is_dir():
                    continue
                if not SESSION_DIR_RE.match(entry.name):
                    continue
                record = sessions.setdefault(
                    entry.name,
                    {
                        "session_id": entry.name,
                        "project_slug": project_slug,
                        "transcript_path": None,
                        "artifacts_dir": None,
                        "debug_log_path": None,
                    },
                )
                record["project_slug"] = project_slug
                record["artifacts_dir"] = entry

    if debug_root.exists():
        for debug_log in sorted(debug_root.glob("*.txt")):
            session_id = debug_log.stem
            record = sessions.setdefault(
                session_id,
                {
                    "session_id": session_id,
                    "project_slug": None,
                    "transcript_path": None,
                    "artifacts_dir": None,
                    "debug_log_path": None,
                },
            )
            record["debug_log_path"] = debug_log

    now = _now_utc()
    records: list[ClaudeSessionHealth] = []
    for record in sessions.values():
        project_slug = record.get("project_slug")
        pointer = bridge_pointers.get(project_slug) if project_slug else None
        transcript_path = record.get("transcript_path")
        artifacts_dir = record.get("artifacts_dir")
        debug_log_path = record.get("debug_log_path")

        timestamps: list[tuple[datetime, str]] = []
        if transcript_path:
            ts = _path_mtime(transcript_path)
            if ts:
                timestamps.append((ts, "transcript"))
        if artifacts_dir:
            ts = _tree_mtime(artifacts_dir)
            if ts:
                timestamps.append((ts, "artifacts"))
        if debug_log_path:
            ts = _path_mtime(debug_log_path)
            if ts:
                timestamps.append((ts, "debug"))

        last_activity_at: datetime | None = None
        last_activity_source: str | None = None
        if timestamps:
            last_activity_at, last_activity_source = max(timestamps, key=lambda item: item[0])

        age_hours: float | None = None
        if last_activity_at is not None:
            age_hours = (now - last_activity_at).total_seconds() / 3600.0

        reasons: list[str] = []
        if pointer:
            reasons.append("bridge_pointer_present")
        if transcript_path is None:
            reasons.append("missing_transcript")
        if artifacts_dir is None:
            reasons.append("missing_artifacts")
        if debug_log_path is None:
            reasons.append("missing_debug_log")

        if transcript_path is None:
            status = "zombie"
        elif pointer is not None:
            status = "protected"
        elif age_hours is not None and age_hours <= float(active_hours):
            status = "active"
        else:
            status = "stale"

        reap_candidate = (
            pointer is None
            and status in {"stale", "zombie"}
            and age_hours is not None
            and age_hours >= float(reap_after_hours)
        )

        records.append(
            ClaudeSessionHealth(
                session_id=record["session_id"],
                project_slug=project_slug,
                transcript_path=transcript_path,
                artifacts_dir=artifacts_dir,
                debug_log_path=debug_log_path,
                bridge_pointer_path=pointer.path if pointer else None,
                status=status,
                reasons=tuple(reasons),
                last_activity_at=last_activity_at,
                last_activity_source=last_activity_source,
                age_hours=age_hours,
                reap_candidate=reap_candidate,
            )
        )

    records.sort(
        key=lambda item: (
            0 if item.reap_candidate else 1,
            0 if item.status == "zombie" else 1,
            -(item.age_hours or -1.0),
            item.project_slug or "",
            item.session_id,
        )
    )
    return records


def _inspect_debug_signals(debug_root: Path, limit: int) -> ClaudeDebugSignals:
    if not debug_root.exists():
        return ClaudeDebugSignals(
            logs_scanned=0,
            rate_limit_errors=0,
            permission_blocks=0,
            timeout_errors=0,
            missing_tool_errors=0,
            mcp_servers=(),
        )

    logs = sorted(
        (path for path in debug_root.glob("*.txt") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if limit >= 0:
        logs = logs[:limit]

    rate_limit_errors = 0
    permission_blocks = 0
    timeout_errors = 0
    missing_tool_errors = 0
    latencies: dict[str, list[int]] = {}

    for log_path in logs:
        try:
            content = log_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        rate_limit_errors += len(RATE_LIMIT_RE.findall(content))
        permission_blocks += len(PERMISSION_BLOCK_RE.findall(content))
        timeout_errors += len(TIMEOUT_RE.findall(content))
        missing_tool_errors += len(MISSING_TOOL_RE.findall(content))
        for match in MCP_CONNECT_RE.finditer(content):
            latencies.setdefault(match.group(1), []).append(int(match.group(2)))

    servers = tuple(
        sorted(
            (
                ClaudeMCPServerLatency(
                    server=server,
                    count=len(values),
                    average_ms=mean(values),
                    max_ms=max(values),
                )
                for server, values in latencies.items()
            ),
            key=lambda item: (-item.average_ms, item.server),
        )
    )
    return ClaudeDebugSignals(
        logs_scanned=len(logs),
        rate_limit_errors=rate_limit_errors,
        permission_blocks=permission_blocks,
        timeout_errors=timeout_errors,
        missing_tool_errors=missing_tool_errors,
        mcp_servers=servers,
    )


def _archive_destination(
    archive_root: Path,
    session: ClaudeSessionHealth,
    source: Path,
    kind: str,
) -> Path:
    project_slug = session.project_slug or "_orphans"
    if kind == "debug":
        return archive_root / "debug" / source.name
    return archive_root / "projects" / project_slug / source.name


def _iter_session_paths(session: ClaudeSessionHealth) -> list[tuple[str, Path]]:
    paths: list[tuple[str, Path]] = []
    if session.transcript_path and session.transcript_path.exists():
        paths.append(("transcript", session.transcript_path))
    if session.artifacts_dir and session.artifacts_dir.exists():
        paths.append(("artifacts", session.artifacts_dir))
    if session.debug_log_path and session.debug_log_path.exists():
        paths.append(("debug", session.debug_log_path))
    return paths


def _string_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _path_mtime(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def _tree_mtime(path: Path) -> datetime | None:
    latest = _path_mtime(path)
    if latest is None or not path.exists():
        return latest
    try:
        for child in path.rglob("*"):
            child_mtime = _path_mtime(child)
            if child_mtime and child_mtime > latest:
                latest = child_mtime
    except OSError:
        return latest
    return latest


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)
