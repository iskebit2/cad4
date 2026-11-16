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
    scope: str = "app"          # "app" | "host" | "panel" | "custom"
    method: str | None = None   # scope'a göre hedef metod adı
    args: tuple = ()
    state: str | None = None    # panel_states anahtarı (None → name)


ACTION_SPECS: list[ActionSpec] = [
    # --- File ---
    ActionSpec("new_project", "New Project", Category.FILE, "New",
               icon="file-plus", shortcut="CTRL+N", method="new_project"),
    ActionSpec("open", "Open Project", Category.FILE, "Open...",
               icon="folder", shortcut="CTRL+O", scope="host", method="open_open_dialog"),
    ActionSpec("save", "Save Project", Category.FILE, "Save",
               icon="save", quick=True, shortcut="CTRL+S", method="quick_save"),
    ActionSpec("save_as", "Save As", Category.FILE, "Save As...",
               icon="save", shortcut="SHIFT+CTRL+S", scope="host", method="open_save_dialog"),
    ActionSpec("close_app", "Exit", Category.FILE, "Exit",
               icon="x", scope="host", method="close_app"),

    # --- Draw ---
    ActionSpec("draw_line", "Draw Line", Category.DRAW, "Line",
               icon="edit", scope="host", method="toggle_draw", args=("line",)),
    ActionSpec("draw_poly", "Draw Polygon", Category.DRAW, "Polygon (D)",
               icon="edit", shortcut="D", scope="host", method="toggle_draw", args=("poly",)),
    ActionSpec("draw_plane", "Draw Plane", Category.DRAW, "Plane (Shift+W)",
               icon="grid", shortcut="SHIFT+W", scope="host", method="toggle_plane"),
    ActionSpec("plane_3pt", "Plane (3pt)", Category.DRAW, "Plane 3pt",
               icon="grid", scope="host", method="start_plane_3pt"),
    ActionSpec("plane_2pt_z", "Plane (2pt Z)", Category.DRAW, "Plane 2pt Z",
               icon="grid", scope="host", method="start_plane_2pt_z"),
    ActionSpec("plane_from_element", "Plane (Element)", Category.DRAW, "Plane from Element",
               icon="grid", scope="host", method="open_plane_source_dialog"),

    # --- View: ortografik/izo viewport'lar ---
    *[
        ActionSpec(f"vp_{preset}", preset.title(), Category.VIEW, preset.title(),
                   icon="x", scope="host", method="open_viewport", args=(preset,),
                   state=f"vp_{preset}_open")
        for preset in ("iso", "top", "bottom", "front", "back", "left", "right",
                       "iso_sw", "iso_se", "iso_ne", "iso_nw")
    ],
    ActionSpec("vp_close_all", "Close All", Category.VIEW, "Close All",
               icon="x", scope="host", method="close_all_viewports"),

    # --- View: görünürlük / render ---
    ActionSpec("toggle_view_2d", "2D Toggle", Category.VIEW, "2D Plane",
               scope="host", method="toggle_view_2d"),
    ActionSpec("render_mode", "Render Mode", Category.VIEW, "Toggle Render Mode",
               scope="app", method="toggle_render_mode"),
    ActionSpec("local_axes", "Local Axes", Category.VIEW, "Local Axes",
               scope="host", method="toggle_local_axes"),
    ActionSpec("toggle_loads_vis", "Toggle Loads", Category.VIEW, "Show Loads",
               scope="host", method="toggle_loads"),

    # --- Edit ---
    ActionSpec("convert_to_link", "Convert to Link", Category.EDIT, "Convert Frames → Links",
               method="convert_frames_to_links", args=("DefaultLink",)),

    # --- Import / Export ---
    ActionSpec("s2k_import", "S2K Import", Category.FILE, "S2K Import...",
               scope="host", method="open_s2k_import"),
    ActionSpec("s2k_export", "S2K Export", Category.FILE, "S2K Export...",
               scope="host", method="open_s2k_export"),
]


def build_commands(host: "UIHost") -> dict[str, Callable]:
    """ActionSpec listesinden runtime dispatch tablosu üret."""
    app: CadApp = host.app
    cmds: dict[str, Callable] = {}

    for spec in ACTION_SPECS:
        target: Any
        if spec.scope == "host":
            target = host
        elif spec.scope == "app":
            target = app
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

    for panel_name in app.panels:
        cmds[panel_name] = (lambda n=panel_name: host.toggle_panel(n))

    return cmds


def build_panel_states(host: "UIHost") -> dict[str, Callable[[], bool]]:
    """Panel görünürlük ve aksiyon aktiflik durumları."""
    app: CadApp = host.app
    eng = getattr(app, "engine", None)
    mgr = getattr(eng, "draw_mgr", None) if eng else None

    def _draw_mode_is(mode_name: str) -> bool:
        return bool(mgr and mgr.is_active and getattr(mgr, "mode", None) == mode_name)

    states: dict[str, Callable[[], bool]] = {
        "draw_line": lambda: _draw_mode_is("line"),
        "draw_poly": lambda: _draw_mode_is("sequential"),
        "draw_plane": lambda: bool(eng and eng.plane_draw_mgr and eng.plane_draw_mgr.is_active),
        "local_axes": lambda: bool(eng and eng.scene and eng.scene.show_local_axes),
        "toggle_loads_vis": app.get_loads_visible,
        "toggle_view_2d": lambda: bool(
            eng and eng.renderer and eng.renderer.projection == "plane_2d"
        ),
    }

    for preset in ("iso", "top", "bottom", "front", "back", "left", "right",
                   "iso_sw", "iso_se", "iso_ne", "iso_nw"):
        states[f"vp_{preset}_open"] = (
            lambda p=preset: bool(
                app.viewport_manager and app.viewport_manager.get(p)
            )
        )

    for name, entry in app.panels.items():
        inst = entry["instance"]
        states[name] = (lambda i=inst: getattr(i, "visible", False))

    return states