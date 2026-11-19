# app/services/panel_registry.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from inspector.window import InspectorWindow
from ui.panels.command_panel import CommandPanel
from ui.panels.grid_panel import GridPanel
from ui.panels.line_properties_panel import LinePropertiesPanel
from plane.plane_manager_panel import PlaneManagerPanel
from ui.panels.polygon_properties_panel import PolygonPropertiesPanel
from ui.panels.s2k_panel import S2KPanel
from ui.panels.wind_analysis_panel import WindAnalysisPanel

if TYPE_CHECKING:
    from app.cad_app import CadApp


@dataclass
class PanelSpec:
    cls: type
    name: str
    title: str
    category: str
    quick: bool = False
    shortcut: str = ""
    menu_label: str = ""
    icon: str = ""
    context: list[str] = field(default_factory=list)


# ==============================================================================
# ELLE KONTROL EDİLEN PANEL LİSTESİ (Sıra = Menü ve Quick-Bar Sırası)
# ==============================================================================
PANELS: dict[int, PanelSpec] = {
    1: PanelSpec(
        cls=CommandPanel,
        name="command_panel",
        title="Komut Satırı",
        category="Management",
        quick=True,
        shortcut="F1",
        menu_label="Komut Satırı",
        icon="⌨",
    ),
    2: PanelSpec(
        cls=GridPanel,
        name="grid",
        title="Grid Ayarları",
        category="View",
        quick=True,
        menu_label="Grid",
        icon="grid",                 # değişti
        context=["project", "scene"],
    ),
    3: PanelSpec(
        cls=PlaneManagerPanel,
        name="plane_manager",
        title="Çalışma Düzlemleri",
        category="View",
        quick=True,
        menu_label="Düzlemler",
        icon="plane-draw",           # eklendi
        context=["project", "engine"],
    ),
    4: PanelSpec(
        cls=LinePropertiesPanel,
        name="line_properties",
        title="Çubuk Özellikleri",
        category="Draw",
        menu_label="Çubuk Özellikleri",
        context=["project", "selection_frames"],
    ),
    5: PanelSpec(
        cls=PolygonPropertiesPanel,
        name="polygon_properties",
        title="Alan / Poligon Özellikleri",
        category="Draw",
        menu_label="Poligon Özellikleri",
        context=["project", "selection_polygons"],
    ),
    6: PanelSpec(
        cls=WindAnalysisPanel,
        name="wind",
        title="Rüzgar Analizi",
        category="Loads",
        quick=True,
        menu_label="Rüzgar Analizi",
        icon="wind",                 # eklendi
        context=["project", "wind_analysis_ref"],
    ),
    7: PanelSpec(
        cls=S2KPanel,
        name="s2k_panel",
        title="SAP2000 (.s2k)",
        category="File",
        menu_label="SAP2000 Import/Export",
        icon="s2k",                  # eklendi
        context=["project"],
    ),
    8: PanelSpec(
        cls=InspectorWindow,
        name="inspector_panel",
        title="Inspector",
        category="Management",
        quick=True,
        shortcut="F10",
        menu_label="Inspector",
        icon="log-in",
        context=["project", "scene", "app"],
    ),
}


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
    """PANELS sözlüğündeki tanımları örnekler ve UI/Command katmanlarına sunar."""

    def __init__(self, app: "CadApp | None" = None) -> None:
        self._by_name: dict[str, PanelEntry] = {}
        self._by_category: dict[str, list[str]] = {}
        if app is not None:
            self.load_from_specs(app, PANELS)

    def load_from_specs(self, app: "CadApp", specs: dict[int, PanelSpec]) -> None:
        for idx in sorted(specs.keys()):
            spec = specs[idx]
            instance = spec.cls(app=app)
            self.register(PanelEntry(
                instance=instance,
                name=spec.name,
                title=spec.title,
                category=str(spec.category),
                quick=spec.quick,
                shortcut=spec.shortcut,
                menu_label=spec.menu_label or spec.title,
                icon=spec.icon,
                context=list(spec.context),
            ))

    def register(self, entry: PanelEntry) -> None:
        if not entry.menu_label:
            entry.menu_label = entry.title
        previous = self._by_name.get(entry.name)
        if previous is not None:
            previous_names = self._by_category.get(previous.category, [])
            if entry.name in previous_names:
                previous_names.remove(entry.name)
        self._by_name[entry.name] = entry
        cat_list = self._by_category.setdefault(entry.category, [])
        if entry.name not in cat_list:
            cat_list.append(entry.name)

    def get(self, name: str) -> PanelEntry | None:
        return self._by_name.get(name)

    def instance(self, name: str) -> Any | None:
        entry = self._by_name.get(name)
        return entry.instance if entry else None

    def all(self) -> list[PanelEntry]:
        return list(self._by_name.values())

    def visible(self) -> list[PanelEntry]:
        return [
            e for e in self._by_name.values()
            if getattr(e.instance, "visible", False)
        ]

    def is_visible(self, name: str) -> bool:
        inst = self.instance(name)
        return bool(getattr(inst, "visible", False)) if inst is not None else False

    def categories(self) -> dict[str, list[str]]:
        return {k: list(v) for k, v in self._by_category.items()}

    # --- Toolbar Bağlantı Köprüleri ---

    def toolbar_specs(self) -> list[PanelEntry]:
        return list(self._by_name.values())

    def toolbar_commands(self, put_command: Callable[[Any], None]) -> dict[str, Callable[[], None]]:
        from app.commands import project_commands as PC
        return {
            name: (lambda n=name: put_command(PC.TogglePanel(n)))
            for name in self._by_name
        }

    def toolbar_states(self) -> dict[str, Callable[[], bool]]:
        return {
            name: (lambda n=name: self.is_visible(n))
            for name in self._by_name
        }

    # def load_from_specs(self, app, specs):
    #     for idx in sorted(specs.keys()):
    #         spec = specs[idx]
    #         try:
    #             instance = spec.cls(app=app)
    #         except TypeError:
    #             # app parametresini kabul etmeyen paneller için
    #             instance = spec.cls()
    #             instance.set_context({"app": app})
            # self.register(PanelEntry(...))