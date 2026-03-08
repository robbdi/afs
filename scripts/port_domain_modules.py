#!/usr/bin/env python3
"""Port domain-specific modules from core AFS to afs-scawful.

Copies 65816/Zelda-specific modules to afs-scawful, then replaces the originals
with compatibility shims that forward to afs_scawful. Follows the same pattern
already used for oracle/ and moe/.

Usage:
    # Dry run (default) - show what would change
    python3 scripts/port_domain_modules.py

    # Execute the migration
    python3 scripts/port_domain_modules.py --execute

    # Only port specific domains
    python3 scripts/port_domain_modules.py --execute --domains training tokenizer

    # Skip copying (if you already placed files in afs-scawful)
    python3 scripts/port_domain_modules.py --execute --shim-only
"""

from __future__ import annotations

import argparse
import shutil
import textwrap
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CORE_SRC = Path(__file__).resolve().parent.parent / "src" / "afs"
SCAWFUL_SRC = (
    Path(__file__).resolve().parent.parent.parent / "afs-scawful" / "src" / "afs_scawful"
)

# Modules to port: (core_subpackage, scawful_target, files_to_shim)
# If files_to_shim is None, shim the entire package (__init__ + all .py files).
# If files_to_shim is a list, only shim those specific files (partial port).

FULL_PACKAGES = {
    "training": {
        "target": "training",
        "description": "Training utilities (ASM encoder, scoring, exporters, pipeline)",
    },
    "tokenizer": {
        "target": "tokenizer",
        "description": "65816 assembly tokenizer (semantic opcodes/addresses)",
    },
    "discriminator": {
        "target": "discriminator",
        "description": "ASM-ELECTRA discriminator for assembly quality",
    },
}

# Partial ports: only move specific files, keep generic code in core
PARTIAL_PACKAGES = {
    "benchmark": {
        "target": "benchmark",
        "move_files": ["din.py", "nayru.py"],
        "keep_files": ["base.py", "suite.py", "leaderboard.py", "__init__.py"],
        "description": "Domain-specific benchmark runners (Din, Nayru, Farore, Veran)",
    },
    "generators": {
        "target": "generators",
        "move_files": [
            "asar_validator.py",
            "asm_augment.py",
            "curriculum_generator.py",
            "knowledge_generator.py",
            "template_libraries.py",
        ],
        "keep_files": [
            "base.py",
            "model_generator.py",
            "data_cleaner.py",
            "__init__.py",
        ],
        "description": "Domain-specific generators (ASM augment, ASAR, curriculum, knowledge)",
    },
}

# Standalone files to move
STANDALONE_MOVES = {
    "model_router.py": {
        "src": Path(__file__).resolve().parent.parent / "model_router.py",
        "dst_dir": "tools",
        "description": "H-MoE Router for Zelda experts",
    },
    "deploy_to_lmstudio.sh": {
        "src": Path(__file__).resolve().parent.parent / "scripts" / "deploy_to_lmstudio.sh",
        "dst_dir": "scripts",
        "description": "LMStudio deployment script (zelda-* models)",
    },
    "chat-service.sh": {
        "src": Path(__file__).resolve().parent.parent / "scripts" / "chat-service.sh",
        "dst_dir": "scripts",
        "description": "Chat service launcher bound to afs-scawful registry",
    },
    "moe_orchestrator.py": {
        "src": Path(__file__).resolve().parent.parent / "tools" / "moe_orchestrator.py",
        "dst_dir": "tools",
        "description": "MoE orchestrator for Oracle of Secrets",
    },
    "orchestrator.py": {
        "src": Path(__file__).resolve().parent.parent / "tools" / "orchestrator.py",
        "dst_dir": "tools",
        "description": "Registry-driven orchestrator for domain agents",
    },
    "validate_providers.py": {
        "src": Path(__file__).resolve().parent.parent / "tools" / "validate_providers.py",
        "dst_dir": "tools",
        "description": "Provider endpoint validator for afs-scawful registries",
    },
}

# Domain CLI modules to move (not eagerly imported by core CLI)
DOMAIN_CLI_FILES = [
    "training.py",
    "pipeline.py",
    "benchmark.py",
    "tokenizer.py",
    "encoder.py",
    "generator.py",
    "generators.py",
    "entity.py",
    "distillation.py",
    "comparison.py",
    "active_learning.py",
]

# Domain test files to move
DOMAIN_TEST_FILES = [
    "test_asm_augment.py",
    "test_benchmarks.py",
    "test_training_pipeline.py",
    "test_scoring.py",
    "test_registry.py",
    "test_continuous_learning.py",
    "test_integration.py",
    "test_deployment_validator.py",
    "test_quality.py",
    "test_quality_gates.py",
    "test_antigravity_export.py",
    "test_claude_export.py",
    "test_codex_history_import.py",
    "test_codex_export.py",
    "test_gemini_export.py",
    "test_memory_export.py",
    "test_rebalance.py",
]

# Knowledge files to move
KNOWLEDGE_MOVES = {
    "src": Path(__file__).resolve().parent.parent / "knowledge",
    "dst_dir": "knowledge",
    "description": "65816 instruction set and label data",
}


def make_shim(module_path: str, description: str) -> str:
    """Generate a compatibility shim that forwards to afs_scawful."""
    return textwrap.dedent(f'''\
        """Compatibility shim for legacy module now owned by afs-scawful.

        {description}
        """

        from __future__ import annotations

        try:
            from {module_path} import *  # type: ignore[F403]
        except Exception as exc:  # pragma: no cover - compatibility path
            raise RuntimeError(
                "Module '{module_path}' moved to the afs-scawful extension. "
                "Install afs-scawful or add it to PYTHONPATH."
            ) from exc
    ''')


def make_init_shim(module_path: str, description: str) -> str:
    """Generate a package __init__ shim."""
    return make_shim(module_path, description)


def collect_py_files(package_dir: Path) -> list[Path]:
    """Collect all .py files in a package (non-recursive for now)."""
    files = []
    for item in sorted(package_dir.iterdir()):
        if item.suffix == ".py" and not item.name.startswith("__pycache__"):
            files.append(item)
    # Include subdirectories with __init__.py
    for item in sorted(package_dir.iterdir()):
        if item.is_dir() and (item / "__init__.py").exists():
            files.extend(collect_py_files(item))
    return files


def port_full_package(
    name: str, config: dict, *, execute: bool = False, shim_only: bool = False
) -> list[str]:
    """Port an entire package to afs-scawful."""
    actions = []
    core_dir = CORE_SRC / name
    target = config["target"]
    scawful_dir = SCAWFUL_SRC / target

    if not core_dir.exists():
        actions.append(f"SKIP {name}: core directory not found at {core_dir}")
        return actions

    py_files = collect_py_files(core_dir)

    # Step 1: Copy to afs-scawful
    if not shim_only:
        if not scawful_dir.exists():
            actions.append(f"CREATE {scawful_dir}")
            if execute:
                scawful_dir.mkdir(parents=True, exist_ok=True)

        for py_file in py_files:
            rel = py_file.relative_to(core_dir)
            dst = scawful_dir / rel
            if dst.exists():
                actions.append(f"SKIP copy {rel} (already exists in afs-scawful)")
            else:
                actions.append(f"COPY {core_dir / rel} -> {dst}")
                if execute:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(py_file, dst)

    # Step 2: Replace core files with shims
    for py_file in py_files:
        rel = py_file.relative_to(core_dir)
        module_stem = str(rel).replace("/", ".").removesuffix(".py")
        if module_stem.endswith(".__init__"):
            module_stem = module_stem.removesuffix(".__init__")
        scawful_module = f"afs_scawful.{target}.{module_stem}" if module_stem != "__init__" else f"afs_scawful.{target}"
        # Fix: if it's the package __init__, the module path is just the package
        if py_file.name == "__init__.py" and py_file.parent == core_dir:
            scawful_module = f"afs_scawful.{target}"

        shim = make_shim(scawful_module, config["description"])
        actions.append(f"SHIM {py_file.relative_to(CORE_SRC.parent.parent)}")
        if execute:
            py_file.write_text(shim)

    return actions


def port_partial_package(
    name: str, config: dict, *, execute: bool = False, shim_only: bool = False
) -> list[str]:
    """Port specific files from a package, keeping generic code in core."""
    actions = []
    core_dir = CORE_SRC / name
    target = config["target"]
    scawful_dir = SCAWFUL_SRC / target

    if not core_dir.exists():
        actions.append(f"SKIP {name}: core directory not found at {core_dir}")
        return actions

    move_files = config["move_files"]

    # Step 1: Copy files to afs-scawful
    if not shim_only:
        if not scawful_dir.exists():
            actions.append(f"CREATE {scawful_dir}")
            if execute:
                scawful_dir.mkdir(parents=True, exist_ok=True)

        for filename in move_files:
            src = core_dir / filename
            dst = scawful_dir / filename
            if not src.exists():
                actions.append(f"SKIP copy {filename} (not found in core)")
                continue
            if dst.exists():
                actions.append(f"SKIP copy {filename} (already exists in afs-scawful)")
            else:
                actions.append(f"COPY {src.relative_to(CORE_SRC.parent.parent)} -> {dst}")
                if execute:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)

    # Step 2: Replace moved files with shims
    for filename in move_files:
        src = core_dir / filename
        if not src.exists():
            continue
        module_stem = filename.removesuffix(".py")
        scawful_module = f"afs_scawful.{target}.{module_stem}"
        shim = make_shim(scawful_module, config["description"])
        actions.append(f"SHIM {src.relative_to(CORE_SRC.parent.parent)}")
        if execute:
            src.write_text(shim)

    # Step 3: Update __init__.py to handle missing modules gracefully
    init_file = core_dir / "__init__.py"
    if init_file.exists():
        actions.append(f"NOTE: {init_file.relative_to(CORE_SRC.parent.parent)} may need manual update")
        actions.append(f"      to wrap imports of moved modules in try/except blocks")

    return actions


def port_standalone_files(
    *, execute: bool = False, shim_only: bool = False
) -> list[str]:
    """Move standalone domain-specific files to afs-scawful."""
    actions = []
    if shim_only:
        return actions

    for name, config in STANDALONE_MOVES.items():
        src = config["src"]
        dst_dir = SCAWFUL_SRC.parent.parent / config["dst_dir"]
        dst = dst_dir / name

        if not src.exists():
            actions.append(f"SKIP {name}: not found at {src}")
            continue

        actions.append(f"MOVE {src} -> {dst} ({config['description']})")
        if execute:
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    return actions


def port_domain_cli(
    *, execute: bool = False, shim_only: bool = False
) -> list[str]:
    """Move domain-specific CLI modules to afs-scawful."""
    actions = []
    if shim_only:
        return actions

    cli_dir = CORE_SRC / "cli"
    scawful_cli = SCAWFUL_SRC / "cli"

    for filename in DOMAIN_CLI_FILES:
        src = cli_dir / filename
        if not src.exists():
            continue
        dst = scawful_cli / filename
        if dst.exists():
            actions.append(f"SKIP CLI {filename} (already exists in afs-scawful)")
        else:
            actions.append(f"COPY CLI {filename} -> {dst}")
            if execute:
                scawful_cli.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

    return actions


def port_domain_tests(
    *, execute: bool = False, shim_only: bool = False
) -> list[str]:
    """Move domain-specific test files to afs-scawful."""
    actions = []
    if shim_only:
        return actions

    test_dir = Path(__file__).resolve().parent.parent / "tests"
    scawful_tests = SCAWFUL_SRC.parent.parent / "tests"

    for filename in DOMAIN_TEST_FILES:
        src = test_dir / filename
        if not src.exists():
            continue
        dst = scawful_tests / filename
        if dst.exists():
            actions.append(f"SKIP test {filename} (already exists in afs-scawful)")
        else:
            actions.append(f"COPY test {filename} -> {dst}")
            if execute:
                scawful_tests.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

    return actions


def port_knowledge(
    *, execute: bool = False, shim_only: bool = False
) -> list[str]:
    """Move knowledge/ directory to afs-scawful."""
    actions = []
    if shim_only:
        return actions

    src_dir = KNOWLEDGE_MOVES["src"]
    if not src_dir.exists():
        actions.append(f"SKIP knowledge: not found at {src_dir}")
        return actions

    dst_dir = SCAWFUL_SRC.parent.parent / KNOWLEDGE_MOVES["dst_dir"]
    actions.append(f"COPY knowledge/ -> {dst_dir} ({KNOWLEDGE_MOVES['description']})")
    if execute:
        if dst_dir.exists():
            actions.append(f"  (merging into existing {dst_dir})")
        shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)

    return actions


def main():
    parser = argparse.ArgumentParser(
        description="Port domain-specific modules from core AFS to afs-scawful",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform the migration (default: dry run)",
    )
    parser.add_argument(
        "--shim-only",
        action="store_true",
        help="Only create shims in core (skip copying to afs-scawful)",
    )
    parser.add_argument(
        "--domains",
        nargs="*",
        choices=list(FULL_PACKAGES) + list(PARTIAL_PACKAGES) + ["cli", "tests", "standalone", "knowledge"],
        help="Only port specific domains (default: all)",
    )
    args = parser.parse_args()

    domains = set(args.domains) if args.domains else None
    all_actions: list[str] = []

    print("=" * 60)
    print("AFS Domain Module Porting Script")
    print(f"Mode: {'EXECUTE' if args.execute else 'DRY RUN'}")
    print(f"Core: {CORE_SRC}")
    print(f"Target: {SCAWFUL_SRC}")
    print("=" * 60)

    if not SCAWFUL_SRC.parent.exists():
        print(f"\nERROR: afs-scawful not found at {SCAWFUL_SRC.parent.parent}")
        print("Clone it first, then re-run this script.")
        return 1

    # Full packages
    for name, config in FULL_PACKAGES.items():
        if domains and name not in domains:
            continue
        print(f"\n--- {name} ({config['description']}) ---")
        actions = port_full_package(
            name, config, execute=args.execute, shim_only=args.shim_only
        )
        for a in actions:
            print(f"  {a}")
        all_actions.extend(actions)

    # Partial packages
    for name, config in PARTIAL_PACKAGES.items():
        if domains and name not in domains:
            continue
        print(f"\n--- {name} (partial: {config['description']}) ---")
        actions = port_partial_package(
            name, config, execute=args.execute, shim_only=args.shim_only
        )
        for a in actions:
            print(f"  {a}")
        all_actions.extend(actions)

    # Standalone files
    if not domains or "standalone" in domains:
        print("\n--- Standalone domain files ---")
        actions = port_standalone_files(execute=args.execute, shim_only=args.shim_only)
        for a in actions:
            print(f"  {a}")
        all_actions.extend(actions)

    # Domain CLI
    if not domains or "cli" in domains:
        print("\n--- Domain CLI modules ---")
        actions = port_domain_cli(execute=args.execute, shim_only=args.shim_only)
        for a in actions:
            print(f"  {a}")
        all_actions.extend(actions)

    # Domain tests
    if not domains or "tests" in domains:
        print("\n--- Domain test files ---")
        actions = port_domain_tests(execute=args.execute, shim_only=args.shim_only)
        for a in actions:
            print(f"  {a}")
        all_actions.extend(actions)

    # Knowledge
    if not domains or "knowledge" in domains:
        print("\n--- Knowledge data ---")
        actions = port_knowledge(execute=args.execute, shim_only=args.shim_only)
        for a in actions:
            print(f"  {a}")
        all_actions.extend(actions)

    # Summary
    print("\n" + "=" * 60)
    copies = sum(1 for a in all_actions if a.startswith("COPY"))
    shims = sum(1 for a in all_actions if a.startswith("SHIM"))
    skips = sum(1 for a in all_actions if a.startswith("SKIP"))
    moves = sum(1 for a in all_actions if a.startswith("MOVE"))
    print(f"Summary: {copies} copies, {shims} shims, {moves} moves, {skips} skipped")

    if not args.execute:
        print("\nThis was a DRY RUN. Re-run with --execute to apply changes.")
        print("Run scripts/validate_core.py afterward to verify integrity.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
