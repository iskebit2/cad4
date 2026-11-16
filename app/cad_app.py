# app/cad_app.py
from __future__ import annotations

import os
import queue
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Dict

import numpy as np

from core.units import UnitSystem, convert_project_units
from domain.definition import Section, WindDirectionResult
from domain.project import Project
from inspector.catalog_project import ProjectCatalog
from logging_config import CadLogger

if TYPE_CHECKING:
    from core.gl_engine import Engine
    from app.cad_window import CadWindow
    from ui.ui_host import UIHost

logger = CadLogger.get(__name__)


class CadApp:
    def __init__(self, window: CadWindow):
        self.window = window
        self.engine: Engine | None = None
        self.initialized = False
        self._ui_host: UIHost | None = None

        self.current_project = Project()
        self.current_file_path: str | None = None
        self._model_text = "MODEL: NEW SCENE"
        self._catalog = ProjectCatalog(self.current_project)
        self.section_catalog: Dict[str, Section] = self._load_section_catalog()
        self.hover_visual_enabled = True
        self._show_only_ids: set[int] | None = None
        self._hidden_ids: set[int] | None = None

        self._wind_queue: queue.Queue = queue.Queue()
        self._wind_generation = 0
        self._wind_status = ""

        self.panels: dict[str, dict] = {}
        self._panels_by_category: dict[str, list[str]] = {}
        self.viewport_manager = None
        self.command_queue = None

        from app.commands.registry import build_registry
        self._command_registry = build_registry()

    def _load_section_catalog(self) -> Dict[str, Section]:
        from data.section_catalog import load_catalog_from_dir
        data_dir = Path(__file__).parent.parent / "data"
        catalog = load_catalog_from_dir(data_dir)
        logger.info("[CadApp] Kesit kataloğu: %d kesit", len(catalog))
        return catalog

    def attach_ui(self, ui_host: "UIHost") -> None:
        self._ui_host = ui_host
        self.command_queue = ui_host.command_queue

    @property
    def ui(self) -> "UIHost | None":
        return self._ui_host

    def tick(self, dt: float) -> None:
        self._ensure_engine()
        if not self.initialized:
            return
        self._drain_commands()
        self.process_wind_queue()
        self._update_scene_if_dirty()
        if self.engine and self.engine.pending_pick_check:
            self.engine.check_pick_result()

    def _ensure_engine(self) -> None:
        if self.initialized:
            return
        w, h = self.window.fb_width, self.window.fb_height
        if w <= 1 or h <= 1:
            return

        from core.gl_engine import Engine
        self.engine = Engine(w, h)
        self.engine.init_gl()
        self.engine.set_working_plane_provider(self._active_working_plane)
        self.engine.on_hover_changed_callback = self.on_hover_changed
        self.engine.sel_mgr.on_selection_changed = self.on_selection_changed
        self.engine.set_app(self)

        from app.input_bindings import build_bindings
        for key, action in build_bindings(self).items():
            if isinstance(key, tuple):
                k, m = key
                self.engine.input.bind(k, m, action)
            else:
                self.engine.input.bind(key, 0, action)

        from core.viewport_manager import ViewportManager
        self.viewport_manager = ViewportManager(self.engine)
        self.engine.viewport_manager = self.viewport_manager
        self.viewport_manager.create_viewport(name="iso", width=1200, height=800, preset="iso")

        self.initialized = True
        if self.current_project:
            self.set_project(self.current_project)

        if self._ui_host is not None:
            self._ui_host.on_engine_ready()

    def shutdown(self) -> None:
        if self._ui_host is not None:
            self._ui_host.shutdown()
        if self.engine is not None:
            self.engine.renderer.cleanup()
        self.engine = None

    def new_project(self) -> None:
        self.set_project(Project())
        self.current_file_path = None
        self._model_text = "MODEL: YENİ SAHNE"

    def load_project(self, path: str) -> None:
        self.set_project(Project.load(path))
        if self.engine:
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
        elif self._ui_host:
            self._ui_host.open_save_dialog()

    def set_project(self, project: Project) -> None:
        self.current_project = project
        self.wind_state()
        self._catalog = ProjectCatalog(project)
        if not self.engine or project.scene is None:
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
        if self._ui_host:
            self._ui_host.on_project_changed()

    def on_s2k_import_complete(self, project: Project) -> None:
        self.set_project(project)
        self._model_text = f"MODEL: S2K import ({len(project.math_model.frames)} çubuk)"

    def on_selection_changed(self, selected: list) -> None:
        if self.engine and self.engine.renderer:
            self.engine.renderer.update_sel()
        if self._ui_host:
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
        if eng and eng.grid and project.grid:
            eng.grid.set_grid(project.grid)
            eng.grid.mark_dirty()
        if eng and eng.math_model and eng.renderer:
            eng.math_model.mark_dirty()
            eng.renderer.update_geo(eng.math_model)
        if eng and eng.scene:
            eng.scene.refresh_bounds()
        if eng and eng.math_model:
            eng.math_model.refresh_bounds()
            eng.fit_view()
        if self._ui_host:
            self._ui_host.on_unit_changed()

    def wind_state(self) -> dict:
        analysis = self.current_project.analysis
        wind = analysis.wind
        if not isinstance(wind, dict):
            wind = {}
            analysis.wind = wind
        directions = wind.get("directions")
        if not isinstance(directions, dict):
            directions = {}
            wind["directions"] = directions
        if not directions:
            directions["01"] = WindDirectionResult(w_dir=(1.0, 0.0, 0.0))
        if wind.get("active_direction") is None:
            first = next(iter(directions.values()))
            if isinstance(first, dict):
                wind["active_direction"] = tuple(first.get("w_dir", (1.0, 0.0, 0.0)))
            else:
                wind["active_direction"] = tuple(getattr(first, "w_dir", (1.0, 0.0, 0.0)))
        return wind

    def run_wind(self) -> None:
        wind = self.wind_state()
        active = wind.get("active_direction")
        if active is None:
            active = next(iter(wind["directions"].values())).w_dir
        direction = tuple(float(v) for v in active)
        key = self._wind_key(direction)
        self._start_wind_analysis(key, direction)

    def select_wind_direction(self, w_dir) -> None:
        direction = tuple(float(v) for v in w_dir)
        if len(direction) != 3 or not np.isfinite(direction).all():
            self._wind_status = "Geçersiz rüzgar yönü."
            return
        if np.linalg.norm(direction[:2]) < 1e-12:
            self._wind_status = "Geçersiz rüzgar yönü."
            return
        wind = self.wind_state()
        wind["active_direction"] = direction
        key = self._wind_key(direction)
        record = wind["directions"][key]
        if hasattr(record, "w_dir"):
            record.w_dir = direction
        elif isinstance(record, dict):
            record["w_dir"] = direction
        self._start_wind_analysis(key, direction)

    def _wind_key(self, w_dir) -> str:
        directions = self.wind_state()["directions"]
        for key, record in directions.items():
            candidate = getattr(record, "w_dir", None)
            if candidate is None and isinstance(record, dict):
                candidate = record.get("w_dir")
            if candidate is not None and np.allclose(candidate, w_dir, atol=1e-8):
                return str(key)
        numeric = [int(k) for k in directions if str(k).isdigit()]
        key = f"{max(numeric, default=0) + 1:02d}"
        directions[key] = WindDirectionResult(w_dir=tuple(w_dir))
        return key

    def _start_wind_analysis(self, direction_key: str, direction) -> None:
        from tools.wind_scene_adapter import WindSceneAdapter
        project = self.current_project
        eng = self.engine
        scene = eng.math_model if eng else project.math_model
        if scene is None:
            return
        points, polygons, wind_config = WindSceneAdapter.build_inputs(project)
        self._wind_generation += 1
        generation = self._wind_generation
        self._wind_status = "Rüzgar analizi çalışıyor..."

        def analyze() -> None:
            zones, engine_data = WindSceneAdapter.analyze(
                points, polygons, wind_config, direction,
            )
            self._wind_queue.put(("done", generation, project, scene, direction_key,
                                  direction, zones, engine_data))

        threading.Thread(target=analyze, daemon=True).start()

    def process_wind_queue(self) -> None:
        from tools.wind_scene_adapter import WindSceneAdapter
        while True:
            try:
                message = self._wind_queue.get_nowait()
            except queue.Empty:
                return
            status, generation, project, scene, key, direction, *payload = message
            if generation != self._wind_generation:
                continue
            if project is not self.current_project:
                continue
            eng = self.engine
            if eng and eng.math_model is not scene:
                continue
            if status == "error":
                self._wind_status = f"Rüzgar analizi başarısız: {payload[0]}"
                continue
            zones, engine_data = payload
            wind = self.wind_state()
            record = wind["directions"].get(key)
            if record is None:
                record = WindDirectionResult(w_dir=direction)
                wind["directions"][key] = record
            if isinstance(record, dict):
                record = WindDirectionResult(**record)
                wind["directions"][key] = record
            record.w_dir = direction
            WindSceneAdapter.update_direction_result(record, zones, engine_data)
            WindSceneAdapter.store_zones(project, key, zones, engine_data, direction)
            if eng is not None:
                eng.update_geo(project)
            self._wind_status = f"{len(zones)} rüzgar bölgesi hesaplandı."
            if self._ui_host:
                self._ui_host.on_wind_analysis_done(key)

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
            if eng.math_model:
                eng.math_model._render_filter = None
            self._hidden_ids = None
            if eng.math_model:
                for element in eng.math_model.all_elements.values():
                    if hasattr(element, "is_visible"):
                        element.is_visible = True
                    elif hasattr(element, "visible"):
                        element.visible = True
            if project is not None:
                eng.update_geo(project)
            eng.fit_view()

    def convert_frames_to_links(self, link_prop_name="DefaultLink", delete_original=True) -> None:
        from tools import frame_to_link
        eng = self.engine
        if not eng or not eng.math_model:
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
        if self.command_queue is None:
            return
        cmds = self.command_queue.drain()
        if not cmds:
            return
        geometry_dirty = False
        project_dirty = False
        for cmd in cmds:
            result = self._command_registry.dispatch(self, cmd)
            if not result.handled:
                logger.warning("[cmd] bilinmeyen: %r (%s)", cmd, type(cmd).__qualname__)
                continue
            geometry_dirty = geometry_dirty or result.geometry_dirty
            project_dirty = project_dirty or result.project_dirty
        if geometry_dirty and self.engine and self.current_project:
            self.engine.update_geo(self.current_project)
        if project_dirty and self._ui_host is not None:
            self._ui_host.on_project_changed()