"""Lightweight MCP server exposing AFS context operations over stdio."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .config import load_config_model
from .discovery import discover_contexts
from .manager import AFSManager
from .models import MountType

SERVER_NAME = "afs"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"


def _read_message(stream) -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if line == b"":
            return None
        if line in (b"\r\n", b"\n"):
            break
        if b":" not in line:
            continue
        key, value = line.decode("utf-8", errors="replace").split(":", 1)
        headers[key.strip().lower()] = value.strip()

    length_raw = headers.get("content-length")
    if not length_raw:
        return None
    try:
        length = int(length_raw)
    except ValueError:
        return None
    body = stream.read(length)
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def _write_message(stream, payload: dict[str, Any]) -> None:
    raw = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    header = f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii")
    stream.write(header)
    stream.write(raw)
    stream.flush()


def _error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _success_response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _allowed_roots(manager: AFSManager) -> list[Path]:
    roots: list[Path] = []

    home_context = (Path.home() / ".context").resolve()
    roots.append(home_context)

    config_root = manager.config.general.context_root.resolve()
    if config_root not in roots:
        roots.append(config_root)

    local_context = (Path.cwd() / ".context").resolve()
    if local_context.exists() and local_context not in roots:
        roots.append(local_context)

    return roots


def _assert_allowed(path: Path, manager: AFSManager) -> Path:
    resolved = path.expanduser().resolve()
    for root in _allowed_roots(manager):
        if resolved == root or resolved.is_relative_to(root):
            return resolved
    raise PermissionError(f"Path outside allowed roots: {resolved}")


def _resolve_context_path(arguments: dict[str, Any], manager: AFSManager) -> Path:
    raw = arguments.get("context_path")
    if isinstance(raw, str) and raw.strip():
        return _assert_allowed(Path(raw), manager)
    default = Path.cwd() / ".context"
    return _assert_allowed(default, manager)


def _tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "name": "fs.read",
            "description": "Read UTF-8 text from a context-scoped file.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative file path."},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
        {
            "name": "fs.write",
            "description": "Write UTF-8 text to a context-scoped file.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "append": {"type": "boolean", "default": False},
                    "mkdirs": {"type": "boolean", "default": False},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
        {
            "name": "fs.list",
            "description": "List files under a context-scoped path.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "max_depth": {"type": "integer", "default": 1},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
        {
            "name": "context.discover",
            "description": "Discover project .context roots.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "search_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "max_depth": {"type": "integer", "default": 3},
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "context.mount",
            "description": "Mount a source path into a context mount type.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "context_path": {"type": "string"},
                    "source": {"type": "string"},
                    "mount_type": {
                        "type": "string",
                        "enum": [mount.value for mount in MountType],
                    },
                    "alias": {"type": "string"},
                },
                "required": ["source", "mount_type"],
                "additionalProperties": False,
            },
        },
    ]


def _as_text_result(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=True)}],
        "structuredContent": payload,
    }


def _handle_tool_call(name: str, arguments: dict[str, Any], manager: AFSManager) -> dict[str, Any]:
    if name == "fs.read":
        path_value = arguments.get("path")
        if not isinstance(path_value, str):
            raise ValueError("path must be a string")
        path = _assert_allowed(Path(path_value), manager)
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        if path.is_dir():
            raise IsADirectoryError(f"Path is a directory: {path}")
        return {
            "path": str(path),
            "content": path.read_text(encoding="utf-8", errors="replace"),
        }

    if name == "fs.write":
        path_value = arguments.get("path")
        content = arguments.get("content")
        append = bool(arguments.get("append", False))
        mkdirs = bool(arguments.get("mkdirs", False))
        if not isinstance(path_value, str) or not isinstance(content, str):
            raise ValueError("path and content must be strings")

        path = _assert_allowed(Path(path_value), manager)
        if not path.parent.exists():
            if not mkdirs:
                raise FileNotFoundError(f"Parent directory missing: {path.parent}")
            path.parent.mkdir(parents=True, exist_ok=True)

        mode = "a" if append else "w"
        with path.open(mode, encoding="utf-8") as handle:
            handle.write(content)
        return {"path": str(path), "bytes": len(content.encode("utf-8")), "append": append}

    if name == "fs.list":
        path_value = arguments.get("path")
        max_depth = arguments.get("max_depth", 1)
        if not isinstance(path_value, str):
            raise ValueError("path must be a string")
        if not isinstance(max_depth, int):
            max_depth = 1

        root = _assert_allowed(Path(path_value), manager)
        if not root.exists():
            raise FileNotFoundError(f"Path not found: {root}")

        entries: list[dict[str, Any]] = []
        if root.is_file():
            entries.append({"path": str(root), "is_dir": False})
        else:
            for candidate in root.rglob("*"):
                try:
                    depth = len(candidate.relative_to(root).parts)
                except Exception:
                    continue
                if max_depth >= 0 and depth > max_depth:
                    continue
                entries.append({"path": str(candidate), "is_dir": candidate.is_dir()})
        return {"path": str(root), "entries": entries}

    if name == "context.discover":
        search_paths_value = arguments.get("search_paths", [])
        max_depth = arguments.get("max_depth", 3)

        search_paths: list[Path] | None = None
        if isinstance(search_paths_value, list):
            values: list[Path] = []
            for item in search_paths_value:
                if isinstance(item, str):
                    values.append(Path(item).expanduser())
            if values:
                search_paths = values

        if not isinstance(max_depth, int):
            max_depth = 3

        contexts = discover_contexts(search_paths=search_paths, max_depth=max_depth, config=manager.config)
        return {
            "contexts": [
                {
                    "project": context.project_name,
                    "path": str(context.path),
                    "valid": context.is_valid,
                    "mounts": context.total_mounts,
                }
                for context in contexts
            ]
        }

    if name == "context.mount":
        context_path = _resolve_context_path(arguments, manager)
        source_value = arguments.get("source")
        mount_type_value = arguments.get("mount_type")
        alias_value = arguments.get("alias")

        if not isinstance(source_value, str):
            raise ValueError("source must be a string")
        if not isinstance(mount_type_value, str):
            raise ValueError("mount_type must be a string")

        source = Path(source_value).expanduser().resolve()
        if not source.exists():
            raise FileNotFoundError(f"Source not found: {source}")

        mount_type = MountType(mount_type_value)
        alias = alias_value if isinstance(alias_value, str) else None
        mount = manager.mount(source, mount_type, alias=alias, context_path=context_path)
        return {
            "context_path": str(context_path),
            "mount": {
                "name": mount.name,
                "mount_type": mount.mount_type.value,
                "source": str(mount.source),
                "is_symlink": mount.is_symlink,
            },
        }

    raise ValueError(f"Unknown tool: {name}")


def _handle_request(request: dict[str, Any], manager: AFSManager) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")

    if method == "initialize":
        return _success_response(
            request_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )

    if method == "notifications/initialized":
        return None

    if method == "ping":
        return _success_response(request_id, {})

    if method == "tools/list":
        return _success_response(request_id, {"tools": _tool_specs()})

    if method == "tools/call":
        params = request.get("params", {})
        if not isinstance(params, dict):
            return _error_response(request_id, -32602, "Invalid params")

        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str):
            return _error_response(request_id, -32602, "Missing tool name")
        if not isinstance(arguments, dict):
            return _error_response(request_id, -32602, "arguments must be object")

        try:
            payload = _handle_tool_call(name, arguments, manager)
        except Exception as exc:
            return _error_response(request_id, -32000, str(exc))

        return _success_response(request_id, _as_text_result(payload))

    if request_id is not None:
        return _error_response(request_id, -32601, f"Method not found: {method}")
    return None


def serve(config_path: Path | None = None) -> int:
    config = load_config_model(config_path=config_path, merge_user=True)
    manager = AFSManager(config=config)

    while True:
        message = _read_message(sys.stdin.buffer)
        if message is None:
            break
        response = _handle_request(message, manager)
        if response is not None:
            _write_message(sys.stdout.buffer, response)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AFS MCP server")
    parser.add_argument("--config", help="Config path override.")
    args = parser.parse_args(argv)
    config_path = Path(args.config).expanduser().resolve() if args.config else None
    return serve(config_path=config_path)


if __name__ == "__main__":
    raise SystemExit(main())
