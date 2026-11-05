# inspector/fields.py
from __future__ import annotations

from typing import Any


_SKIP = frozenset({
    "element_type", "unique_id", "pick_id", "needs_update",
    "show_axes_override", "connected", "dof_indices", "loads",
    "is_selected", "source_node_id",
    "node_i", "node_j", "nodes", "dist_loads",
})


def inspector_fields(obj) -> list[tuple[str, Any]]:
    if obj is None:
        return []
    out = []
    for name in dir(obj):
        if name.startswith("_") or name in _SKIP:
            continue
        try:
            value = getattr(obj, name)
        except AttributeError:
            continue
        if callable(value):
            continue
        out.append((name, value))
    return out


class _Mixed:
    def __repr__(self):
        return "<MIXED>"


_MIXED = _Mixed()


def common_value(objects: list, key: str):
    if not objects:
        return _MIXED
    try:
        first = getattr(objects[0], key, _MIXED)
    except AttributeError:
        return _MIXED
    for o in objects[1:]:
        try:
            if getattr(o, key, _MIXED) != first:
                return _MIXED
        except AttributeError:
            return _MIXED
    return first


def set_value_all(objects: list, key: str, value):
    for o in objects:
        try:
            setattr(o, key, value)
        except AttributeError:
            pass


def is_mixed(v) -> bool:
    return v is _MIXED