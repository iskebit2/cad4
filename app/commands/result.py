# app/commands/result.py
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class CommandResult:
    """Komut uygulama sonucu."""
    geometry_dirty: bool = False   # engine.update_geo gerekiyor mu
    project_dirty: bool = False    # UI panelleri yenilensin mi
    handled: bool = True           # bilinmiyorsa False