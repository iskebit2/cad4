# app/settings/app_paths.py
from __future__ import annotations

import os
import sys
from pathlib import Path


def _user_root() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        return (Path(base) / "cad4") if base else (Path.home() / ".cad4")
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "cad4"
    return Path.home() / ".cad4"


def config_dir() -> Path:
    d = _user_root()
    d.mkdir(parents=True, exist_ok=True)
    return d


def toolbar_layout_file() -> Path:
    return config_dir() / "toolbar.json"


def shortcuts_file() -> Path:
    return config_dir() / "shortcuts.json"