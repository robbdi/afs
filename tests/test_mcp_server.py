from __future__ import annotations

from pathlib import Path

from afs.manager import AFSManager
from afs.mcp_server import _handle_request, build_mcp_registry
from afs.schema import AFSConfig, ContextIndexConfig, ExtensionsConfig, GeneralConfig


def _make_manager(tmp_path: Path) -> AFSManager:
    context_root = tmp_path / "context"
    context_root.mkdir(parents=True)
    (context_root / "scratchpad").mkdir()
    general = GeneralConfig(
        context_root=context_root,
        agent_workspaces_dir=context_root / "workspaces",
    )
    return AFSManager(config=AFSConfig(general=general))


def test_tools_list_returns_afs_tools(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    response = _handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, manager)
    assert response is not None
    tools = response["result"]["tools"]
    names = {tool["name"] for tool in tools}
    assert {
        "fs.read",
        "fs.write",
        "fs.delete",
        "fs.move",
        "fs.list",
        "context.discover",
        "context.init",
        "context.mount",
        "context.unmount",
        "context.index.rebuild",
        "context.query",
    }.issubset(names)


def test_fs_write_and_read_tool_calls(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    target = manager.config.general.context_root / "scratchpad" / "notes.txt"

    write_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "fs.write",
                "arguments": {"path": str(target), "content": "hello", "mkdirs": True},
            },
        },
        manager,
    )
    assert write_response is not None
    assert write_response["result"]["structuredContent"]["bytes"] == 5

    read_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "fs.read",
                "arguments": {"path": str(target)},
            },
        },
        manager,
    )
    assert read_response is not None
    assert read_response["result"]["structuredContent"]["content"] == "hello"


def test_context_init_tool_creates_project_context(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    project_root = tmp_path / "workspace_project"
    project_root.mkdir(parents=True)

    init_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 31,
            "method": "tools/call",
            "params": {
                "name": "context.init",
                "arguments": {"project_path": str(project_root)},
            },
        },
        manager,
    )
    assert init_response is not None
    structured = init_response["result"]["structuredContent"]
    assert structured["context_path"] == str(project_root / ".context")
    assert (project_root / ".context").exists()


def test_context_unmount_tool_removes_alias(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    context_root = manager.config.general.context_root
    (context_root / "knowledge").mkdir(exist_ok=True)

    source_docs = tmp_path / "docs_source"
    source_docs.mkdir(parents=True)

    mount_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 32,
            "method": "tools/call",
            "params": {
                "name": "context.mount",
                "arguments": {
                    "context_path": str(context_root),
                    "source": str(source_docs),
                    "mount_type": "knowledge",
                    "alias": "docs",
                },
            },
        },
        manager,
    )
    assert mount_response is not None
    assert (context_root / "knowledge" / "docs").exists()

    unmount_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 33,
            "method": "tools/call",
            "params": {
                "name": "context.unmount",
                "arguments": {
                    "context_path": str(context_root),
                    "mount_type": "knowledge",
                    "alias": "docs",
                },
            },
        },
        manager,
    )
    assert unmount_response is not None
    structured = unmount_response["result"]["structuredContent"]
    assert structured["removed"] is True
    assert not (context_root / "knowledge" / "docs").exists()


def test_context_index_rebuild_tool(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    context_root = manager.config.general.context_root
    notes = context_root / "scratchpad" / "notes.txt"
    notes.write_text("portable sqlite index", encoding="utf-8")

    rebuild_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "context.index.rebuild",
                "arguments": {
                    "context_path": str(context_root),
                    "mount_types": ["scratchpad"],
                    "include_content": True,
                },
            },
        },
        manager,
    )
    assert rebuild_response is not None
    structured = rebuild_response["result"]["structuredContent"]
    assert structured["rows_written"] >= 1
    assert structured["by_mount_type"]["scratchpad"] >= 1
    assert structured["db_path"].endswith("context_index.sqlite3")


def test_context_index_uses_configured_db_filename(tmp_path: Path) -> None:
    context_root = tmp_path / "context"
    context_root.mkdir(parents=True)
    (context_root / "scratchpad").mkdir()
    manager = AFSManager(
        config=AFSConfig(
            general=GeneralConfig(
                context_root=context_root,
                agent_workspaces_dir=context_root / "workspaces",
            ),
            context_index=ContextIndexConfig(db_filename="sqlite/context.db"),
        )
    )
    notes = context_root / "scratchpad" / "notes.txt"
    notes.write_text("custom db path", encoding="utf-8")

    rebuild_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 40,
            "method": "tools/call",
            "params": {
                "name": "context.index.rebuild",
                "arguments": {
                    "context_path": str(context_root),
                    "mount_types": ["scratchpad"],
                },
            },
        },
        manager,
    )
    assert rebuild_response is not None
    db_path = rebuild_response["result"]["structuredContent"]["db_path"]
    assert db_path.endswith("global/sqlite/context.db")


def test_context_query_tool_auto_indexes(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    context_root = manager.config.general.context_root
    note_path = context_root / "scratchpad" / "gemini_notes.md"
    note_path.write_text("Gemini-compatible context query support", encoding="utf-8")

    query_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "context.query",
                "arguments": {
                    "context_path": str(context_root),
                    "mount_types": ["scratchpad"],
                    "query": "Gemini-compatible",
                    "limit": 10,
                },
            },
        },
        manager,
    )
    assert query_response is not None
    structured = query_response["result"]["structuredContent"]
    assert structured["count"] >= 1
    assert any(entry["relative_path"] == "gemini_notes.md" for entry in structured["entries"])
    assert "index_rebuild" in structured


def test_context_query_respects_auto_index_config_default(tmp_path: Path) -> None:
    context_root = tmp_path / "context"
    context_root.mkdir(parents=True)
    (context_root / "scratchpad").mkdir()
    manager = AFSManager(
        config=AFSConfig(
            general=GeneralConfig(
                context_root=context_root,
                agent_workspaces_dir=context_root / "workspaces",
            ),
            context_index=ContextIndexConfig(auto_index=False),
        )
    )
    note_path = context_root / "scratchpad" / "manual_index.md"
    note_path.write_text("manual indexing required", encoding="utf-8")

    query_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 41,
            "method": "tools/call",
            "params": {
                "name": "context.query",
                "arguments": {
                    "context_path": str(context_root),
                    "mount_types": ["scratchpad"],
                    "query": "manual indexing required",
                },
            },
        },
        manager,
    )
    assert query_response is not None
    structured = query_response["result"]["structuredContent"]
    assert structured["count"] == 0
    assert "index_rebuild" not in structured


def test_context_query_indexes_symlink_mount_content(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    context_root = manager.config.general.context_root
    knowledge_root = context_root / "knowledge"
    knowledge_root.mkdir(exist_ok=True)

    source_docs = tmp_path / "source_docs"
    source_docs.mkdir()
    (source_docs / "design.md").write_text("SQLite indexing for mounted docs", encoding="utf-8")
    (knowledge_root / "docs").symlink_to(source_docs, target_is_directory=True)

    query_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "context.query",
                "arguments": {
                    "context_path": str(context_root),
                    "mount_types": ["knowledge"],
                    "query": "mounted docs",
                    "limit": 10,
                },
            },
        },
        manager,
    )
    assert query_response is not None
    structured = query_response["result"]["structuredContent"]
    assert any(entry["relative_path"] == "docs/design.md" for entry in structured["entries"])


def test_fs_write_keeps_context_query_fresh_without_rebuild(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    context_root = manager.config.general.context_root
    target = context_root / "scratchpad" / "state.md"
    target.write_text("initial context", encoding="utf-8")

    rebuild_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "context.index.rebuild",
                "arguments": {
                    "context_path": str(context_root),
                    "mount_types": ["scratchpad"],
                },
            },
        },
        manager,
    )
    assert rebuild_response is not None

    write_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {
                "name": "fs.write",
                "arguments": {
                    "path": str(target),
                    "content": "incremental freshness check",
                },
            },
        },
        manager,
    )
    assert write_response is not None
    assert write_response["result"]["structuredContent"]["index_updated"] is True

    query_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {
                "name": "context.query",
                "arguments": {
                    "context_path": str(context_root),
                    "mount_types": ["scratchpad"],
                    "query": "freshness",
                    "auto_index": False,
                },
            },
        },
        manager,
    )
    assert query_response is not None
    structured = query_response["result"]["structuredContent"]
    assert any(entry["relative_path"] == "state.md" for entry in structured["entries"])
    assert "index_rebuild" not in structured


def test_fs_delete_updates_context_index(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    context_root = manager.config.general.context_root
    target = context_root / "scratchpad" / "delete_me.md"
    target.write_text("remove from index", encoding="utf-8")

    rebuild_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 13,
            "method": "tools/call",
            "params": {
                "name": "context.index.rebuild",
                "arguments": {
                    "context_path": str(context_root),
                    "mount_types": ["scratchpad"],
                },
            },
        },
        manager,
    )
    assert rebuild_response is not None

    delete_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 14,
            "method": "tools/call",
            "params": {
                "name": "fs.delete",
                "arguments": {"path": str(target)},
            },
        },
        manager,
    )
    assert delete_response is not None
    assert delete_response["result"]["structuredContent"]["index_updated"] is True

    query_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 15,
            "method": "tools/call",
            "params": {
                "name": "context.query",
                "arguments": {
                    "context_path": str(context_root),
                    "mount_types": ["scratchpad"],
                    "query": "remove from index",
                    "auto_index": False,
                },
            },
        },
        manager,
    )
    assert query_response is not None
    entries = query_response["result"]["structuredContent"]["entries"]
    assert not any(entry["relative_path"] == "delete_me.md" for entry in entries)


def test_fs_move_updates_context_index(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    context_root = manager.config.general.context_root
    source = context_root / "scratchpad" / "before.md"
    destination = context_root / "scratchpad" / "after.md"
    source.write_text("moved content marker", encoding="utf-8")

    rebuild_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 16,
            "method": "tools/call",
            "params": {
                "name": "context.index.rebuild",
                "arguments": {
                    "context_path": str(context_root),
                    "mount_types": ["scratchpad"],
                },
            },
        },
        manager,
    )
    assert rebuild_response is not None

    move_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 17,
            "method": "tools/call",
            "params": {
                "name": "fs.move",
                "arguments": {"source": str(source), "destination": str(destination)},
            },
        },
        manager,
    )
    assert move_response is not None
    payload = move_response["result"]["structuredContent"]
    assert payload["index_updated"] is True
    assert destination.exists()
    assert not source.exists()

    query_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 18,
            "method": "tools/call",
            "params": {
                "name": "context.query",
                "arguments": {
                    "context_path": str(context_root),
                    "mount_types": ["scratchpad"],
                    "query": "moved content marker",
                    "auto_index": False,
                },
            },
        },
        manager,
    )
    assert query_response is not None
    entries = query_response["result"]["structuredContent"]["entries"]
    assert any(entry["relative_path"] == "after.md" for entry in entries)
    assert not any(entry["relative_path"] == "before.md" for entry in entries)


def test_context_query_auto_refreshes_after_external_write(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    context_root = manager.config.general.context_root
    target = context_root / "scratchpad" / "external.md"
    target.write_text("before external edit", encoding="utf-8")

    rebuild_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "context.index.rebuild",
                "arguments": {
                    "context_path": str(context_root),
                    "mount_types": ["scratchpad"],
                },
            },
        },
        manager,
    )
    assert rebuild_response is not None

    target.write_text("after external edit", encoding="utf-8")

    query_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "context.query",
                "arguments": {
                    "context_path": str(context_root),
                    "mount_types": ["scratchpad"],
                    "query": "external edit",
                    "auto_index": True,
                },
            },
        },
        manager,
    )
    assert query_response is not None
    structured = query_response["result"]["structuredContent"]
    assert any(entry["relative_path"] == "external.md" for entry in structured["entries"])
    assert "index_rebuild" in structured


def test_initialize_advertises_resources_and_prompts(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    response = _handle_request(
        {"jsonrpc": "2.0", "id": 20, "method": "initialize", "params": {}}, manager
    )
    assert response is not None
    caps = response["result"]["capabilities"]
    assert "tools" in caps
    assert "resources" in caps
    assert "prompts" in caps


def test_resources_list_returns_contexts_resource(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    response = _handle_request(
        {"jsonrpc": "2.0", "id": 21, "method": "resources/list"}, manager
    )
    assert response is not None
    resources = response["result"]["resources"]
    uris = [r["uri"] for r in resources]
    assert "afs://contexts" in uris


def test_resources_read_contexts(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 22,
            "method": "resources/read",
            "params": {"uri": "afs://contexts"},
        },
        manager,
    )
    assert response is not None
    contents = response["result"]["contents"]
    assert len(contents) == 1
    assert contents[0]["uri"] == "afs://contexts"
    assert contents[0]["mimeType"] == "application/json"
    import json
    data = json.loads(contents[0]["text"])
    assert isinstance(data, list)


def test_resources_read_metadata(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    context_root = manager.config.general.context_root
    import json
    (context_root / "metadata.json").write_text(
        json.dumps({"created_at": "2025-01-01", "description": "test", "agents": []}),
        encoding="utf-8",
    )
    uri = f"afs://context/{context_root}/metadata"
    response = _handle_request(
        {"jsonrpc": "2.0", "id": 23, "method": "resources/read", "params": {"uri": uri}},
        manager,
    )
    assert response is not None
    contents = response["result"]["contents"]
    assert len(contents) == 1
    data = json.loads(contents[0]["text"])
    assert data["description"] == "test"


def test_resources_read_index(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    context_root = manager.config.general.context_root
    uri = f"afs://context/{context_root}/index"
    response = _handle_request(
        {"jsonrpc": "2.0", "id": 24, "method": "resources/read", "params": {"uri": uri}},
        manager,
    )
    assert response is not None
    contents = response["result"]["contents"]
    assert len(contents) == 1
    import json
    data = json.loads(contents[0]["text"])
    assert "has_entries" in data
    assert "needs_refresh" in data


def test_resources_read_unknown_uri(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 25,
            "method": "resources/read",
            "params": {"uri": "afs://unknown"},
        },
        manager,
    )
    assert response is not None
    assert "error" in response


def test_prompts_list_returns_expected_prompts(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    response = _handle_request(
        {"jsonrpc": "2.0", "id": 26, "method": "prompts/list"}, manager
    )
    assert response is not None
    prompts = response["result"]["prompts"]
    names = {p["name"] for p in prompts}
    assert {"afs.context.overview", "afs.query.search", "afs.scratchpad.review"}.issubset(names)
    # Verify argument schemas
    for prompt in prompts:
        assert "arguments" in prompt
        assert isinstance(prompt["arguments"], list)


def test_prompts_get_context_overview(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    context_root = manager.config.general.context_root
    import json
    (context_root / "metadata.json").write_text(
        json.dumps({
            "created_at": "2025-01-01",
            "description": "test project",
            "agents": ["claude"],
            "directories": {},
            "manual_only": [],
        }),
        encoding="utf-8",
    )
    response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 27,
            "method": "prompts/get",
            "params": {
                "name": "afs.context.overview",
                "arguments": {"context_path": str(context_root)},
            },
        },
        manager,
    )
    assert response is not None
    messages = response["result"]["messages"]
    assert len(messages) >= 1
    assert messages[0]["role"] == "user"
    assert "AFS Context" in messages[0]["content"]["text"]


def test_prompts_get_query_search(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    context_root = manager.config.general.context_root
    (context_root / "scratchpad" / "notes.txt").write_text(
        "prompt search test content", encoding="utf-8"
    )
    response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 28,
            "method": "prompts/get",
            "params": {
                "name": "afs.query.search",
                "arguments": {"query": "prompt search"},
            },
        },
        manager,
    )
    assert response is not None
    messages = response["result"]["messages"]
    assert len(messages) >= 1
    assert messages[0]["role"] == "user"
    text = messages[0]["content"]["text"]
    assert "prompt search" in text.lower() or "Search results" in text


def test_prompts_get_scratchpad_review(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    context_root = manager.config.general.context_root
    (context_root / "scratchpad" / "state.md").write_text(
        "current state info", encoding="utf-8"
    )
    (context_root / "scratchpad" / "deferred.md").write_text(
        "deferred task list", encoding="utf-8"
    )
    response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 29,
            "method": "prompts/get",
            "params": {
                "name": "afs.scratchpad.review",
                "arguments": {"context_path": str(context_root)},
            },
        },
        manager,
    )
    assert response is not None
    messages = response["result"]["messages"]
    assert len(messages) >= 1
    text = messages[0]["content"]["text"]
    assert "current state info" in text
    assert "deferred task list" in text


def test_prompts_get_unknown_prompt(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 30,
            "method": "prompts/get",
            "params": {"name": "nonexistent", "arguments": {}},
        },
        manager,
    )
    assert response is not None
    assert "error" in response


def test_extension_mcp_tools_are_registered_and_callable(tmp_path: Path) -> None:
    ext_root = tmp_path / "extensions"
    ext_dir = ext_root / "ext_workspace"
    ext_dir.mkdir(parents=True)
    (ext_dir / "extension.toml").write_text(
        "name = \"ext_workspace\"\n"
        "\n"
        "[mcp_tools]\n"
        "module = \"ext_mcp\"\n"
        "factory = \"register_mcp_tools\"\n",
        encoding="utf-8",
    )
    (ext_dir / "ext_mcp.py").write_text(
        "def register_mcp_tools(_manager):\n"
        "    def echo(arguments):\n"
        "        value = arguments.get('value', '')\n"
        "        return {'echo': value}\n"
        "    return [\n"
        "        {\n"
        "            'name': 'workspace.echo',\n"
        "            'description': 'Echo test payload',\n"
        "            'inputSchema': {\n"
        "                'type': 'object',\n"
        "                'properties': {'value': {'type': 'string'}},\n"
        "                'additionalProperties': False,\n"
        "            },\n"
        "            'handler': echo,\n"
        "        }\n"
        "    ]\n",
        encoding="utf-8",
    )

    context_root = tmp_path / "context"
    context_root.mkdir(parents=True)
    (context_root / "scratchpad").mkdir()
    manager = AFSManager(
        config=AFSConfig(
            general=GeneralConfig(
                context_root=context_root,
                agent_workspaces_dir=context_root / "workspaces",
            ),
            extensions=ExtensionsConfig(
                enabled_extensions=["ext_workspace"],
                extension_dirs=[ext_root],
            ),
        )
    )

    registry = build_mcp_registry(manager)
    assert "workspace.echo" in registry.tools

    call_response = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 19,
            "method": "tools/call",
            "params": {
                "name": "workspace.echo",
                "arguments": {"value": "ok"},
            },
        },
        manager,
        registry=registry,
    )
    assert call_response is not None
    assert call_response["result"]["structuredContent"]["echo"] == "ok"
