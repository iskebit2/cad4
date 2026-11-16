# ui/ui_host.py
from __future__ import annotations

from typing import TYPE_CHECKING

import os
import glfw
from imgui_bundle import imgui
from OpenGL.GL import (
    GL_ARRAY_BUFFER, GL_BLEND, GL_COLOR_BUFFER_BIT, GL_CULL_FACE,
    GL_DEPTH_BUFFER_BIT, GL_DEPTH_TEST, GL_ELEMENT_ARRAY_BUFFER, GL_FRAMEBUFFER,
    GL_ONE_MINUS_SRC_ALPHA, GL_SRC_ALPHA,
    glBindBuffer, glBindFramebuffer, glBindVertexArray, glBlendFunc, glClear, glClearColor,
    glDisable, glEnable, glUseProgram, glViewport,
)
from core.commands import project_commands as PC
from core.commands.command_queue import CommandQueue
from core.commands.project_commands import RefreshGeometry
from domain.element import Area, Frame, Link, Node
from domain.polygon import Polygon
from logging_config import CadLogger
from ui.actions_registry import ACTION_SPECS, build_commands, build_panel_states
from ui.panels.viewport_panel import ViewportPanel

if TYPE_CHECKING:
    from app.cad_app import CadApp

logger = CadLogger.get(__name__)


class UIHost:
    """ImGui frame, dock space, panel yönetimi, event bridge."""

    def __init__(self, app: CadApp):
        self.app = app
        self._io = None
        self._initialized = False
        self._panel_specs = []
        self._category_order: list[str] = []
        self._menu_specs: list = []

        # Viewport paneli listesi (ViewportPanel örnekleri)
        self._viewport_panels: list = []
        self._last_active_viewport_name: str | None = None

        # Toolbar, dialogs, inspector vb.
        self.toolbar = None
        self.file_dialog = None
        self.plane_source_dialog = None
        self.debug_panel = None
        self.inspector = None
        self.command_queue = CommandQueue()
        self._icon_mgr = None

    def on_panel_applied(self, panel) -> None:
        """Panel Apply'a bastı. Kuyruğa sadece bir 'geometry refresh' at."""
        self.command_queue.put(RefreshGeometry())

    # ------------------------------------------------------------------
    # CADAPP HOOK'LARI
    # ------------------------------------------------------------------
    def on_engine_ready(self) -> None:
        """Engine hazır olduğunda çağrılır."""
        from core.viewport_manager import ViewportManager  # noqa
        from plane.plane_source_dialog import PlaneSourceDialog
        from app.debug_panel import DebugPanel
        from inspector import InspectorWindow
        from inspector.catalog_project import ProjectCatalog
        from ui.widgets.toolbar import Toolbar
        from ui.panels.viewport_panel import ViewportPanel
        from ui.widgets.file_dialog import ImGuiFileDialog
        

        self.debug_panel = DebugPanel(self)
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

        # İlk viewport paneli
        vp = self.app.viewport_manager.get("iso")
        if vp is None:
            vp = self.app.viewport_manager.create_viewport(
                name="iso", width=1200, height=800, preset="iso",
            )
        panel = ViewportPanel(self.app, "iso", self.app.viewport_manager, preset="iso")
        self._viewport_panels.append(panel)

        self._initialized = True

    def on_selection_changed(self, selected: list) -> None:
        for name, entry in self.app.panels.items():
            p = entry["instance"]
            if not getattr(p, "visible", False):
                continue
            hook = getattr(p, "on_scene_selection_changed", None) or \
                   getattr(p, "on_selection_changed", None)
            if callable(hook):
                try:
                    hook(selected)
                except Exception:
                    logger.exception("Panel '%s' selection hook hatası", name)

    def on_wind_analysis_done(self, key: str) -> None:
        panel = self.get_panel("wind")
        if panel is not None and hasattr(panel, "_invalidate_zones_cache"):
            panel._invalidate_zones_cache()

    def on_unit_changed(self) -> None:
        panel = self.get_panel("grid")
        if panel is not None and hasattr(panel, "on_unit_changed"):
            panel.on_unit_changed()

    # ------------------------------------------------------------------
    # REGISTRY
    # ------------------------------------------------------------------
    def _init_registry(self) -> None:
        from ui.registry import discover_panels
        from ui.base.panel_base import CATEGORY_ORDER
        import ui.panels as panels_pkg

        discovered = discover_panels(panels_pkg)
        logger.info("[registry] %d panel yüklendi", len(discovered))
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
    # PANEL ERİŞİMİ
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
        selection = list(eng.sel_mgr.get_selected()) if eng and eng.sel_mgr else \
                    (list(math_model.get_selected()) if math_model else [])
        resolvers = {
            "engine": lambda: eng,
            "scene": lambda: scene,
            "math_model": lambda: math_model,
            "project": lambda: project,
            "catalog": lambda: app._catalog,
            "selection": lambda: selection,
            "selection_frames": lambda: [e for e in selection if isinstance(e, Frame)],
            "selection_areas": lambda: [e for e in selection if isinstance(e, Area)],
            "selection_polygons": lambda: [e for e in selection if isinstance(e, Polygon)],
            "selection_links": lambda: [e for e in selection if isinstance(e, Link)],
            "selection_nodes": lambda: [e for e in selection if isinstance(e, Node)],
            "patterns": lambda: list(getattr(project, "load_patterns", {}).keys()),
            "sections": lambda: list(getattr(project, "sections", {}).keys()),
            "materials": lambda: list(getattr(project, "materials", {}).keys()),
            "renderer": lambda: renderer,
            "math_model_renderer": lambda: renderer.math_model_renderer if renderer else None,
            "camera": lambda: camera,
            "wind_analysis_ref": lambda: app.wind_state(),
            "selection_manager": lambda: eng.sel_mgr if eng else None,
            "selection_policy":  lambda: eng.sel_policy if eng else None,
            "selection_count":   lambda: len(selection),
        }
        return {k: resolvers[k]() for k in keys if k in resolvers}

    def toggle_panel(self, name: str) -> None:
        entry = self.app.panels.get(name)
        if not entry:
            return
        p = entry["instance"]
        if getattr(p, "visible", False):
            p.close()
            return
        self.prepare_panel(name, p)
        p.open()

    def open_panel(self, name: str, **kwargs) -> None:
        entry = self.app.panels.get(name)
        if not entry:
            return
        p = entry["instance"]
        self.prepare_panel(name, p)
        p.open(**kwargs)

    # ------------------------------------------------------------------
    # FRAME
    # ------------------------------------------------------------------
    def frame(self, dt: float) -> None:
        self.app.tick(dt)
        if not self._initialized:
            return
        if self._io is None:
            self._io = imgui.get_io()

        self._draw_dock_space()
        self.toolbar.draw(
            model_text=self.app._model_text,
            current_unit=self.app.current_project.unit_system if self.app.current_project else None,
            project=self.app.current_project,
        )
        
        self.file_dialog.draw()

        # ★ Tüm viewport'ları engine üzerinden render et (OpenGL engine içinde)
        self.app.viewport_manager.render_all()

        # GL state reset (ImGui çiziminden önce)
        self._reset_gl_state_for_imgui()

        self._draw_panels()
        self._forward_active_viewport_events()
        self.debug_panel.draw()
        self.plane_source_dialog.draw()
        self._consume_plane_completion()

    def _reset_gl_state_for_imgui(self) -> None:
        w = self.app.window.fb_width
        h = self.app.window.fb_height
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

    def _draw_panels(self) -> None:
        for vp_panel in self._viewport_panels:
            vp_panel.draw()
        for entry in self.app.panels.values():
            panel = entry["instance"]
            if getattr(panel, "visible", False):
                panel.draw()

    def _draw_dock_space(self) -> None:
        viewport = imgui.get_main_viewport()
        imgui.set_next_window_pos(viewport.work_pos)
        imgui.set_next_window_size(viewport.work_size)
        imgui.push_style_var(imgui.StyleVar_.window_rounding, 0.0)
        imgui.push_style_var(imgui.StyleVar_.window_border_size, 0.0)
        imgui.push_style_var(imgui.StyleVar_.window_padding, imgui.ImVec2(0, 0))
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
    # EVENT BRIDGE (ImGui → Engine)
    # ------------------------------------------------------------------
    def _forward_active_viewport_events(self) -> None:
        eng = self.app.engine
        vm = self.app.viewport_manager
        if eng is None or vm is None or not self._viewport_panels:
            return

        io = imgui.get_io()
        any_drag = bool(io.mouse_down[0] or io.mouse_down[1] or io.mouse_down[2])

        hovered = next((p for p in self._viewport_panels if p._is_hovered), None)
        target = hovered
        if target is None and any_drag and self._last_active_viewport_name:
            target = next((p for p in self._viewport_panels
                           if p.viewport_name == self._last_active_viewport_name), None)

        mods = 0
        if io.key_ctrl: mods |= glfw.MOD_CONTROL
        if io.key_shift: mods |= glfw.MOD_SHIFT
        if io.key_alt: mods |= glfw.MOD_ALT
        if io.key_super: mods |= glfw.MOD_SUPER
        eng.input.state.modifiers = mods

        if target is None:
            return

        vm.set_active(target.viewport_name)
        self._last_active_viewport_name = target.viewport_name
        self._forward_imgui_events(target)

    def _forward_imgui_events(self, panel) -> None:
        eng = self.app.engine
        if eng is None:
            return
        vp = self.app.viewport_manager.get(panel.viewport_name)
        if vp is None:
            return
        io = imgui.get_io()
        item_min = panel._item_min
        mouse = imgui.get_mouse_pos()
        x_px = int(mouse.x - item_min.x)
        y_px = int(mouse.y - item_min.y)
        self._sync_input_state(eng, io, panel._is_hovered)
        if panel._is_hovered:
            eng.set_viewport_pointer(vp, x_px, y_px)
        dx = float(io.mouse_delta.x)
        dy = float(io.mouse_delta.y)
        if panel._is_hovered:
            eng.input.dispatch_move(x_px, y_px, dx, dy)
        if panel._is_hovered:
            for button, imgui_btn in (
                (0, imgui.MouseButton_.left), (2, imgui.MouseButton_.middle),
                (1, imgui.MouseButton_.right),
            ):
                if imgui.is_mouse_clicked(imgui_btn):
                    eng.input.dispatch_click(x_px, y_px, button)
                    break
        for button, imgui_btn in (
            (0, imgui.MouseButton_.left), (2, imgui.MouseButton_.middle),
            (1, imgui.MouseButton_.right),
        ):
            if imgui.is_mouse_released(imgui_btn):
                eng.input.dispatch_release(x_px, y_px, button)
        wheel = float(io.mouse_wheel)
        if wheel != 0.0 and panel._is_hovered:
            eng.input.dispatch_scroll(wheel)
            io.mouse_wheel = 0.0
        if panel._is_hovered or self._any_viewport_active():
            self._forward_keys(eng)

    def _any_viewport_active(self) -> bool:
        for panel in self._viewport_panels:
            if getattr(panel, "_is_hovered", False):
                return True
        io = imgui.get_io()
        if io.mouse_down[0] or io.mouse_down[1] or io.mouse_down[2]:
            return self._last_active_viewport_name is not None
        return False

    def _forward_keys(self, eng) -> None:
        key_map = {
            imgui.Key.escape: glfw.KEY_ESCAPE,
            imgui.Key.space: glfw.KEY_SPACE,
            imgui.Key.enter: glfw.KEY_ENTER,
            imgui.Key.tab: glfw.KEY_TAB,
            imgui.Key.delete: glfw.KEY_DELETE,
            imgui.Key.backspace: glfw.KEY_BACKSPACE,
            imgui.Key.left_arrow: glfw.KEY_LEFT,
            imgui.Key.right_arrow: glfw.KEY_RIGHT,
            imgui.Key.up_arrow: glfw.KEY_UP,
            imgui.Key.down_arrow: glfw.KEY_DOWN,
        }
        io = imgui.get_io()
        mods = 0
        if io.key_ctrl: mods |= glfw.MOD_CONTROL
        if io.key_shift: mods |= glfw.MOD_SHIFT
        if io.key_alt: mods |= glfw.MOD_ALT
        if io.key_super: mods |= glfw.MOD_SUPER
        for imgui_key, glfw_key in key_map.items():
            if imgui.is_key_pressed(imgui_key):
                eng.input.dispatch_key(glfw_key, mods)

    @staticmethod
    def _sync_input_state(eng, io, item_hovered: bool) -> None:
        state = eng.input.state
        if item_hovered:
            state.buttons[0] = bool(imgui.is_mouse_down(imgui.MouseButton_.left))
            state.buttons[2] = bool(imgui.is_mouse_down(imgui.MouseButton_.middle))
            state.buttons[1] = bool(imgui.is_mouse_down(imgui.MouseButton_.right))
            state.mouse_pos.x = float(io.mouse_pos.x)
            state.mouse_pos.y = float(io.mouse_pos.y)
        mods = 0
        if io.key_ctrl: mods |= glfw.MOD_CONTROL
        if io.key_shift: mods |= glfw.MOD_SHIFT
        if io.key_alt: mods |= glfw.MOD_ALT
        state.modifiers = mods

    # ------------------------------------------------------------------
    # DRAW / TOGGLE ACTIONS
    # ------------------------------------------------------------------
    def toggle_draw(self, sender=None):
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

    def toggle_plane(self):
        pdm = getattr(self.app.engine, "plane_draw_mgr", None)
        if pdm is None:
            return
        if pdm.is_active:
            pdm.cancel()
            return
        pdm.start_3pt()

    def toggle_local_axes(self):
        eng = self.app.engine
        if eng and eng.scene:
            eng.scene.show_local_axes = not eng.scene.show_local_axes

    def toggle_loads(self):
        self.app.set_loads_visible(not self.app.get_loads_visible())

    # ------------------------------------------------------------------
    # VIEWPORT
    # ------------------------------------------------------------------
    def open_viewport(self, preset: str):
        if self.app.viewport_manager is None:
            return None
        name = self.app.viewport_manager.next_name(preset)
        vp = self.app.viewport_manager.create_viewport(
            name=name, width=800, height=600, preset=preset,
        )
        
        panel = ViewportPanel(self.app, name, self.app.viewport_manager, preset=preset)
        self._viewport_panels.append(panel)
        return vp

    def close_all_viewports(self):
        if self.app.viewport_manager is None:
            return
        for name in list(self.app.viewport_manager.viewports.keys()):
            self.app.viewport_manager.remove_viewport(name)
        self._viewport_panels.clear()

    def _consume_plane_completion(self):
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

    # ------------------------------------------------------------------
    # DIALOGS
    # ------------------------------------------------------------------
    def open_open_dialog(self):
        self.file_dialog.open(
            mode="open", filters=[".cd4"], title="Proje Aç (.cd4)",
            initial_dir=os.getcwd(), on_select=self.app.load_project,
        )

    def open_save_dialog(self):
        self.file_dialog.open(
            mode="save", filters=[".cd4"], title="Projeyi Kaydet (.cd4)",
            initial_dir=os.getcwd(), default_name="model_projesi.cd4",
            on_select=self.app.save_project,
        )

    def on_project_changed(self) -> None:
        for name, entry in self.app.panels.items():
            panel = entry["instance"]
            if getattr(panel, "visible", False):
                self.prepare_panel(name, panel)
                if hasattr(panel, "_refresh_draft"):
                    panel._refresh_draft()

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
            self._toggle_row("Global Axis", "global_axis",
                            bool(eng.show.get("global_axis", True)))
            self._toggle_row("Local Axes", "local_axes",
                            bool(eng.scene and eng.scene.show_local_axes))

            imgui.separator()
            imgui.text_disabled("RENDER MODU")
            imgui.separator()
            mode = eng.renderer.get_render_mode() if eng.renderer else "shaded"
            for m, lbl in (
                ("shaded",    "Shaded"),
                ("simple",    "Simple"),
            ):
                if imgui.radio_button(lbl, mode == m):
                    self.command_queue.put(PC.SetRenderMode(m))
                    self.command_queue.put(PC.RefreshGeometry())

        return ("👁 View", _draw)


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

    def close_app(self) -> None:
        glfw.set_window_should_close(self.app.window.window, True)

    def open_s2k_import(self) -> None:
        self.open_panel("s2k_panel", mode="import")

    def open_s2k_export(self) -> None:
        self.open_panel("s2k_panel", mode="export")

    def start_plane_3pt(self) -> None:
        self.app.engine.plane_draw_mgr.start_3pt()

    def start_plane_2pt_z(self) -> None:
        self.app.engine.plane_draw_mgr.start_2pt_z()

    def open_plane_source_dialog(self) -> None:
        self.plane_source_dialog.open()

    def toggle_view_2d(self) -> None:
        self.app.toggle_2d()

    def shutdown(self) -> None:
        # Panel temizliği vb. gerekirse
        self._viewport_panels.clear()