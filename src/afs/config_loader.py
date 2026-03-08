"""Compatibility helpers for loading TOML and chat registries."""

import sys
from pathlib import Path
from typing import Any

from .chat_registry import load_chat_registry

try:
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib
except ImportError:
    # Fallback for environments without tomli/tomllib
    # We will use a simple parser for our specific use case or fail gracefully
    tomllib = None

def load_toml(path: Path) -> dict[str, Any]:
    """Load TOML file with fallback."""
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "rb") as f:
        if tomllib:
            return tomllib.load(f)
        else:
            # Very basic fallback or error
            raise ImportError("Python 3.11+ or 'tomli' package required to parse TOML configuration.")

def get_chat_registry(root_path: Path | None = None) -> dict[str, Any]:
    """Load chat registry data from explicit paths or active profile registries."""
    if root_path is not None:
        return load_chat_registry(registry_paths=[root_path]).to_dict()
    return load_chat_registry().to_dict()
