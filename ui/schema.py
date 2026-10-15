# ui/schema.py
"""Şema tanımları — ImGui'den bağımsız, sadece veri."""
from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class FieldSpec:
    key: str
    kind: str = "str"                     # bool|enum|float|int|color|str|list_object
    label: Optional[str] = None
    choices: Optional[List[str]] = None
    editable: bool = True
    step: float = 0.1
    format: str = "%.3f"
    item_schema: Optional[List[Any]] = None


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
    for i, p in enumerate(parts[:-1]):
        next_p = parts[i + 1]
        is_next_int = next_p.isdigit()
        
        if isinstance(cur, dict):
            if p not in cur or cur[p] is None:
                cur[p] = [] if is_next_int else {}
            cur = cur[p]
        elif isinstance(cur, list):
            idx = int(p)
            while len(cur) <= idx:
                cur.append([] if is_next_int else {})
            cur = cur[idx]
            
    last_p = parts[-1]
    if isinstance(cur, list):
        cur[int(last_p)] = value
    elif isinstance(cur, dict):
        cur[last_p] = value