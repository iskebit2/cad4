"""Widget sözleşmesi ve ortak yardımcılar."""

from dataclasses import dataclass, field
from typing import Any, Dict

import imgui

from inspector.schema_bridge import MIXED


# ----------------------------------------------------------------------
@dataclass
class DrawContext:
    """Widget'lara geçen edit buffer ve durum."""
    values: Dict[str, Any]
    mixed_buffer: Dict[str, str] = field(default_factory=dict)
    changed: bool = False
    catalog: Any = None

    def touch(self):
        self.changed = True

    def is_mixed(self, key: str) -> bool:
        return _get_path(self.values, key) == MIXED

    def get(self, key, default=None):
        v = _get_path(self.values, key, default)
        return default if v is None else v

    def set(self, key, value):
        _set_path(self.values, key, value)
        self.changed = True


# ----------------------------------------------------------------------
class Widget:
    """Soyut taban."""

    #: field.kind değeri -> Widget sınıfı eşlemesi için
    kind: str = ""

    def draw(self, field, ctx: DrawContext) -> bool:
        raise NotImplementedError

    # --- ortak yardımcılar ---
    @staticmethod
    def label_row(label: str, offset: float = 140.0):
        imgui.align_text_to_frame_padding()
        imgui.text(label)
        imgui.same_line(position=offset)

    @staticmethod
    def mixed_marker(text: str = "(karışık)"):
        imgui.same_line()
        imgui.text_colored(text, 0.95, 0.85, 0.45, 1.0)


# ----------------------------------------------------------------------
# Path erişimi — "a.b.0.c" gibi
def _get_path(d, path: str, default=None):
    cur = d
    for part in path.split("."):
        if isinstance(cur, dict):
            if part not in cur:
                return default
            cur = cur[part]
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return default
        else:
            return default
    return cur


def _set_path(d, path: str, value):
    parts = path.split(".")
    cur = d
    for p in parts[:-1]:
        if isinstance(cur, dict):
            cur = cur.setdefault(p, {})
        elif isinstance(cur, list):
            cur = cur[int(p)]
    last = parts[-1]
    if isinstance(cur, dict):
        cur[last] = value
    elif isinstance(cur, list):
        cur[int(last)] = value