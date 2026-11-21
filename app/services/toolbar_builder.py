from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.commands.registry import CommandRegistry
from app.services.panel_registry import PanelRegistry
from app.settings.categories import FALLBACK_CATEGORY
from app.settings.layout_store import LayoutStore, ToolbarLayout
from app.settings.shortcut_store import ShortcutStore


@dataclass
class UnifiedSpec:
    key: str
    label: str
    icon: str
    shortcut: str
    category: str
    quick: bool
    tooltip: str
    is_panel: bool
    panel_name: str | None = None
    cmd: Any = None
    check_state: Callable[[Any], bool] | None = None


class ToolbarBuilder:
    def __init__(
        self,
        cmd_registry: CommandRegistry,
        panel_registry: PanelRegistry,
        layout_store: LayoutStore,
        shortcut_store: ShortcutStore,
    ) -> None:
        self.cmd_registry = cmd_registry
        self.panel_registry = panel_registry
        self.layout_store = layout_store
        self.shortcut_store = shortcut_store

    def build(self) -> list[UnifiedSpec]:
        layout = self.layout_store.load()
        specs = self._command_specs(layout) + self._panel_specs(layout)
        return self._sort(specs, layout)

    def _command_specs(self, layout: ToolbarLayout) -> list[UnifiedSpec]:
        out: list[UnifiedSpec] = []
        for cmd_id, _cmd_type, meta in self.cmd_registry.all_meta():
            if not meta.visible_in_ui or cmd_id in layout.hidden:
                continue
            instance = self.cmd_registry.build_instance(cmd_id)
            out.append(UnifiedSpec(
                key=cmd_id,
                label=meta.label,
                icon=meta.icon,
                shortcut=self.shortcut_store.resolve(cmd_id, meta.default_shortcut),
                category=meta.category or FALLBACK_CATEGORY,
                quick=layout.quick_override.get(cmd_id, meta.quick),
                tooltip=meta.tooltip or meta.label,
                is_panel=False,
                cmd=instance,
                check_state=meta.check_state,
            ))
        return out

    def _panel_specs(self, layout: ToolbarLayout) -> list[UnifiedSpec]:
        out: list[UnifiedSpec] = []
        for entry in self.panel_registry.all():
            if entry.name in layout.hidden:
                continue
            out.append(UnifiedSpec(
                key=entry.name,
                label=entry.menu_label or entry.title,
                icon=entry.icon or "",
                shortcut=self.shortcut_store.resolve(entry.name, entry.shortcut or ""),
                category=str(entry.category) or FALLBACK_CATEGORY,
                quick=layout.quick_override.get(entry.name, entry.quick),
                tooltip=entry.title,
                is_panel=True,
                panel_name=entry.name,
            ))
        return out

    def _sort(self, specs: list[UnifiedSpec], layout: ToolbarLayout) -> list[UnifiedSpec]:
        order_index = {c: i for i, c in enumerate(layout.category_order)}
        by_category: dict[str, list[UnifiedSpec]] = {}
        for s in specs:
            cat = s.category.value if hasattr(s.category, "value") else str(s.category)
            by_category.setdefault(cat, []).append(s)

        ordered: list[UnifiedSpec] = []
        for category in layout.category_order:
            items = by_category.pop(category, [])
            if not items:
                continue
            item_order = layout.item_order.get(category, [])
            idx = {k: i for i, k in enumerate(item_order)}
            items.sort(key=lambda s: (
                idx.get(s.key, 100_000),
                0 if s.quick else 1,
                s.label.casefold(),
            ))
            ordered.extend(items)

        leftover = [
            (order_index.get(cat, len(layout.category_order)), cat, items)
            for cat, items in by_category.items()
        ]
        leftover.sort(key=lambda t: (t[0], t[1]))
        for _, _cat, items in leftover:
            items.sort(key=lambda s: (0 if s.quick else 1, s.label.casefold()))
            ordered.extend(items)
        return ordered