# ui/ui_host.py
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from imgui_bundle import imgui
from OpenGL.GL import (
    GL_ARRAY_BUFFER, GL_BLEND, GL_COLOR_BUFFER_BIT, GL_CULL_FACE,
    GL_DEPTH_BUFFER_BIT, GL_DEPTH_TEST, GL_ELEMENT_ARRAY_BUFFER, GL_FRAMEBUFFER,
    GL_ONE_MINUS_SRC_ALPHA, GL_SRC_ALPHA,
    glBindBuffer, glBindFramebuffer, glBindVertexArray, glBlendFunc, glClear,
    glClearColor, glDisable, glEnable, glUseProgram, glViewport,
)

from assets.themes import _apply_dark_theme, _load_fonts
from app.commands import project_commands as PC
from app.services.panel_registry import PanelEntry
from inspector import InspectorWindow
from logging_config import CadLogger
from plane.plane_source_dialog import PlaneSourceDialog
from ui.actions_registry import ACTION_SPECS, build_commands, build_panel_states
from ui.base.panel_base import CATEGORY_ORDER
from ui.context_menu import ContextMenuManager
from ui.context_resolvers import resolve_context
from ui.registry import discover_panels, validate
from ui.widgets.file_dialog import ImGuiFileDialog
from ui.widgets.status_bar import StatusBar
from ui.widgets.toolbar import Toolbar
from viewport.viewport_panel import ViewportPanel

if TYPE_CHECKING:
    from app.cad_app import CadApp

logger = CadLogger.get(__name__)


class UIHost:
    """
    Sadece UI altyapısı: panel kaydı, çizim döngüsü, viewport yönetimi.

    - Domain/engine/servis çağrısı YAPMAZ.
    - Tüm aksiyonlar `command_queue.put(PC.*)` ile komut kuyruğuna gider.
    - Panel durumu `app.panel_registry` üzerinden yönetilir.
    """

    def __init__(self, app: "CadApp"):
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
        self.context_menu = ContextMenuManager(self.app)

    # ------------------------------------------------------------------
    # YAŞAM DÖNGÜSÜ
    # ------------------------------------------------------------------
    def init_context(self) -> None:
        imgui.create_context()
        io = imgui.get_io()
        io.config_flags |= imgui.ConfigFlags_.docking_enable
        io.config_windows_move_from_title_bar_only = True
        _load_fonts(font_size=16)
        _apply_dark_theme()

    def on_engine_ready(self) -> None:
        ps = self.app.project_service
        self.file_dialog = ImGuiFileDialog()
        self.plane_source_dialog = PlaneSourceDialog(self)
        self.inspector = InspectorWindow(scene=ps.project.scene)
        self.inspector.set_project(ps.project)
        self.inspector.app = self.app

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
        logger.info(
            "[UIHost] Hazır (%d panel, %d aksiyon)",
            len(self.app.panel_registry.all()), len(ACTION_SPECS),
        )

    def shutdown(self) -> None:
        self._viewport_panels.clear()
        self._initialized = False

    # ------------------------------------------------------------------
    # PANEL YÖNETİMİ  (tek sorumluluk)
    # ------------------------------------------------------------------
    def _init_registry(self) -> None:
        import ui.panels as panels_pkg

        discovered = discover_panels(panels_pkg)
        errors = validate(discovered, ACTION_SPECS)
        if errors:
            for e in errors:
                logger.error("[UIHost] panel doğrulama: %s", e)

        for spec in discovered:
            inst = spec.cls(app=self.app)
            self.app.panel_registry.register(PanelEntry(
                instance=inst,
                name=spec.name,
                title=spec.title,
                category=str(spec.category),
                quick=spec.quick,
                shortcut=spec.shortcut,
                menu_label=spec.menu_label,
                icon=spec.icon,
                context=list(spec.context),
            ))

        self._menu_specs = list(discovered) + list(ACTION_SPECS)
        self._category_order = [str(c) for c in CATEGORY_ORDER]

    def get_panel(self, name: str):
        return self.app.panel_registry.instance(name)

    def prepare_panel(self, name: str, panel) -> None:
        entry = self.app.panel_registry.get(name)
        keys = entry.context if entry else []
        panel.set_context(resolve_context(self, self.app, keys))

    def toggle_panel(self, name: str) -> None:
        entry = self.app.panel_registry.get(name)
        if not entry:
            return
        panel = entry.instance
        if getattr(panel, "visible", False):
            panel.close()
            return
        self.prepare_panel(name, panel)
        panel.open()

    def open_panel(self, name: str, **kwargs) -> None:
        entry = self.app.panel_registry.get(name)
        if not entry:
            return
        panel = entry.instance
        self.prepare_panel(name, panel)
        panel.open(**kwargs)

    def on_panel_applied(self, panel) -> None:
        self.command_queue.put(PC.RefreshGeometry())

    # ------------------------------------------------------------------
    # AKSİYONLAR — hepsi komut kuyruğuna gider, UIHost iş YAPMAZ
    # ------------------------------------------------------------------
    def new_project(self) -> None:
        self.command_queue.put(PC.NewProject())

    def open_open_dialog(self) -> None:
        if self.file_dialog is None:
            return
        self.file_dialog.open(
            mode="open", filters=[".cd4"], title="Proje Aç",
            initial_dir=os.getcwd(),
            on_select=lambda path: self.command_queue.put(PC.OpenProject(path)),
        )

    def open_save_dialog(self) -> None:
        if self.file_dialog is None:
            return
        self.file_dialog.open(
            mode="save", filters=[".cd4"], title="Projeyi Kaydet",
            initial_dir=os.getcwd(), default_name="model.cd4",
            on_select=lambda path: self.command_queue.put(PC.SaveProjectAs(path)),
        )

    def quick_save(self) -> None:
        # Yol varsa doğrudan kaydet; yoksa dialog aç (UI kararı)
        if self.app.project_service.file_path:
            self.command_queue.put(PC.SaveProject(self.app.project_service.file_path))
        else:
            self.open_save_dialog()

    def close_app(self) -> None:
        self.command_queue.put(PC.QuitApp())

    def toggle_draw(self, sender: str | None = None) -> None:
        if sender == "poly":
            self.command_queue.put(PC.StartDrawTool("sequential"))
        else:
            self.command_queue.put(PC.StartDrawTool("line"))

    def toggle_plane(self) -> None:
        self.command_queue.put(PC.StartPlaneTool())

    def start_plane_3pt(self) -> None:
        self.command_queue.put(PC.StartPlane3pt())

    def start_plane_2pt_z(self) -> None:
        self.command_queue.put(PC.StartPlane2ptZ())

    def open_plane_source_dialog(self) -> None:
        if self.plane_source_dialog is not None:
            self.plane_source_dialog.open()

    def open_inspector(self) -> None:
        self.command_queue.put(PC.OpenInspector())

    def toggle_local_axes(self) -> None:
        self.command_queue.put(PC.ToggleLocalAxes())

    def toggle_loads(self) -> None:
        self.command_queue.put(PC.ToggleLoadsVisible(None))

    def toggle_view_2d(self) -> None:
        self.command_queue.put(PC.Toggle2D())

    def toggle_render_mode(self) -> None:
        self.command_queue.put(PC.ToggleRenderMode())
        self.command_queue.put(PC.RefreshGeometry())

    def convert_frames_to_link(self, link_prop_name: str = "DefaultLink") -> None:
        self.command_queue.put(PC.ConvertFramesToLinks(link_prop_name))

    def open_s2k_import(self) -> None:
        self.open_panel("s2k_panel", mode="import")

    def open_s2k_export(self) -> None:
        self.open_panel("s2k_panel", mode="export")

    # ------------------------------------------------------------------
    # ÇİZİM
    # ------------------------------------------------------------------
    def notify_key(self, key: int, action: int, mods: int) -> None:
        self.status_bar.notify_key(key, action, mods)

    def draw_frame(self, dt: float) -> None:
        if not self._initialized:
            return

        self._reset_gl_state()
        self._draw_dock_space()

        ps = self.app.project_service
        if self.toolbar is not None:
            self.toolbar.draw(
                model_text=ps.model_text,
                current_unit=ps.project.unit_system,
                project=ps.project,
            )

        self._draw_marquee_overlays()
        if self.file_dialog is not None:
            self.file_dialog.draw()

        for vp_panel in list(self._viewport_panels):
            vp_panel.draw()

        for entry in self.app.panel_registry.visible():
            entry.instance.draw()

        if self.plane_source_dialog is not None:
            self.plane_source_dialog.draw()
        if self.inspector is not None:
            self.inspector.draw()

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
        self.context_menu.render()
        imgui.end()

    # ------------------------------------------------------------------
    # VIEWPORT — sadece mouse/overlay koordinasyonu (domain yok)
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
                    (p for p in self._viewport_panels
                     if p.viewport_name == self._last_active_viewport_name),
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
            if target._is_hovered and imgui.is_mouse_clicked(imgui_btn):
                eng.input.dispatch_click(x_px, y_px, btn_id)
            if imgui.is_mouse_released(imgui_btn):
                eng.input.dispatch_release(x_px, y_px, btn_id)

        if target._is_hovered:
            wheel = float(io.mouse_wheel)
            if wheel != 0.0:
                eng.input.dispatch_scroll(wheel)
                io.mouse_wheel = 0.0

    def _draw_marquee_overlays(self) -> None:
        eng = self.app.engine
        marquee = getattr(eng, "marquee", None) if eng else None
        if not marquee or not marquee.is_active:
            return
        coords = marquee.get_box_coords()
        if not coords:
            return
        panel = next((p for p in self._viewport_panels
                      if p.viewport_name == marquee.viewport_name), None)
        if not panel:
            return
        x1, y1, x2, y2 = coords
        min_x, max_x = min(x1, x2), max(x1, x2)
        min_y, max_y = min(y1, y2), max(y1, y2)
        item_min = panel._item_min
        p0 = imgui.ImVec2(item_min.x + min_x, item_min.y + min_y)
        p1 = imgui.ImVec2(item_min.x + max_x, item_min.y + max_y)
        is_crossing = x2 < x1
        fill_color = (
            imgui.ImVec4(0.20, 0.85, 0.20, 0.22) if is_crossing
            else imgui.ImVec4(0.20, 0.50, 0.95, 0.22)
        )
        border_color = (
            imgui.ImVec4(0.30, 1.00, 0.30, 0.95) if is_crossing
            else imgui.ImVec4(0.40, 0.75, 1.00, 0.95)
        )
        draw_list = imgui.get_foreground_draw_list()
        draw_list.add_rect_filled(p0, p1, imgui.get_color_u32(fill_color))
        draw_list.add_rect(p0, p1, imgui.get_color_u32(border_color))

    # ------------------------------------------------------------------
    # VIEWPORT YÖNETİMİ — yaşam döngüsü (UIHost sorumluluğu)
    # ------------------------------------------------------------------
    def _ensure_default_viewport(self) -> None:
        vm = self.app.viewport_manager
        if vm is None:
            return
        if vm.get("iso") is None:
            vm.create_viewport(
                name="iso", width=self.app.width, height=self.app.height, preset="iso",
            )
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

    # ------------------------------------------------------------------
    # VIEW MENÜ — checkbox → komut
    # ------------------------------------------------------------------
    def _build_view_menu(self):
        app = self.app
        vs = app.view_service

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
            self._toggle_row("Loads", "loads", vs.get_loads_visible())
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
    # PROJE / SEÇİM HOOK'LARI — sadece panel iterasyonu
    # ------------------------------------------------------------------
    def reset_all(self) -> None:
        if self._is_resetting:
            return
        self._is_resetting = True
        try:
            for entry in self.app.panel_registry.all():
                panel = entry.instance
                panel.visible = False
                panel._preview_snapshot = None
                panel._original = None
                panel.draft = None
                panel._dirty = False

            self.close_all_viewports()
            self._ensure_default_viewport()
            self.command_queue.put(PC.ClearSelection())
        finally:
            self._is_resetting = False

    def on_project_changed(self) -> None:
        if self.inspector is not None:
            self.inspector.set_project(self.app.project_service.project)
        if self._initialized:
            self._ensure_default_viewport()

    def on_selection_changed(self, selected: list) -> None:
        if self.inspector is not None and self.inspector.visible:
            self.inspector.set_selection(selected)
        for entry in self.app.panel_registry.all():
            panel = entry.instance
            if not getattr(panel, "visible", False):
                continue
            hook = (
                getattr(panel, "on_scene_selection_changed", None)
                or getattr(panel, "on_selection_changed", None)
            )
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

    def log_command_result(self, text: str, level: str = "info") -> None:
        panel = self.get_panel("command_panel")
        if panel is not None:
            panel.append_result(text, level=level)
        self.status_bar.notify_command(text)