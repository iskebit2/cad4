# ui/schema.py
"""Şema tanımları — ImGui'den bağımsız, sadece veri."""
from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class FieldSpec:
    key: str
    kind: str = "str"                     # bool|enum|float|int|color|str
    label: Optional[str] = None
    choices: Optional[List[str]] = None
    editable: bool = True
    step: float = 0.1
    format: str = "%.3f"


@dataclass
class GroupSpec:
    title: str
    fields: List[FieldSpec] = field(default_factory=list)
    default_open: bool = True


def get_path(d: dict, path: str):
    cur = d
    for p in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(p)
        elif isinstance(cur, (list, tuple)) and p.isdigit():
            cur = cur[int(p)]
        else:
            return None
    return cur


def set_path(d: dict, path: str, value):
    parts = path.split(".")
    cur = d
    for p in parts[:-1]:
        if p not in cur or cur[p] is None:
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value