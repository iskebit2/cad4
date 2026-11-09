# app/cad_app.py

from __future__ import annotations
import time

from pathlib import Path

import glfw
from imgui_bundle import imgui
from OpenGL.GL import (
    GL_ARRAY_BUFFER, GL_BLEND, GL_COLOR_BUFFER_BIT, GL_CULL_FACE,
    GL_DEPTH_BUFFER_BIT, GL_DEPTH_TEST, GL_ELEMENT_ARRAY_BUFFER,
    GL_ONE_MINUS_SRC_ALPHA, GL_SRC_ALPHA,
    glBindBuffer, glBindVertexArray, glBlendFunc, glClear, glClearColor,
    glDisable, glEnable, glUseProgram, glViewport,
)

from app.app_actions import AppActions
from app.cad_window import CadWindow
from app.input_bindings import build_bindings
from app.panel_registry import PANEL_SPECS, PanelSpec
from app.toolbar import Toolbar
from core.gl_engine import Engine
from domain.project import Project
from inspector import InspectorWindow
from inspector.catalog_project import ProjectCatalog
from app.debug_panel import DebugPanel

from logging_config import CadLogger
logger = CadLogger.get(__name__)


class CadApp:

    def __init__(self, window: CadWindow):
        self.window = window
        self.engine: Engine | None = None
        self.initialized = False

        self.debug_panel = DebugPanel(self)

        self.current_project = Project()
        self.current_file_path: str | None = None
        self._model_text = "MODEL: NEW SCENE"
        self._catalog = ProjectCatalog(self.current_project)
        self.hover_visual_enabled = True
        self._show_only_ids: set[int] | None = None
        self.inspector: InspectorWindow | None = None
        self._io = None

        self.panels: dict[str, dict] = {}
        self._panels_by_category: dict[str, list[str]] = {}

        self.actions = AppActions(self)

        self._init_registry()

        self.toolbar = Toolbar(
            commands=self._build_toolbar_commands(),
            panel_states=self._build_panel_states(),
        )

        self._wire_panel_hooks()
        self._wire_window()

    # ------------------------------------------------------------------
    def _init_registry(self) -> None:
        for spec in PANEL_SPECS:
            if spec.kind != "panel" or spec.cls is None:
                continue
            inst = spec.cls()
            inst.app = self
            self.panels[spec.name] = {
                "instance": inst,
                "title": spec.title,
                "category": spec.category,
                "quick": spec.quick,
                "shortcut": spec.shortcut,
                "menu_label": spec.menu_label,
                "icon": spec.icon,
                "context": spec.context,
            }
            self._panels_by_category.setdefault(spec.category, []).append(spec.name)
            setattr(self, spec.name, inst)

    def _wire_panel_hooks(self) -> None:
        fl = self.panels.get("assign_frame_distributed_load", {}).get("instance")
        if fl:
            fl.on_apply = self.actions.apply_frame_load

        at = self.panels.get("area_to_frame", {}).get("instance")
        if at:
            at.on_transfer_complete = self.actions.on_area_transfer_complete

        rs = self.panels.get("render_settings", {}).get("instance")
        if rs:
            rs.get_loads_visible = self.actions.get_loads_visible
            rs.set_loads_visible = self.actions.set_loads_visible

        s2k = self.panels.get("s2k_panel", {}).get("instance")
        if s2k:
            s2k.on_import_complete = self.actions.on_s2k_import_complete
            s2k.get_project = lambda: self.current_project
            s2k.get_selected_elements = self._selected

        ins = self.panels.get("inspector", {}).get("instance")
        if ins:
            ins.app = self
            ins.set_catalog(self._catalog)

        wind = self.panels.get("wind_analysis", {}).get("instance")
        if wind:
            wind.on_run_analysis = self.actions.run_wind
            wind.on_select_direction = self.actions.select_wind_direction

    def _wire_window(self) -> None:
        self.window.on_resize = self._on_resize
        self.window.on_key = self._on_key
        self.window.on_mouse_button = self._on_mouse_button
        self.window.on_mouse_move = self._on_mouse_move
        self.window.on_scroll = self._on_scroll

    # ------------------------------------------------------------------
    def _on_resize(self, w, h) -> None:
        if self.engine:
            self.engine.resize(max(1, w), max(1, h))

    def _on_key(self, key, scancode, action, mods) -> None:
        
        if self.engine:
            self.engine.input.on_key(key, action, mods)

    def _on_mouse_button(self, button, action, mods) -> None:
        if self.engine:
            self.engine.input.on_mouse_button(button, action, mods)

    def _on_mouse_move(self, x, y) -> None:
        if self.engine:
            self.engine.input.on_mouse_move(x, y)

    def _on_scroll(self, xoff, yoff):
        if imgui.get_io().want_capture_mouse:
            return
        if imgui.is_window_hovered(imgui.HoveredFlags_.any_window):
            return
        if self.engine:
            self.engine.input.on_scroll(yoff)

    # ------------------------------------------------------------------
    def frame(self, dt: float) -> None:
        t_start = time.perf_counter()
        self._ensure_engine()
        if not self.initialized:
            return
        if self._io is None:
            self._io = imgui.get_io()

        self.toolbar.draw(
            model_text=self._model_text,
            current_unit=self.current_project.unit_system if self.current_project else None,
            project=self.current_project,
        )
        self.actions.draw_dialog()
        self.actions.process_wind_queue()
        self._update_scene_if_dirty()
        self._render_scene(dt)
        t_render = time.perf_counter()
        self._draw_panels()
        self.debug_panel.draw()

        self._consume_plane_completion()

        if self.engine and self.engine.pending_pick_check:
            self.engine.check_pick_result()

        if time.perf_counter() - t_start > 0.033:
            logger.debug("[CadApp.frame] SLOW: %.1f ms (render: %.1f)", (time.perf_counter() - t_start) * 1000, (t_render - t_start) * 1000)

    def _ensure_engine(self) -> None:
        if self.initialized:
            return
        w, h = self.window.fb_width, self.window.fb_height
        if w <= 1 or h <= 1:
            return

        self.engine = Engine(w, h)
        self.engine.init_gl()
        self.engine.set_working_plane_provider(self._active_working_plane)
        self.engine.on_hover_changed_callback = self.actions.on_hover_changed
        self.engine.sel_mgr.on_selection_changed = self.actions.on_selection_changed
        self.engine.set_app(self)

        

        from app.input_bindings import build_bindings
        bindings = build_bindings(self)
        
        for key, action in bindings.items():
            if isinstance(key, tuple):
                k, m = key
                self.engine.input.bind(k, m, action)
            else:
                self.engine.input.bind(key, 0, action)

        
        

        
        for key, action in build_bindings(self).items():
            if isinstance(key, tuple):
                k, m = key
                self.engine.input.bind(k, m, action)
            else:
                self.engine.input.bind(key, 0, action)

        self.initialized = True
        if self.current_project:
            self.set_project(self.current_project)

    def _update_scene_if_dirty(self) -> None:
        model = self.engine.math_model if self.engine else None
        if model and model.is_dirty():
            self.engine.renderer.update_geo(model)
            model.clear_dirty()

    def _draw_panels(self) -> None:
        for entry in self.panels.values():
            panel = entry["instance"]
            if getattr(panel, "visible", False):
                panel.draw()

    def _consume_plane_completion(self):
        pdm = self.engine.plane_draw_mgr if self.engine else None
        if pdm is None or pdm.is_active or pdm.completed_plane is None:
            return
        plane = pdm.completed_plane
        pdm.completed_plane = None

        pm = self.panels.get("plane_manager", {}).get("instance")
        if pm is not None:
            pm._selected_name = plane.name
            pm.visible = True

        if self.engine and self.current_project:
            self.engine.update_geo(self.current_project)

    # ------------------------------------------------------------------
    def _render_scene(self, dt: float) -> None:
        w, h = self.window.fb_width, self.window.fb_height
        glViewport(0, 0, w, h)
        glEnable(GL_DEPTH_TEST)
        glClearColor(0.08, 0.10, 0.16, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        if self.engine:
            self.engine.render(self.engine.cam)

        glViewport(0, 0, w, h)
        glUseProgram(0)
        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_CULL_FACE)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def _toggle_2d(self) -> None:
        if not (self.engine and self.engine.renderer):
            return
        r = self.engine.renderer
        if r.projection != "plane_2d" and self.engine.plane_draw_mgr.is_active:
            self.engine.plane_draw_mgr.cancel()
        r.toggle_projection()

    def _active_working_plane(self):
        project = self.current_project
        if project is None or project.scene is None:
            return None
        return project.active_plane

    def _selected(self):
        if self.engine and self.engine.sel_mgr:
            return self.engine.sel_mgr.get_selected()
        return []

    # ------------------------------------------------------------------
    def _build_toolbar_commands(self) -> dict:
        cmds = {
            "new_project": self.actions.new_project,
            "open": self.actions.open_dialog,
            "save": self.actions.quick_save,
            "save_as": self.actions.save_as_dialog,
            "close_app": lambda: glfw.set_window_should_close(self.window.window, True),
            "s2k_import": self.actions.s2k_import,
            "s2k_export": self.actions.s2k_export,
            "draw_line": lambda: self.actions.toggle_draw("line"),
            "draw_poly": lambda: self.actions.toggle_draw("poly"),
            "draw_plane": self.actions.toggle_plane,
            "render_mode": lambda: self.engine.renderer.toggle_render_mode() if self.engine else None,
            "toggle_loads_vis": self.actions.toggle_loads,
            "local_axes": self.actions.toggle_local_axes,
            "show_only": self.actions.toggle_show_only,
            "convert_to_link": lambda: self.actions.convert_frames_to_links("DefaultLink"),
            "on_unit_change": self.actions.set_unit_system,
            "toggle_view_2d": self._toggle_2d,
        }
        for name in self.panels:
            cmds[name] = (lambda n=name: self.actions.toggle_panel(n))
        return cmds

    def _build_panel_states(self) -> dict:
        states = {
            "draw_line": lambda: bool(self.engine and self.engine.draw_mgr and self.engine.draw_mgr.is_active),
            "draw_poly": lambda: bool(self.engine and self.engine.draw_mgr and self.engine.draw_mgr.is_active),
            "draw_plane": lambda: bool(self.engine and self.engine.plane_draw_mgr and self.engine.plane_draw_mgr.is_active),
            "local_axes": lambda: bool(self.engine and self.engine.scene and self.engine.scene.show_local_axes),
            "show_loads": self.actions.get_loads_visible,
            "show_only": lambda: self._show_only_ids is not None,
            "toggle_view_2d": lambda: bool(self.engine and self.engine.renderer and self.engine.renderer.projection == "plane_2d"),
        }
        for name, entry in self.panels.items():
            inst = entry["instance"]
            states[name] = (lambda i=inst: getattr(i, "visible", False))
        return states

    # ------------------------------------------------------------------
    def set_project(self, project: Project) -> None:
        self.current_project = project
        self.actions.wind_state()
        self._catalog = ProjectCatalog(project)

        if not self.engine or project.scene is None:
            return

        self.engine.set_scene(project)

        if self.inspector:
            self.inspector.set_catalog(self._catalog)
            self.inspector.set_project(project)

        self.engine.update_geo(project)

        if self.engine.grid and project.scene.grid:
            self.engine.grid.set_grid(project.scene.grid)
            self.engine.grid.mark_dirty()

        if self.engine.sel_mgr:
            self.engine.sel_mgr.clear()

        pm = self.panels.get("plane_manager", {}).get("instance")
        if pm is not None:
            pm.reset()

    def _toggle_2d(self) -> None:
        eng = self.engine
        if not eng or not eng.renderer:
            return
        if eng.plane_draw_mgr.is_active:
            eng.plane_draw_mgr.cancel()

        if eng.renderer.projection == "plane_2d":
            eng.exit_plane_2d()
            return

        project = self.current_project
        plane = project.active_plane if project else None
        if plane is None:
            plane = eng.default_xy_plane()
            if plane is not None and project is not None:
                project.activate_plane(plane)

        if plane is None:
            return
        eng.enter_plane_2d(plane)
        
    def shutdown(self) -> None:
        pass