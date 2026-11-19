# app/services/toolbar_builder.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.services.panel_registry import PanelRegistry, PanelEntry
from app.services.toolbar_specs import CommandSpec, default_commands


@dataclass
class UnifiedSpec:
    """Toolbar'ın tek gördüğü spec türü — panel veya komut."""
    key: str
    label: str
    icon: str
    shortcut: str
    category: str
    quick: bool
    tooltip: str
    is_panel: bool = False

    # Panel ise:
    panel_name: str | None = None

    # Komut ise:
    cmd: Any = None
    check_state: Callable[[Any], bool] | None = None


CATEGORY_ORDER = [
    "File", "Edit", "View", "Draw", "Convert",
    "Management", "Loads",
]


def build_unified_specs(
    panel_registry: PanelRegistry,
    extra_commands: list[CommandSpec] | None = None,
) -> list[UnifiedSpec]:
    """PANELS + varsayılan komut kataloğu → tek sıralı list."""
    out: list[UnifiedSpec] = []

    # 1) Komutlar (dosya, düzen, görünüm, çizim)
    for c in (extra_commands if extra_commands is not None else default_commands()):
        out.append(UnifiedSpec(
            key=c.name,
            label=c.label,
            icon=c.icon,
            shortcut=c.shortcut,
            category=c.category,
            quick=c.quick,
            tooltip=c.tooltip or c.label,
            is_panel=False,
            cmd=c.cmd,
            check_state=c.check_state,
        ))

    # 2) Paneller
    for entry in panel_registry.all():
        out.append(UnifiedSpec(
            key=entry.name,
            label=entry.menu_label or entry.title,
            icon=entry.icon,
            shortcut=entry.shortcut,
            category=entry.category,
            quick=entry.quick,
            tooltip=entry.title,
            is_panel=True,
            panel_name=entry.name,
        ))

    # Sıralama: kategoriye göre, sonra quick önce
    def _sort_key(s: UnifiedSpec):
        try:
            ci = CATEGORY_ORDER.index(s.category)
        except ValueError:
            ci = len(CATEGORY_ORDER)
        return (ci, 0 if s.quick else 1, s.label.lower())

    out.sort(key=_sort_key)
    return out


def group_by_category(specs: list[UnifiedSpec]) -> dict[str, list[UnifiedSpec]]:
    buckets: dict[str, list[UnifiedSpec]] = {}
    for s in specs:
        buckets.setdefault(s.category, []).append(s)
    return buckets