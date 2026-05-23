"""Pytest configuration and module loaders without Home Assistant."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "ip_attack_map"


def load_module(name: str, relative: str | None = None):
    """Load an integration module file without importing __init__.py."""
    path = INTEGRATION / (relative or f"{name}.py")
    module_name = f"ip_attack_map_{name.replace('/', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
