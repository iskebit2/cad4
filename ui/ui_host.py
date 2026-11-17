from __future__ import annotations

import os
from typing import TYPE_CHECKING

from imgui_bundle import imgui
from OpenGL.GL import (
    GL_ARRAY_BUFFER, GL_BLEND, GL_COLOR_BUFFER_BIT, GL_CULL_FACE,
    GL_DEPTH_BUFFER_BIT, GL_DEPTH_TEST, GL_ELEMENT_ARRAY_BUFFER, GL_FRAMEBUFFER,
    GL_ONE_MINUS_SRC_ALPHA, GL_SRC_ALPHA,
    glBindBuffer, glBindFramebuffer, glBindVertexArray, glBlendFunc, glClear, glClearColor,
    glDisable, glEnable, glUseProgram, glViewport,
)

from assets.themes import _apply_dark_theme, _load_fonts
from app.commands import project_commands as PC
from app.commands.project_commands import RefreshGeometry
from domain.element import Area, Frame, Link, Node
from domain.polygon import Polygon
from inspector import InspectorWindow
from logging_config import CadLogger
from plane.plane_source_dialog import PlaneSourceDialog
from ui.actions_registry import ACTION_SPECS, build_commands, build_panel_states
from ui.base.panel_base import CATEGORY_ORDER
from ui.registry import discover_panels, validate
from ui.widgets.file_dialog import ImGuiFileDialog
from ui.widgets.status_bar import StatusBar
from ui.widgets.toolbar import Toolbar
from viewport.viewport_panel import ViewportPanel

if TYPE_CHECKING:
    from app.cad_app import CadApp

logger = CadLogger.get(__name__)

_CONTEXT_RESOLVERS = {
    "engine": lambda h, app, eng, prj, scn, mm, rnd, cam, sel: eng,
    "scene": lambda h, app, eng, prj, scn, mm, rnd, cam, sel: scn,
    "math_model": lambda h, app, eng, prj, scn, mm, rnd, cam, sel: mm,
    "project": lambda h, app, eng, prj, scn, mm, rnd, cam, sel: prj,
    "catalog": lambda h, app, eng, prj, scn, mm, rnd, cam, sel: app._catalog,
    "selection": lambda h, app, eng, prj, scn, mm, rnd, cam, sel: sel,
    "selection_frames": lambda h, app, eng, prj, scn, mm, rnd, cam, sel: [e for e in sel if isinstance(e, Frame)],
    "selection_areas": lambda h, app, eng, prj, scn, mm, rnd, cam, sel: [e for e in sel if isinstance(e, Area)],
    "selection_polygons": lambda h, app, eng, prj, scn, mm, rnd, cam, sel: [e for e in sel if isinstance(e, Polygon)],
    "selection_links": lambda h, app, eng, prj, scn, mm, rnd, cam, sel: [e for e in sel if isinstance(e, Link)],
    "selection_nodes": lambda h, app, eng, prj, scn, mm, rnd, cam, sel: [e for e in sel if isinstance(e, Node)],
    "patterns": lambda h, app, eng, prj, scn, mm, rnd, cam, sel: list(getattr(prj, "load_patterns", {}).keys()),
    "sections": lambda h, app, eng, prj, scn, mm, rnd, cam, sel: list(getattr(prj, "sections", {}).keys()),
    "materials": lambda h, app, eng, prj, scn, mm, rnd, cam, sel: list(getattr(prj, "materials", {}).keys()),
    "renderer": lambda h, app, eng, prj, scn, mm, rnd, cam, sel: rnd,
    "math_model_renderer": lambda h, app, eng, prj, scn, mm, rnd, cam, sel: rnd.math_model_renderer if rnd else None,
    "camera": lambda h, app, eng, prj, scn, mm, rnd, cam, sel: cam,
    "wind_analysis_ref": lambda h, app, eng, prj, scn, mm, rnd, cam, sel: app.wind_state(),
    "selection_manager": lambda h, app, eng, prj, scn, mm, rnd, cam, sel: eng.sel_mgr if eng else None,
    "selection_policy": lambda h, app, eng, prj, scn, mm, rnd, cam, sel: eng.sel_policy if eng else None,
    "selection_count": lambda h, app, eng, prj, scn, mm, rnd, cam, sel: len(sel),
}


class UIHost:
    def __init__(self, app: CadApp):
        self.app = app
        self.command_queue = app.command_queue
        self.toolbar: Toolbar | None = None
        self.status_bar = StatusBar()
        self.file_dialog: ImGuiFileDialog | None = None
        self.plane_source_dialog: PlaneSourceDialog | None = None
        self.inspector: InspectorWindow | None = None

        self._viewport_panels: list[ViewportPanel] = []
        self._last_active_viewport_name: str | None = None
        self._menu_specs: list = []
        self._category_order: list[str] = []
        self._is_resetting = False
        self._initialized = False

    def init_context(self) -> None:
        imgui.create_context()
        io = imgui.get_io()
        io.config_flags |= imgui.ConfigFlags_.docking_enable
        io.config_windows_move_from_title_bar_only = True
        _load_fonts(font_size=16)
        _apply_dark_theme()

    def on_engine_ready(self) -> None:
        self.file_dialog = ImGuiFileDialog()
        self.plane_source_dialog = PlaneSourceDialog(self)
        self.inspector = InspectorWindow(scene=self.app.current_project.math_model)
        self.app.inspector = self.inspector

        self._init_registry()
        self.toolbar = Toolbar(
            commands=build_commands(self),
            panel_states=build_panel_states(self),
            specs=self._menu_specs,
            categories=self._category_order,
            extra_menus=[self._build_view_menu()],
        )

        self._ensure_default_viewport()
        self._initialized = True
        logger.info("[UIHost] Hazır (%d panel, %d aksiyon)", len(self.app.panels), len(ACTION_SPECS))

        import inspect
        registry = self.app._command_registry
        print("Registry türü:", type(registry))
        print("Public metotlar:")
        for name, _ in inspect.getmembers(registry, predicate=inspect.ismethod):
            if not name.startswith("_"):
                print("  -", name)
        print("Attribute'lar:")
        for name in dir(registry):
            if not name.startswith("_") and not callable(getattr(registry, name)):
                print("  -", name, "=", type(getattr(registry, name)))
        

    def _init_registry(self) -> None:
        import ui.panels as panels_pkg

        discovered = discover_panels(panels_pkg)
        validate(discovered, ACTION_SPECS)

        for spec in discovered:
            inst = spec.cls(app=self.app)
            self.app.panels[spec.name] = {
                "instance": inst,
                "title": spec.title,
                "category": str(spec.category),
                "quick": spec.quick,
                "shortcut": spec.shortcut,
                "menu_label": spec.menu_label,
                "icon": spec.icon,
                "context": list(spec.context),
            }
            self.app._panels_by_category.setdefault(str(spec.category), []).append(spec.name)

        self._menu_specs = list(discovered) + list(ACTION_SPECS)
        self._category_order = [str(c) for c in CATEGORY_ORDER]

    # ------------------------------------------------------------------
    # PANEL YÖNETİMİ
    # ------------------------------------------------------------------
    def get_panel(self, name: str):
        entry = self.app.panels.get(name)
        return entry["instance"] if entry else None

    def prepare_panel(self, name: str, panel) -> None:
        keys = self.app.panels[name].get("context", [])
        panel.set_context(self._resolve_context(keys))

    def _resolve_context(self, keys: list[str]) -> dict:
        if not keys:
            return {}

        app = self.app
        eng = app.engine
        project = app.current_project
        scene = eng.scene if eng else (project.scene if project else None)
        math_model = eng.math_model if eng else (project.math_model if project else None)
        renderer = eng.renderer if eng else None
        camera = eng.cam if eng else None

        if eng and eng.sel_mgr:
            selection = list(eng.sel_mgr.get_selected())
        elif math_model:
            selection = list(math_model.get_selected())
        else:
            selection = []

        context = {}
        for key in keys:
            resolver = _CONTEXT_RESOLVERS.get(key)
            if resolver is not None:
                context[key] = resolver(self, app, eng, project, scene, math_model, renderer, camera, selection)
        return context

    def toggle_panel(self, name: str) -> None:
        entry = self.app.panels.get(name)
        if not entry:
            return
        panel = entry["instance"]
        if getattr(panel, "visible", False):
            panel.close()
            return
        self.prepare_panel(name, panel)
        panel.open()

    def open_panel(self, name: str, **kwargs) -> None:
        entry = self.app.panels.get(name)
        if not entry:
            return
        panel = entry["instance"]
        self.prepare_panel(name, panel)
        panel.open(**kwargs)

    def on_panel_applied(self, panel) -> None:
        self.command_queue.put(RefreshGeometry())

    # ------------------------------------------------------------------
    # FRAME ÇİZİMİ
    # ------------------------------------------------------------------
    def notify_key(self, key: int, action: int, mods: int) -> None:
        self.status_bar.notify_key(key, action, mods)

    def draw_frame(self, dt: float) -> None:
        if not self._initialized:
            return

        self._reset_gl_state()
        self._draw_dock_space()

        if self.toolbar is not None:
            self.toolbar.draw(
                model_text=self.app._model_text,
                current_unit=self.app.current_project.unit_system if self.app.current_project else None,
                project=self.app.current_project,
            )

        self._draw_marquee_overlays()
        if self.file_dialog is not None:
            self.file_dialog.draw()

        for vp_panel in list(self._viewport_panels):
            vp_panel.draw()

        for entry in self.app.panels.values():
            panel = entry["instance"]
            if getattr(panel, "visible", False):
                panel.draw()

        if self.plane_source_dialog is not None:
            self.plane_source_dialog.draw()

        self._consume_plane_completion()
        self._forward_viewport_mouse_events()

        eng = self.app.engine
        inp = eng.input.state if eng else None
        is_drawing = bool(eng and eng.draw_mgr and eng.draw_mgr.is_active)
        app_status = "Çizim Aktif" if is_drawing else self.status_bar.last_event_text

        self.status_bar.draw(
            engine_connected=(eng is not None),
            app_status=app_status,
            mouse_pos=(inp.mouse_pos.x, inp.mouse_pos.y) if inp else (0.0, 0.0),
            mouse_buttons=inp.buttons if inp else {},
            modifiers=inp.modifiers if inp else 0,
            fps=(1.0 / dt) if dt > 0 else 0.0,
        )

    def _reset_gl_state(self) -> None:
        w = max(1, self.app.width)
        h = max(1, self.app.height)
        glViewport(0, 0, w, h)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glClearColor(0.06, 0.07, 0.10, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glUseProgram(0)
        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_CULL_FACE)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def _draw_dock_space(self) -> None:
        viewport = imgui.get_main_viewport()
        work_pos = imgui.ImVec2(viewport.work_pos.x, viewport.work_pos.y)
        work_size = imgui.ImVec2(
            viewport.work_size.x,
            max(1.0, viewport.work_size.y - self.status_bar.height),
        )
        imgui.set_next_window_pos(work_pos)
        imgui.set_next_window_size(work_size)
        imgui.push_style_var(imgui.StyleVar_.window_rounding, 0.0)
        imgui.push_style_var(imgui.StyleVar_.window_border_size, 0.0)
        imgui.push_style_var(imgui.StyleVar_.window_padding, imgui.ImVec2(0.0, 0.0))
        flags = (
            imgui.WindowFlags_.no_title_bar
            | imgui.WindowFlags_.no_collapse
            | imgui.WindowFlags_.no_resize
            | imgui.WindowFlags_.no_move
            | imgui.WindowFlags_.no_bring_to_front_on_focus
            | imgui.WindowFlags_.no_nav_focus
            | imgui.WindowFlags_.no_docking
            | imgui.WindowFlags_.no_background
        )
        imgui.begin("##DockSpace", None, flags)
        imgui.pop_style_var(3)
        imgui.dock_space(imgui.get_id("DockSpace"))
        imgui.end()

    # ------------------------------------------------------------------
    # VIEWPORT MOUSE & MARQUEE
    # ------------------------------------------------------------------
    def _forward_viewport_mouse_events(self) -> None:
        eng = self.app.engine
        vm = self.app.viewport_manager
        if eng is None or vm is None or not self._viewport_panels:
            return

        io = imgui.get_io()
        state = eng.input.state
        state.modifiers = (
            (1 if io.key_shift else 0)
            | (2 if io.key_ctrl else 0)
            | (4 if io.key_alt else 0)
            | (8 if io.key_super else 0)
        )

        target = next((p for p in self._viewport_panels if p._is_hovered), None)
        if target is None and (io.mouse_down[0] or io.mouse_down[1] or io.mouse_down[2]):
            if self._last_active_viewport_name:
                target = next(
                    (p for p in self._viewport_panels if p.viewport_name == self._last_active_viewport_name),
                    None,
                )

        if target is None:
            return

        if self._last_active_viewport_name != target.viewport_name:
            vm.set_active(target.viewport_name)
            self._last_active_viewport_name = target.viewport_name

        vp = vm.get(target.viewport_name)
        if vp is None:
            return

        mouse = imgui.get_mouse_pos()
        x_px = int(mouse.x - target._item_min.x)
        y_px = int(mouse.y - target._item_min.y)

        state.mouse_pos.x = float(x_px)
        state.mouse_pos.y = float(y_px)
        state.buttons[0] = bool(imgui.is_mouse_down(imgui.MouseButton_.left))
        state.buttons[1] = bool(imgui.is_mouse_down(imgui.MouseButton_.right))
        state.buttons[2] = bool(imgui.is_mouse_down(imgui.MouseButton_.middle))

        if target._is_hovered:
            eng.set_viewport_pointer(vp, x_px, y_px)
            eng.input.dispatch_move(x_px, y_px, float(io.mouse_delta.x), float(io.mouse_delta.y))

            for btn_id, imgui_btn in (
                (0, imgui.MouseButton_.left),
                (2, imgui.MouseButton_.middle),
                (1, imgui.MouseButton_.right),
            ):
                if imgui.is_mouse_clicked(imgui_btn):
                    eng.input.dispatch_click(x_px, y_px, btn_id)

            wheel = float(io.mouse_wheel)
            if wheel != 0.0:
                eng.input.dispatch_scroll(wheel)
                io.mouse_wheel = 0.0

        for btn_id, imgui_btn in (
            (0, imgui.MouseButton_.left),
            (2, imgui.MouseButton_.middle),
            (1, imgui.MouseButton_.right),
        ):
            if imgui.is_mouse_released(imgui_btn):
                eng.input.dispatch_release(x_px, y_px, btn_id)

    def _draw_marquee_overlays(self) -> None:
        eng = self.app.engine
        marquee = getattr(eng, "marquee", None) if eng else None
        if not marquee or not marquee.is_active:
            return

        coords = marquee.get_box_coords()
        if not coords:
            return

        panel = next((p for p in self._viewport_panels if p.viewport_name == marquee.viewport_name), None)
        if not panel:
            return

        x1, y1, x2, y2 = coords
        min_x, max_x = min(x1, x2), max(x1, x2)
        min_y, max_y = min(y1, y2), max(y1, y2)

        item_min = panel._item_min
        p0 = imgui.ImVec2(item_min.x + min_x, item_min.y + min_y)
        p1 = imgui.ImVec2(item_min.x + max_x, item_min.y + max_y)

        is_crossing = x2 < x1
        fill_color = imgui.ImVec4(0.20, 0.85, 0.20, 0.22) if is_crossing else imgui.ImVec4(0.20, 0.50, 0.95, 0.22)
        border_color = imgui.ImVec4(0.30, 1.00, 0.30, 0.95) if is_crossing else imgui.ImVec4(0.40, 0.75, 1.00, 0.95)

        draw_list = imgui.get_foreground_draw_list()
        draw_list.add_rect_filled(p0, p1, imgui.get_color_u32(fill_color))
        draw_list.add_rect(p0, p1, imgui.get_color_u32(border_color))

    # ------------------------------------------------------------------
    # ACTION_SPECS HOST METOTLARI
    # ------------------------------------------------------------------
    def toggle_draw(self, sender: str | None = None) -> None:
        eng = self.app.engine
        if not eng or not eng.draw_mgr:
            return
        mgr = eng.draw_mgr
        if mgr.is_active:
            mgr.cancel()
            return
        if sender:
            panel_name = "polygon_properties" if sender == "poly" else "line_properties"
            mode = "sequential" if sender == "poly" else "line"
            panel = self.get_panel(panel_name)
            if panel is not None and not getattr(panel, "visible", False):
                self.prepare_panel(panel_name, panel)
                panel.open()
            mgr.start(mode=mode)

    def toggle_plane(self) -> None:
        pdm = getattr(self.app.engine, "plane_draw_mgr", None)
        if pdm is None:
            return
        if pdm.is_active:
            pdm.cancel()
            return
        pdm.start_3pt()

    def start_plane_3pt(self) -> None:
        if self.app.engine and self.app.engine.plane_draw_mgr:
            self.app.engine.plane_draw_mgr.start_3pt()

    def start_plane_2pt_z(self) -> None:
        if self.app.engine and self.app.engine.plane_draw_mgr:
            self.app.engine.plane_draw_mgr.start_2pt_z()

    def open_plane_source_dialog(self) -> None:
        if self.plane_source_dialog is not None:
            self.plane_source_dialog.open()

    def toggle_local_axes(self) -> None:
        eng = self.app.engine
        if eng and eng.scene:
            eng.scene.show_local_axes = not eng.scene.show_local_axes

    def toggle_loads(self) -> None:
        self.app.set_loads_visible(not self.app.get_loads_visible())

    def toggle_view_2d(self) -> None:
        self.app.toggle_2d()

    def open_open_dialog(self) -> None:
        self.file_dialog.open(
            mode="open", filters=[".cd4"], title="Proje Aç",
            initial_dir=os.getcwd(),
            on_select=lambda path: self.command_queue.put(PC.OpenProject(path)),
        )

    def open_save_dialog(self) -> None:
        self.file_dialog.open(
            mode="save", filters=[".cd4"], title="Projeyi Kaydet",
            initial_dir=os.getcwd(), default_name="model.cd4",
            on_select=lambda path: self.command_queue.put(PC.SaveProjectAs(path)),
        )

    def open_s2k_import(self) -> None:
        self.open_panel("s2k_panel", mode="import")

    def open_s2k_export(self) -> None:
        self.open_panel("s2k_panel", mode="export")

    def close_app(self) -> None:
        self.app.request_quit()

    def _ensure_default_viewport(self) -> None:
        vm = self.app.viewport_manager
        if vm is None:
            return
        if vm.get("iso") is None:
            vm.create_viewport(name="iso", width=1200, height=800, preset="iso")
        if not any(p.viewport_name == "iso" for p in self._viewport_panels):
            self._viewport_panels.append(ViewportPanel(self, "iso", vm))

    def open_viewport(self, preset: str):
        vm = self.app.viewport_manager
        if vm is None:
            return None
        name = vm.next_name(preset)
        vp = vm.create_viewport(name=name, width=800, height=600, preset=preset)
        self._viewport_panels.append(ViewportPanel(self, name, vm))
        return vp

    def close_all_viewports(self) -> None:
        vm = self.app.viewport_manager
        if vm is not None:
            for name in list(vm.viewports.keys()):
                vm.remove_viewport(name)
        self._viewport_panels.clear()
        self._last_active_viewport_name = None

    def on_viewport_panel_closed(self, panel: ViewportPanel) -> None:
        if panel in self._viewport_panels:
            self._viewport_panels.remove(panel)
        if self._last_active_viewport_name == panel.viewport_name:
            self._last_active_viewport_name = None

    def _consume_plane_completion(self) -> None:
        eng = self.app.engine
        pdm = eng.plane_draw_mgr if eng else None
        if pdm is None or pdm.is_active or pdm.completed_plane is None:
            return
        plane = pdm.completed_plane
        pdm.completed_plane = None
        pm = self.get_panel("plane_manager")
        if pm is not None:
            pm._selected_name = plane.name
            pm.visible = True
        if eng and self.app.current_project:
            eng.update_geo(self.app.current_project)

    def _build_view_menu(self):
        app = self.app

        def _draw():
            eng = app.engine
            if eng is None:
                imgui.text_disabled("Engine hazır değil")
                return

            imgui.text_disabled("GÖRÜNÜRLÜK")
            imgui.separator()
            for label, key in [
                ("Scene",       "scene"),
                ("Grid",        "grid"),
                ("Polygon",     "polygon"),
                ("Lines",       "lines"),
                ("Labels",      "labels"),
                ("Interaction", "interaction"),
            ]:
                self._toggle_row(label, key, bool(eng.show.get(key, True)))

            imgui.separator()
            imgui.text_disabled("YÜK")
            imgui.separator()
            self._toggle_row("Loads", "loads", app.get_loads_visible())
            self._toggle_row("Wind Zones", "zones", bool(eng.show.get("zones", True)))

            imgui.separator()
            imgui.text_disabled("EKSEN")
            imgui.separator()
            self._toggle_row("Global Axis", "global_axis", bool(eng.show.get("global_axis", True)))
            self._toggle_row("Local Axes", "local_axes", bool(eng.scene and eng.scene.show_local_axes))

            imgui.separator()
            imgui.text_disabled("RENDER MODU")
            imgui.separator()
            mode = eng.renderer.get_render_mode() if eng.renderer else "shaded"
            for m, lbl in (("shaded", "Shaded"), ("simple", "Simple")):
                if imgui.radio_button(lbl, mode == m):
                    self.command_queue.put(PC.SetRenderMode(m))
                    self.command_queue.put(PC.RefreshGeometry())

        return ("View", _draw)

    def _toggle_row(self, label: str, key: str, current: bool) -> None:
        changed, new_val = imgui.checkbox(f"##{key}", current)
        imgui.same_line()
        imgui.text(label)
        if not changed:
            return
        if key == "local_axes":
            self.command_queue.put(PC.ToggleLocalAxes())
        elif key == "loads":
            self.command_queue.put(PC.ToggleLoadsVisible(new_val))
        else:
            self.command_queue.put(PC.ToggleRenderFlag(key, new_val))

    # ------------------------------------------------------------------
    # PROJE / SEÇİM HOOK'LARI
    # ------------------------------------------------------------------
    def reset_all(self) -> None:
        if self._is_resetting:
            return
        self._is_resetting = True
        try:
            for entry in self.app.panels.values():
                panel = entry.get("instance")
                if panel:
                    panel.visible = False
                    panel._preview_snapshot = None
                    panel._original = None
                    panel.draft = None
                    panel._dirty = False

            self.close_all_viewports()
            self._ensure_default_viewport()

            eng = self.app.engine
            if eng is not None:
                if eng.sel_mgr:
                    eng.sel_mgr.clear()
                eng.clear_hover()
                if eng.interaction_renderer:
                    eng.interaction_renderer.preview_plane = None
        finally:
            self._is_resetting = False

    def on_project_changed(self) -> None:
        if self._initialized:
            self._ensure_default_viewport()

    def on_selection_changed(self, selected: list) -> None:
        for name, entry in self.app.panels.items():
            panel = entry["instance"]
            if not getattr(panel, "visible", False):
                continue
            hook = getattr(panel, "on_scene_selection_changed", None) or getattr(panel, "on_selection_changed", None)
            if callable(hook):
                hook(selected)

    def on_unit_changed(self) -> None:
        panel = self.get_panel("grid")
        if panel is not None and hasattr(panel, "on_unit_changed"):
            panel.on_unit_changed()

    def on_wind_analysis_done(self, key: str) -> None:
        panel = self.get_panel("wind")
        if panel is not None and hasattr(panel, "_invalidate_zones_cache"):
            panel._invalidate_zones_cache()

    def on_hover_changed(self, key: str) -> None:
        pass

    def log_command_result(self, text: str, level: str = "info") -> None:
        panel = self.get_panel("command_panel")
        if panel is not None:
            panel.append_result(text, level=level)
        self.status_bar.notify_command(text)

    def shutdown(self) -> None:
        self._viewport_panels.clear()
        self._initialized = False