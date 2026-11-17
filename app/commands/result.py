# app/commands/result.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CommandResult:
    geometry_dirty: bool = False
    project_dirty: bool = False
    handled: bool = True
    message: str = ""
    level: str = "info"           # "info" | "success" | "warn" | "error"
    followup: Any = None          # zincirleme komut (opsiyonel)