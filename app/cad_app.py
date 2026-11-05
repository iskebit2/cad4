# app/cad_app.py
from __future__ import annotations

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
from app.input_router import InputRouter
from app.panel_registry import PANEL_SPECS

from app.toolbar import Toolbar
from core.gl_engine import Engine
from core.plane_draw_manager import PlaneCreationTool
from domain.definition import Section
from domain.project import Project
from inspector import InspectorWindow
from inspector.catalog_project import ProjectCatalog


from inspector.topbar import TopBar
from logging_config import CadLogger

logger = CadLogger.get(__name__)


class CadApp:

    def __init__(self, window: CadWindow):
        self.window = window
        self.engine: Engine | None = None
        self.initialized = False

        self.current_project = Project()
        self.current_file_path: str | None = None
        self._model_text = "MODEL: YENİ SAHNE"
        self._catalog = ProjectCatalog(self.current_project)
        self.section_catalog: dict[str, Section] = {}
        self.hover_visual_enabled = True
        self._show_only_ids: set[int] | None = None
        self.inspector: InspectorWindow | None = None
        self._io = None

        self.panels: dict[str, dict] = {}
        self._panels_by_category: dict[str, list[str]] = {}
        self._shortcut_map: dict[str, str] = {}
        self._key_shortcuts: dict[int, tuple] = {}

        self.actions = AppActions(self)
        self.input = InputRouter(self)

        self._init_registry()
        self._init_shortcuts()

        self.toolbar = Toolbar(
            commands=self._build_toolbar_commands(),
            panel_states=self._build_panel_states(),
        )

        self._load_section_catalog()
        self.input.wire_window(window)
        window.on_resize = self._on_resize

        
        self._wire_panel_hooks()

        

    # ------------------------------------------------------------------
    def _init_registry(self) -> None:
        for spec in PANEL_SPECS:
            if spec.get("kind", "panel") != "panel":
                continue
            name = spec["name"]
            try:
                inst = spec["cls"]()
            except Exception:
                logger.exception("[Registry] %s", name)
                continue
            inst.app = self
            self.panels[name] = {
                "instance": inst,
                "title": spec["title"],
                "category": spec["category"],
                "quick": spec.get("quick", False),
                "shortcut": spec.get("shortcut"),
                "menu_label": spec.get("menu_label"),
                "icon": spec.get("icon"),
                "context": spec.get("context", []),
            }
            self._panels_by_category.setdefault(spec["category"], []).append(name)
            if spec.get("shortcut"):
                self._shortcut_map[spec["shortcut"]] = name
            setattr(self, name, inst)

    def _init_shortcuts(self) -> None:
        for shortcut, panel_name in self._shortcut_map.items():
            parts = shortcut.split("+")
            key_name = parts[-1]
            mods = {p.upper() for p in parts[:-1]}
            glfw_key = getattr(glfw, f"KEY_{key_name}", None)
            if glfw_key is None:
                continue
            self._key_shortcuts[glfw_key] = (
                panel_name, "CTRL" in mods, "SHIFT" in mods,
            )

    def _wire_panel_hooks(self) -> None:
        fl = self.panels.get("assign_frame_distributed_load", {}).get("instance")
        if fl:
            fl.on_apply = self.input.apply_frame_load

        at = self.panels.get("area_to_frame", {}).get("instance")
        if at:
            at.on_transfer_complete = self.input.on_area_transfer_complete

        rs = self.panels.get("render_settings", {}).get("instance")
        if rs:
            rs.get_loads_visible = self.input.get_loads_visible
            rs.set_loads_visible = self.input.set_loads_visible

        s2k = self.panels.get("s2k_panel", {}).get("instance")
        if s2k:
            s2k.on_import_complete = self.actions.on_s2k_import_complete
            s2k.get_project = lambda: self.current_project
            s2k.get_selected_elements = self._selected

        ins = self.panels.get("inspector", {}).get("instance")
        if ins:
            ins.app = self
            ins.set_catalog(self._catalog)

        wind = self.panels.get("wind", {}).get("instance")
        if wind:
            wind.on_run_analysis = self.actions.run_wind
            wind.on_select_direction = self.actions.select_wind_direction

    # ------------------------------------------------------------------
    def frame(self, dt: float) -> None:
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
        self.input.process_pending()
        self.actions.process_wind_queue()
        self._update_scene_if_dirty()
        self._render_scene(dt)
        self._draw_panels()
        self.input.draw_hud()
        self.input.draw_pdm_hud()
        self._consume_plane_completion()

        if self.engine and self.engine.pending_pick_check:
            self.engine.check_pick_result()

    # ------------------------------------------------------------------
    def _ensure_engine(self) -> None:
        if self.initialized:
            return
        w, h = self.window.fb_width, self.window.fb_height
        if w <= 1 or h <= 1:
            return
        try:
            self.engine = Engine(w, h)
            self.engine.init_gl()
            self.engine.set_working_plane_provider(self._active_working_plane)
            self.engine.on_hover_changed_callback = self.actions.on_hover_changed
            self.engine.sel_mgr.on_selection_changed = self.actions.on_selection_changed
            self.engine.plane_draw_mgr = PlaneCreationTool(self.engine)
            self.initialized = True
            if self.current_project:
                self.set_project(self.current_project)
        except Exception:
            logger.exception("[Init] Engine başlatma hatası")
            self.initialized = True

    def _update_scene_if_dirty(self) -> None:
        scn = self.engine.scene if self.engine else None
        if scn and hasattr(scn, "is_dirty") and scn.is_dirty():
            if self.engine.renderer:
                self.engine.renderer.update_geo(scn)
            scn.clear_dirty()

    def _draw_panels(self) -> None:
        for name, entry in self.panels.items():
            panel = entry["instance"]
            if not getattr(panel, "visible", False):
                continue
            try:
                panel.draw()
            except Exception:
                logger.exception("[Panel] %s draw", name)
                try:
                    panel.close()
                except Exception:
                    pass

    def _render_scene(self, dt: float) -> None:
        w, h = self.window.fb_width, self.window.fb_height
        glViewport(0, 0, w, h)
        try:
            glEnable(GL_DEPTH_TEST)
            glClearColor(0.08, 0.10, 0.16, 1.0)
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            if self.engine:
                self.engine.render(self.engine.cam)
        finally:
            glViewport(0, 0, w, h)
            glUseProgram(0)
            glBindVertexArray(0)
            glBindBuffer(GL_ARRAY_BUFFER, 0)
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)
            glDisable(GL_DEPTH_TEST)
            glDisable(GL_CULL_FACE)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def _consume_plane_completion(self) -> None:
        eng = self.engine
        if not eng:
            return
        pdm = getattr(eng, "plane_draw_mgr", None)
        if pdm is None or pdm.is_active:
            return
        plane = getattr(pdm, "completed_plane", None)
        if plane is None:
            return
        pdm.completed_plane = None
        self._on_plane_selected(plane)
        if eng.renderer and eng.renderer.projection != "plane_2d":
            self._toggle_2d()

    # ------------------------------------------------------------------
    def _toggle_2d(self) -> None:
        if not self.engine or not self.engine.renderer:
            return
        r = self.engine.renderer
        if r.projection != "plane_2d":
            pdm = getattr(self.engine, "plane_draw_mgr", None)
            if pdm is not None and pdm.is_active:
                pdm.cancel()
        return r.toggle_projection()

    def _active_working_plane(self):
        project = self.current_project
        if project is None or project.scene is None:
            return None
        return project.active_plane

    def _on_plane_selected(self, plane) -> None:
        project = self.current_project
        if project is None:
            return
        if plane is None:
            project.deactivate_plane()
        else:
            project.activate_plane(plane)

        if self.engine is None:
            return
        scn = self.engine.scene
        if self.engine.renderer is not None and scn is not None:
            self.engine.renderer.update_geo(scn)
        if self.engine.sel_mgr:
            self.engine.sel_mgr.clear()

    def _selected(self):
        if self.engine and self.engine.scene:
            return self.engine.scene.get_selected()
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
            "draw_line": lambda: self.input.toggle_draw("line"),
            "draw_poly": lambda: self.input.toggle_draw("poly"),
            "draw_plane": self.input.toggle_plane,
            "render_mode": lambda: self.engine.renderer.toggle_render_mode() if self.engine else None,
            "toggle_loads_vis": self.input.toggle_loads,
            "local_axes": self.input.toggle_local_axes,
            "show_only": self.input.toggle_show_only,
            "convert_to_link": lambda: self.input.convert_frames_to_links("DefaultLink"),
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
            "draw_plane": lambda: bool(self.engine and getattr(self.engine, "plane_draw_mgr", None) and self.engine.plane_draw_mgr.is_active),
            "local_axes": lambda: bool(self.engine and self.engine.scene and self.engine.scene.show_local_axes),
            "show_loads": self.input.get_loads_visible,
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

        if not self.engine:
            return
        if project.scene is None:
            return

        self.engine.set_scene(project)

        if self.inspector:
            self.inspector.set_catalog(self._catalog)
            self.inspector.set_scene(project.scene)

        self.engine.update_geo(project)

        if self.engine.grid and project.grid:
            self.engine.grid.set_grid(project.grid)
            self.engine.grid.mark_dirty()

        if self.engine.sel_mgr:
            self.engine.sel_mgr.clear()

        pm = self.panels.get("plane_manager", {}).get("instance")
        if pm is not None:
            pm._selected_name = None
            pm._form_open = False
            pm._editing_plane = None
            if hasattr(pm, "_clear_preview"):
                pm._clear_preview()

    def _on_update_geo(self) -> None:
        if self.engine and self.current_project:
            self.engine.update_geo(self.current_project)

    def _load_section_catalog(self) -> None:
        from data.section_catalog import load_catalog_from_dir

        data_dir = Path(__file__).parent.parent / "data"
        try:
            self.section_catalog = load_catalog_from_dir(data_dir)
        except Exception:
            logger.exception("[CadApp] Katalog yüklenemedi")
            self.section_catalog = {}

    def _on_resize(self, w, h) -> None:
        if self.engine:
            self.engine.resize(max(1, w), max(1, h))

    def shutdown(self) -> None:
        pass