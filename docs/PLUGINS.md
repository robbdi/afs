# Plugins and Extensions

AFS supports two extension mechanisms:

- Python plugins (runtime hooks)
- Manifest-based extensions (`extension.toml`)

## Python Plugins

Discovery inputs:

- Name prefix (`afs_plugin`, optionally `afs_ext`)
- Configured `plugin_dirs`
- `AFS_PLUGIN_DIRS`
- Default directories: `~/.config/afs/plugins`, `~/.afs/plugins`

Enable explicitly:

```bash
export AFS_ENABLED_PLUGINS="afs_plugin_hello"
```

Supported plugin hooks:

- `register_cli(subparsers)`
- `register_parsers(subparsers)`
- `register_backend()`

Inspect resolved plugin state:

```bash
./scripts/afs plugins --details
./scripts/afs plugins --json
```

## Manifest Extensions

Extensions are discovered from `extension.toml` files.

Discovery roots:

- `AFS_EXTENSION_DIRS`
- configured `extension_dirs`
- `extensions/`
- `~/.config/afs/extensions`
- `~/.afs/extensions`

Config and env:

- `[extensions]` in `afs.toml`
- `AFS_EXTENSION_DIRS`
- `AFS_ENABLED_EXTENSIONS`

Manifest fields:

- `knowledge_mounts`
- `skill_roots`
- `model_registries`
- `cli_modules`
- `agent_modules`
- `policies`
- `[hooks]`
- `[mcp_tools]`
- `[mcp_server]`

`agent_modules` let an extension register extra `afs agents run ...` entries without
putting personal or domain-specific agent code into core `afs`.

When two extension roots contain the same manifest `name`, the first discovery
root wins. That means repo-local or context-local extension dirs can safely
override an older user-global install with the same name.

`[mcp_tools]` example:

```toml
[mcp_tools]
module = "my_extension.mcp_tools"
factory = "register_mcp_tools"
```

`[mcp_server]` is the broader surface. It can register tools, resources, and
prompts from one extension module:

```toml
[mcp_server]
module = "my_extension.mcp_surface"
factory = "register_mcp_server"
```

Expected factory shape:

```python
def register_mcp_server(_manager):
    return {
        "tools": [...],
        "resources": [...],
        "prompts": [...],
    }
```

Legacy `[mcp_tools]` remains supported for tool-only extensions. Core MCP
resource URIs and prompt names are reserved and cannot be overridden.

## Bundles

`afs bundle install` materializes a bundle as a normal manifest extension. In
addition to copying `knowledge/` and `skills/`, it can generate:

- an `agent_modules` shim from bundled profile `agent_configs`
- an `[mcp_server]` shim from bundled profile `mcp_tools`
- `profile-snippet.toml` for safe profile reactivation

That keeps bundles portable without requiring manual extension glue after
install.
