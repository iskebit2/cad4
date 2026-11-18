# app/services/panel_registry.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PanelEntry:
    instance: Any
    name: str
    title: str
    category: str
    quick: bool = False
    shortcut: str = ""
    menu_label: str = ""
    icon: str = ""
    context: list[str] = field(default_factory=list)


class PanelRegistry:
    """Panel keşfi ve saklama. UIHost buradan okur; CadApp state tutmaz."""

    def __init__(self) -> None:
        self._by_name: dict[str, PanelEntry] = {}
        self._by_category: dict[str, list[str]] = {}

    def register(self, entry: PanelEntry) -> None:
        self._by_name[entry.name] = entry
        self._by_category.setdefault(entry.category, []).append(entry.name)

    def get(self, name: str) -> PanelEntry | None:
        return self._by_name.get(name)

    def instance(self, name: str) -> Any | None:
        entry = self._by_name.get(name)
        return entry.instance if entry else None

    def all(self) -> list[PanelEntry]:
        return list(self._by_name.values())

    def visible(self) -> list[PanelEntry]:
        return [e for e in self._by_name.values()
                if getattr(e.instance, "visible", False)]

    def categories(self) -> dict[str, list[str]]:
        return {k: list(v) for k, v in self._by_category.items()}