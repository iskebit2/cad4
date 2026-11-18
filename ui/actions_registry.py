# ui/actions_registry.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, TYPE_CHECKING

from ui.base.panel_base import Category

if TYPE_CHECKING:
    from app.cad_app import CadApp
    from ui.ui_host import UIHost


@dataclass(frozen=True)
class ActionSpec:
    name: str
    title: str
    category: Category
    menu_label: str
    icon: str | None = None
    quick: bool = False
    shortcut: str | None = None
    scope: str = "host"         # "host" | "panel" | "custom"  ("app" kaldırıldı)
    method: str | None = None
    args: tuple = ()
    state: str | None = None    # panel_states anahtarı (None → name)


ACTION_SPECS: list[ActionSpec] = [
    # --- File ---
    ActionSpec("new_project", "New Project", Category.FILE, "New",
               icon="file-plus", shortcut="CTRL+N", method="new_project"),
    ActionSpec("open", "Open Project", Category.FILE, "Open...",
               icon="folder", shortcut="CTRL+O", method="open_open_dialog"),
    ActionSpec("save", "Save Project", Category.FILE, "Save",
               icon="save", quick=True, shortcut="CTRL+S", method="quick_save"),
    ActionSpec("save_as", "Save As", Category.FILE, "Save As...",
               icon="save", shortcut="SHIFT+CTRL+S", method="open_save_dialog"),
    ActionSpec("close_app", "Exit", Category.FILE, "Exit",
               icon="x", method="close_app"),

    # --- Draw ---
    ActionSpec("draw_line", "Draw Line", Category.DRAW, "Line",
               icon="edit", method="toggle_draw", args=("line",)),
    ActionSpec("draw_poly", "Draw Polygon", Category.DRAW, "Polygon (D)",
               icon="edit", shortcut="D", method="toggle_draw", args=("poly",)),
    ActionSpec("draw_plane", "Draw Plane", Category.DRAW, "Plane (Shift+W)",
               icon="grid", shortcut="SHIFT+W", method="toggle_plane"),
    ActionSpec("plane_3pt", "Plane (3pt)", Category.DRAW, "Plane 3pt",
               icon="grid", method="start_plane_3pt"),
    ActionSpec("plane_2pt_z", "Plane (2pt Z)", Category.DRAW, "Plane 2pt Z",
               icon="grid", method="start_plane_2pt_z"),
    ActionSpec("plane_from_element", "Plane (Element)", Category.DRAW, "Plane from Element",
               icon="grid", method="open_plane_source_dialog"),

    # --- View: ortografik/izo viewport'lar ---
    *[
        ActionSpec(f"vp_{preset}", preset.title(), Category.VIEW, preset.title(),
                   icon="x", method="open_viewport", args=(preset,),
                   state=f"vp_{preset}_open")
        for preset in ("iso", "top", "bottom", "front", "back", "left", "right",
                       "iso_sw", "iso_se", "iso_ne", "iso_nw")
    ],
    ActionSpec("vp_close_all", "Close All", Category.VIEW, "Close All",
               icon="x", method="close_all_viewports"),
    ActionSpec("open_inspector", "Inspector", Category.VIEW, "Inspector",
               icon="edit", method="open_inspector"),

    # --- View: görünürlük / render ---
    ActionSpec("toggle_view_2d", "2D Toggle", Category.VIEW, "2D Plane",
               method="toggle_view_2d"),
    ActionSpec("render_mode", "Render Mode", Category.VIEW, "Toggle Render Mode",
               method="toggle_render_mode"),
    ActionSpec("local_axes", "Local Axes", Category.VIEW, "Local Axes",
               method="toggle_local_axes"),
    ActionSpec("toggle_loads_vis", "Toggle Loads", Category.VIEW, "Show Loads",
               method="toggle_loads"),

    # --- Edit ---
    ActionSpec("convert_to_link", "Convert to Link", Category.EDIT, "Convert Frames → Links",
               method="convert_frames_to_link", args=("DefaultLink",)),

    # --- Import / Export ---
    ActionSpec("s2k_import", "S2K Import", Category.FILE, "S2K Import...",
               method="open_s2k_import"),
    ActionSpec("s2k_export", "S2K Export", Category.FILE, "S2K Export...",
               method="open_s2k_export"),
]


def build_commands(host: "UIHost") -> dict[str, Callable]:
    """ActionSpec listesinden runtime dispatch tablosu üret."""
    app: CadApp = host.app
    cmds: dict[str, Callable] = {}

    for spec in ACTION_SPECS:
        if spec.scope == "host":
            target: Any = host
        elif spec.scope == "panel":
            target = host.get_panel(spec.method or spec.name)
            if target is None:
                continue
        else:
            continue

        method_name = spec.method or spec.name
        fn = getattr(target, method_name, None)
        if not callable(fn):
            continue

        if spec.args:
            cmds[spec.name] = (lambda f=fn, a=spec.args: f(*a))
        else:
            cmds[spec.name] = fn

    # Panel toggle komutları — PanelRegistry üzerinden
    for entry in app.panel_registry.all():
        cmds[entry.name] = (lambda n=entry.name: host.toggle_panel(n))

    return cmds


def build_panel_states(host: "UIHost") -> dict[str, Callable[[], bool]]:
    """Panel görünürlük ve aksiyon aktiflik durumları."""
    app: CadApp = host.app
    eng = getattr(app, "engine", None)
    mgr = getattr(eng, "draw_mgr", None) if eng else None
    vs = app.view_service

    def _draw_mode_is(mode_name: str) -> bool:
        return bool(mgr and mgr.is_active and getattr(mgr, "mode", None) == mode_name)

    def _active_view_is_2d() -> bool:
        viewport_manager = app.viewport_manager
        viewport = viewport_manager.active if viewport_manager is not None else None
        if viewport is not None:
            return bool(viewport.is_2d)
        return bool(eng and eng.plane_mode and eng.plane_mode.is_2d)

    states: dict[str, Callable[[], bool]] = {
        "draw_line": lambda: _draw_mode_is("line"),
        "draw_poly": lambda: _draw_mode_is("sequential"),
        "draw_plane": lambda: bool(eng and eng.plane_draw_mgr and eng.plane_draw_mgr.is_active),
        "local_axes": lambda: bool(eng and eng.scene and eng.scene.show_local_axes),
        "toggle_loads_vis": vs.get_loads_visible,                       # ✅ servis
        "toggle_view_2d": _active_view_is_2d,
    }

    for preset in ("iso", "top", "bottom", "front", "back", "left", "right",
                   "iso_sw", "iso_se", "iso_ne", "iso_nw"):
        states[f"vp_{preset}_open"] = (
            lambda p=preset: bool(
                app.viewport_manager and app.viewport_manager.get(p)
            )
        )

    # Panel durumları — PanelRegistry üzerinden
    for entry in app.panel_registry.all():
        inst = entry.instance
        states[entry.name] = (lambda i=inst: getattr(i, "visible", False))

    return states