# Plugins

AFS plugins are regular Python modules/packages that expose optional hooks.
They are discovered by name prefix and can live outside the repo.

## Discovery Rules

AFS discovers plugins by:
- Name prefix: `afs_plugin` (or `afs_scawful` if enabled)
- Configured `plugin_dirs`
- `AFS_PLUGIN_DIRS` (colon-separated on macOS/Linux)
- Default directories: `~/.config/afs/plugins` and `~/.afs/plugins`

To enable specific plugins regardless of auto-discovery, set:

```bash
export AFS_ENABLED_PLUGINS="afs_plugin_hello"
```

## Quickstart (no build required)

Use the skeleton in `examples/plugin_skeleton`:

```bash
export AFS_PLUGIN_DIRS="$PWD/examples/plugin_skeleton"
./scripts/afs plugins --details
./scripts/afs hello
```

## Supported Hooks

- `register_cli(subparsers)` or `register_parsers(subparsers)`
- `register_backend()` (generator backends)
- `register_converter()` (training converters)

Run `afs plugins --json` to inspect resolved plugin config.

## Extension Manifests

AFS also supports non-Python extension manifests in `extension.toml` files.

- Discovery roots: `extensions/`, `~/.config/afs/extensions`, `~/.afs/extensions`
- Config: `[extensions]` in `afs.toml`
- Env overrides:
  - `AFS_EXTENSION_DIRS`
  - `AFS_ENABLED_EXTENSIONS`

Each extension can declare:

- `knowledge_mounts`
- `skill_roots`
- `model_registries`
- `cli_modules`
- `policies`
- `[hooks]` (`before_context_read`, `after_context_write`, `before_agent_dispatch`)

Use `afs plugins --details` or `afs plugins --json` to inspect both plugin and extension resolution.
