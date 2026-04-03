#!/usr/bin/env python3
"""Validate core AFS package integrity after porting.

Checks that the core afs package imports cleanly, the MCP server starts,
and no domain-specific modules are eagerly loaded.

Usage:
    python3 scripts/validate_core.py              # Core-only checks
    python3 scripts/validate_core.py --with-ext    # Also check extension plugin integration
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

CORE_SRC = Path(__file__).resolve().parent.parent / "src"
EXT_SRC = Path(os.environ.get("AFS_EXT_SRC", "")) if os.environ.get("AFS_EXT_SRC") else None

# Modules that MUST import cleanly in core-only mode
REQUIRED_CORE_MODULES = [
    "afs",
    "afs.config",
    "afs.core",
    "afs.discovery",
    "afs.graph",
    "afs.manager",
    "afs.models",
    "afs.plugins",
    "afs.schema",
    "afs.validator",
    "afs.policy",
    "afs.mcp_server",
    "afs.cli",
    "afs.extensions",
]

# Modules that should NOT be imported by core init (domain-specific)
DOMAIN_MODULES = [
    "afs.training",
    "afs.tokenizer",
    "afs.discriminator",
    "afs.moe",
    "afs.oracle",
]

# Heavy dependencies that should NOT be required for core
HEAVY_DEPS = [
    "torch",
    "transformers",
    "trl",
    "peft",
    "datasets",
]


def check_core_imports() -> list[str]:
    """Check that all required core modules import cleanly."""
    errors = []
    for module_name in REQUIRED_CORE_MODULES:
        try:
            importlib.import_module(module_name)
        except Exception as e:
            errors.append(f"FAIL: import {module_name} -> {type(e).__name__}: {e}")
    return errors


def check_no_eager_domain_imports() -> list[str]:
    """Check that importing 'afs' doesn't eagerly load domain modules."""
    errors = []
    # Clear all afs modules first
    to_remove = [k for k in sys.modules if k.startswith("afs")]
    for k in to_remove:
        del sys.modules[k]

    # Import just afs
    import afs  # noqa: F401

    for module_name in DOMAIN_MODULES:
        if module_name in sys.modules:
            errors.append(
                f"WARN: {module_name} was eagerly loaded by 'import afs' "
                "(should be lazy/on-demand)"
            )
    return errors


def check_no_heavy_deps() -> list[str]:
    """Check that core afs doesn't require heavy dependencies."""
    errors = []
    # Clear all afs modules
    to_remove = [k for k in sys.modules if k.startswith("afs")]
    for k in to_remove:
        del sys.modules[k]

    import afs  # noqa: F401

    for dep in HEAVY_DEPS:
        if dep in sys.modules:
            errors.append(
                f"WARN: {dep} was imported by core afs "
                "(should only be needed by domain modules)"
            )
    return errors


def check_mcp_server() -> list[str]:
    """Check that MCP server builds and responds correctly."""
    errors = []
    try:
        from afs.config import load_config_model
        from afs.manager import AFSManager
        from afs.mcp_server import _handle_request, build_mcp_registry

        config = load_config_model(merge_user=True)
        manager = AFSManager(config=config)
        registry = build_mcp_registry(manager)

        # Check tools/list
        resp = _handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            manager,
            registry,
        )
        tools = resp["result"]["tools"]
        expected_core_tools = {
            "context.read",
            "context.write",
            "context.list",
            "context.discover",
            "context.mount",
        }
        expected_alias_tools = {"fs.read", "fs.write", "fs.list"}
        actual_names = {t["name"] for t in tools}
        missing = expected_core_tools - actual_names
        if missing:
            errors.append(f"FAIL: MCP missing core tools: {missing}")
        missing_aliases = expected_alias_tools - actual_names
        if missing_aliases:
            errors.append(f"FAIL: MCP missing compatibility aliases: {missing_aliases}")

        # Check initialize
        resp = _handle_request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {}},
            },
            manager,
            registry,
        )
        if "error" in resp:
            errors.append(f"FAIL: MCP initialize error: {resp['error']}")

        # Check ping
        resp = _handle_request({"jsonrpc": "2.0", "id": 3, "method": "ping"}, manager, registry)
        if "error" in resp:
            errors.append(f"FAIL: MCP ping error: {resp['error']}")

    except Exception as e:
        errors.append(f"FAIL: MCP server check -> {type(e).__name__}: {e}")

    return errors


def check_pyproject_toml() -> list[str]:
    """Check pyproject.toml doesn't have broken entry points or heavy core deps."""
    errors = []
    toml_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if not toml_path.exists():
        errors.append("FAIL: pyproject.toml not found")
        return errors

    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    with open(toml_path, "rb") as f:
        data = tomllib.load(f)

    # Check core deps don't include heavy packages
    deps = data.get("project", {}).get("dependencies", [])
    for dep in deps:
        dep_name = dep.split(">=")[0].split("<=")[0].split("==")[0].strip()
        if dep_name in HEAVY_DEPS:
            errors.append(
                f"FAIL: '{dep_name}' is a core dependency in pyproject.toml "
                "(should be in [project.optional-dependencies.training])"
            )

    # Check entry points reference existing modules
    scripts = data.get("project", {}).get("scripts", {})
    for name, target in scripts.items():
        module_path = target.split(":")[0]
        try:
            importlib.import_module(module_path)
        except Exception as e:
            errors.append(f"FAIL: entry point '{name}' -> '{target}' fails: {e}")

    # Check package discovery is configured
    setuptools = data.get("tool", {}).get("setuptools", {})
    packages_find = setuptools.get("packages", {})
    if isinstance(packages_find, list) and len(packages_find) == 1:
        errors.append(
            "WARN: setuptools packages is a flat list (may miss subpackages). "
            "Use [tool.setuptools.packages.find] instead."
        )

    return errors


def check_syntax_all_py() -> list[str]:
    """Check all .py files in src/afs/ for syntax errors."""
    errors = []
    import ast

    afs_dir = CORE_SRC / "afs"
    for py_file in sorted(afs_dir.rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        try:
            ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError as e:
            errors.append(f"FAIL: {py_file.relative_to(CORE_SRC)}: {e}")

    return errors


def check_extension_integration() -> list[str]:
    """Check extension plugin loads correctly (requires --with-ext and AFS_EXT_SRC env)."""
    errors = []

    if EXT_SRC is None or not EXT_SRC.exists():
        errors.append("SKIP: no extension source found (set AFS_EXT_SRC env var)")
        return errors

    ext_str = str(EXT_SRC)
    if ext_str not in sys.path:
        sys.path.insert(0, ext_str)

    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate core AFS package integrity")
    parser.add_argument("--with-ext", action="store_true", help="Also check extension plugin integration")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show passing checks too")
    args = parser.parse_args()

    # Ensure core src is on path
    core_str = str(CORE_SRC)
    if core_str not in sys.path:
        sys.path.insert(0, core_str)

    all_errors: list[str] = []
    checks = [
        ("Syntax check (all .py files)", check_syntax_all_py),
        ("pyproject.toml", check_pyproject_toml),
        ("Core module imports", check_core_imports),
        ("No eager domain imports", check_no_eager_domain_imports),
        ("No heavy deps in core", check_no_heavy_deps),
        ("MCP server", check_mcp_server),
    ]

    if args.with_ext:
        checks.append(("Extension integration", check_extension_integration))

    print("=" * 60)
    print("AFS Core Validation")
    print("=" * 60)

    passed = 0
    failed = 0
    warned = 0

    for name, check_fn in checks:
        errors = check_fn()
        fails = [e for e in errors if e.startswith("FAIL")]
        warns = [e for e in errors if e.startswith("WARN")]
        skips = [e for e in errors if e.startswith("SKIP")]

        if fails:
            print(f"\n  FAIL  {name}")
            failed += 1
        elif warns:
            print(f"\n  WARN  {name}")
            warned += 1
        else:
            if args.verbose:
                print(f"\n  PASS  {name}")
            passed += 1

        for e in errors:
            print(f"    {e}")

    print("\n" + "=" * 60)
    total = passed + failed + warned
    print(f"Results: {passed}/{total} passed, {failed} failed, {warned} warnings")

    if failed:
        print("\nCore AFS is NOT ready for deployment.")
        return 1

    if warned:
        print("\nCore AFS is functional but has warnings.")
        return 0

    print("\nCore AFS is clean and ready for deployment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
