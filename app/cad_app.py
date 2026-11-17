# app/cad_app.py
from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Dict

from app.commands.command_queue import CommandQueue
from core.units import UnitSystem, convert_project_units
from domain.definition import Section
from domain.project import Project, ProjectCatalog
from logging_config import CadLogger
from tools.wind_manager import WindManager

if TYPE_CHECKING:
    from core.engine import Engine
    from ui.ui_host import UIHost

logger = CadLogger.get(__name__)


class CadApp:
    def __init__(self, width: int = 1200, height: int = 800):
        self.width = width
        self.height = height
        self.engine: Engine | None = None
        self.viewport_manager = None
        self.command_queue = CommandQueue()

        self._ui_host: UIHost | None = None
        self.on_quit: Callable[[], None] | None = None

        self.current_project = Project()
        self.current_file_path: str | None = None
        self._model_text = "MODEL: NEW SCENE"
        self._catalog = ProjectCatalog(self.current_project)
        self.section_catalog: Dict[str, Section] = self._load_section_catalog()

        self.hover_visual_enabled = True
        self._show_only_ids: set[int] | None = None
        self._hidden_ids: set[int] | None = None

        self.panels: dict[str, dict] = {}
        self._panels_by_category: dict[str, list[str]] = {}

        from app.commands.registry import build_registry
        self._command_registry = build_registry()
        self.wind_manager = WindManager(self)


        

    def _load_section_catalog(self) -> Dict[str, Section]:
        from data.section_catalog import load_catalog_from_dir
        data_dir = Path(__file__).parent.parent / "data"
        catalog = load_catalog_from_dir(data_dir)
        logger.info("[CadApp] Kesit kataloğu: %d kesit", len(catalog))
        return catalog

    def init_engine(self) -> None:
        from app.input_bindings import build_bindings
        from core.engine import Engine
        from viewport.viewport_manager import ViewportManager

        w = max(1, self.width)
        h = max(1, self.height)

        self.engine = Engine(w, h, self.command_queue)
        self.engine.init_gl()

        for key, action in build_bindings(self.command_queue).items():
            if isinstance(key, tuple):
                self.engine.input.bind(key[0], key[1], action)
            else:
                self.engine.input.bind(key, 0, action)

        self.viewport_manager = ViewportManager(self.engine)
        self.engine.viewport_manager = self.viewport_manager

    def attach_ui(self, ui_host: UIHost) -> None:
        self._ui_host = ui_host
        if self.engine is not None:
            self._ui_host.on_engine_ready()

    @property
    def ui(self) -> UIHost | None:
        return self._ui_host

    def resize(self, width: int, height: int) -> None:
        self.width = max(1, width)
        self.height = max(1, height)
        if self.engine is not None:
            self.engine.resize(self.width, self.height)

    def tick(self, dt: float) -> None:
        if self.engine is None:
            return
        self._drain_commands()
        self.wind_manager.process_queue()
        self._update_scene_if_dirty()
        if self.engine.pending_pick_check:
            self.engine.check_pick_result()

    def request_quit(self) -> None:
        if self.on_quit is not None:
            self.on_quit()

    def shutdown(self) -> None:
        if self._ui_host is not None:
            self._ui_host.shutdown()
            self._ui_host = None
        if self.engine is not None:
            self.engine.renderer.cleanup()
            self.engine = None

    def new_project(self) -> None:
        self.set_project(Project())
        self.current_file_path = None
        self._model_text = "MODEL: YENİ SAHNE"

    def load_project(self, path: str) -> None:
        self.set_project(Project.load(path))
        if self.engine is not None:
            self.engine.fit_view()
            self.engine.sel_mgr.clear()
        self.current_file_path = path
        self._model_text = f"MODEL: {os.path.basename(path)}"

    def save_project(self, path: str) -> None:
        self.current_project.save(path)
        self.current_file_path = path
        self._model_text = f"MODEL: {os.path.basename(path)}"

    def quick_save(self) -> None:
        if self.current_file_path:
            self.save_project(self.current_file_path)
        elif self._ui_host is not None:
            self._ui_host.open_save_dialog()

    def set_project(self, project: Project) -> None:
        if self._ui_host is not None:
            self._ui_host.reset_all()

        self.current_project = project
        self.wind_manager.wind_state()
        self._catalog = ProjectCatalog(project)

        if self.engine is None or project.scene is None:
            return

        self.engine.set_scene(project)
        self.engine.update_geo(project)

        if self.engine.grid and project.scene.grid:
            self.engine.grid.set_grid(project.scene.grid)
            self.engine.grid.mark_dirty()

        if self.engine.sel_mgr:
            self.engine.sel_mgr.clear()

        bounds = self.engine._combined_bounds()
        if bounds is not None and self.viewport_manager is not None:
            for vp in self.viewport_manager.viewports.values():
                vp.camera.update_bounds(bounds.center, bounds.size)
                vp.camera.focus_on_model()

        if self._ui_host is not None:
            self._ui_host.on_project_changed()

        

    def on_s2k_import_complete(self, project: Project) -> None:
        self.set_project(project)
        self._model_text = f"MODEL: S2K import ({len(project.math_model.frames)} çubuk)"

    def on_selection_changed(self, selected: list) -> None:
        if self.engine and self.engine.renderer:
            self.engine.renderer.update_sel()
        if self._ui_host is not None:
            self._ui_host.on_selection_changed(selected)

    def on_hover_changed(self, element) -> None:
        pass

    def get_selected(self) -> list:
        if self.engine and self.engine.sel_mgr:
            return list(self.engine.sel_mgr.get_selected())
        return []

    def set_unit_system(self, unit_system: UnitSystem) -> None:
        project = self.current_project
        if project.unit_system == unit_system:
            return

        convert_project_units(project, unit_system, reason="ui")
        eng = self.engine
        if eng is not None:
            if eng.grid and project.grid:
                eng.grid.set_grid(project.grid)
                eng.grid.mark_dirty()
            if eng.math_model and eng.renderer:
                eng.math_model.mark_dirty()
                eng.renderer.update_geo(eng.math_model)
            if eng.scene:
                eng.scene.refresh_bounds()
            if eng.math_model:
                eng.math_model.refresh_bounds()
                eng.fit_view()

        if self._ui_host is not None:
            self._ui_host.on_unit_changed()

    def wind_state(self) -> dict:
        return self.wind_manager.wind_state()

    def run_wind(self) -> None:
        self.wind_manager.run_wind()

    def select_wind_direction(self, w_dir) -> None:
        self.wind_manager.select_wind_direction(w_dir)

    def on_plane_selected(self, plane) -> None:
        project = self.current_project
        if project is None:
            return

        if plane is None:
            project.deactivate_plane()
        else:
            project.activate_plane(plane)

        eng = self.engine
        if eng is None:
            return

        if eng.interaction_renderer:
            eng.interaction_renderer.preview_plane = None
        if eng.renderer is not None and eng.math_model is not None:
            eng.update_geo(project)
        if eng.sel_mgr:
            eng.sel_mgr.clear()

    def toggle_2d(self) -> None:
        eng = self.engine
        if eng is None or eng.renderer is None:
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

        if plane is not None:
            eng.enter_plane_2d(plane)

    def get_loads_visible(self) -> bool:
        pres = self.engine.presentation_renderer if self.engine else None
        if pres and getattr(pres, "loads", None):
            return bool(pres.loads.enabled)
        return False

    def set_loads_visible(self, enabled: bool) -> None:
        pres = self.engine.presentation_renderer if self.engine else None
        if pres and getattr(pres, "loads", None):
            pres.loads.enabled = bool(enabled)
            if enabled and self.engine.math_model:
                pres.update_loads(self.engine.math_model, camera_scale=1.0, scene_size=1.0)

    def show_entire_model(self) -> None:
        project = self.current_project
        eng = self.engine

        if project is not None:
            project.deactivate_plane()

        if eng is not None:
            self._show_only_ids = None
            self._hidden_ids = None
            if eng.math_model:
                eng.math_model._render_filter = None
                for element in eng.math_model.all_elements.values():
                    if hasattr(element, "is_visible"):
                        element.is_visible = True
                    elif hasattr(element, "visible"):
                        element.visible = True
            if project is not None:
                eng.update_geo(project)
            eng.fit_view()

    def convert_frames_to_links(self, link_prop_name: str = "DefaultLink", delete_original: bool = True) -> None:
        from tools import frame_to_link

        eng = self.engine
        if eng is None or eng.math_model is None:
            return

        scn = eng.math_model
        frames = [e for e in scn.get_selected() if e.__class__.__name__ == "Frame"]
        if not frames:
            return

        report = frame_to_link.convert_frames_to_links(
            scene=scn,
            project=self.current_project,
            frames=frames,
            link_prop_name=link_prop_name,
            delete_original=delete_original,
        )

        if self._show_only_ids is not None:
            removed = {f.unique_id for f in frames}
            self._show_only_ids -= removed
            self._show_only_ids.update(l.unique_id for l in report["new_links"])
            scn._render_filter = self._show_only_ids

        if eng.sel_mgr:
            eng.sel_mgr.clear()

    def _active_working_plane(self):
        project = self.current_project
        if project is None or project.scene is None:
            return None
        return project.active_plane

    def _update_scene_if_dirty(self) -> None:
        model = self.engine.math_model if self.engine else None
        if model and model.is_dirty():
            self.engine.renderer.update_geo(model)
            model.clear_dirty()

    def _drain_commands(self) -> None:
        cmds = self.command_queue.drain()
        if not cmds:
            return

        geometry_dirty = False
        project_dirty = False

        for cmd in cmds:
            result = self._command_registry.dispatch(self, cmd)
            if self._ui_host is not None and result.message:
                self._ui_host.log_command_result(result.message, level=result.level)
            if not result.handled:
                logger.warning("[cmd] bilinmeyen: %r (%s)", cmd, type(cmd).__qualname__)
                continue
            if result.followup is not None:
                self.command_queue.put(result.followup)
            geometry_dirty = geometry_dirty or result.geometry_dirty
            project_dirty = project_dirty or result.project_dirty

        if geometry_dirty and self.engine and self.current_project:
            self.engine.update_geo(self.current_project)

        if project_dirty and self._ui_host is not None:
            self._ui_host.on_project_changed()

        if result.message and self._ui_host is not None:
            self._ui_host.log_command_result(result.message, result.level)
        if result.followup is not None:
            self.command_queue.put(result.followup)
