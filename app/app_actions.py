# app/app_actions.py
from __future__ import annotations

import os
import queue
import threading

import numpy as np

from core.units import UnitSystem, convert_project_units
from domain.definition import WindDirectionResult
from domain.element import Area, Frame, Link, Node
from domain.polygon import Polygon
from domain.project import Project
from inspector.catalog_project import ProjectCatalog
from logging_config import CadLogger
from tools.s2k.loader import S2KLoader
from tools.wind_scene_adapter import WindSceneAdapter
from ui.file_dialog import ImGuiFileDialog

logger = CadLogger.get(__name__)

def _copy_load(load_set):
    from copy import deepcopy
    return deepcopy(load_set)

class AppActions:

    def __init__(self, app):
        self.app = app
        self.file_dialog = ImGuiFileDialog()
        self._wind_queue: queue.Queue = queue.Queue()
        self._wind_generation = 0
        self._wind_status = ""

    # ------------------------------------------------------------------
    # FILE
    # ------------------------------------------------------------------
    def new_project(self) -> None:
        self.app.set_project(Project())
        self.app.current_file_path = None
        self.app._model_text = "MODEL: YENİ SAHNE"

    def load(self, path: str) -> None:
        self.app.set_project(Project.load(path))
        if self.app.engine:
            self.app.engine.fit_view()
            self.app.engine.sel_mgr.clear()
        self.app.current_file_path = path
        self.app._model_text = f"MODEL: {os.path.basename(path)}"

    def save(self, path: str) -> None:
        self.app.current_project.save(path)
        self.app.current_file_path = path
        self.app._model_text = f"MODEL: {os.path.basename(path)}"

    def quick_save(self) -> None:
        if self.app.current_file_path:
            self.save(self.app.current_file_path)
        else:
            self.save_as_dialog()

    def save_as_dialog(self) -> None:
        self.file_dialog.open(
            mode="save", filters=[".cd4"], title="Projeyi Kaydet (.cd4)",
            initial_dir=os.getcwd(), default_name="model_projesi.cd4",
            on_select=self.save,
        )

    def open_dialog(self) -> None:
        self.file_dialog.open(
            mode="open", filters=[".cd4"], title="Proje Aç (.cd4)",
            initial_dir=os.getcwd(), on_select=self.load,
        )

    def draw_dialog(self) -> None:
        self.file_dialog.draw()

    def s2k_import(self) -> None:
        panel = self.app.panels.get("s2k_panel", {}).get("instance")
        if panel:
            panel.open(mode=getattr(panel, "MODE_IMPORT", "import"))

    def s2k_export(self) -> None:
        panel = self.app.panels.get("s2k_panel", {}).get("instance")
        if panel:
            panel.open(mode=getattr(panel, "MODE_EXPORT", "export"))

    def on_s2k_import_complete(self, project: Project) -> None:
        self.app.set_project(project)
        self.app._model_text = f"MODEL: S2K import ({len(project.math_model.frames)} çubuk)"

    def import_s2k_direct(self) -> None:
        candidates = [
            os.path.join(os.getcwd(), "tests", "eski_.s2k"),
            r"D:\Program\cad4\tests\eski_.s2k",
        ]
        path = next((p for p in candidates if os.path.exists(p)), None)
        if not path:
            return
        project = S2KLoader(path).load(Project())
        self.app.set_project(project)
        self.app._model_text = f"MODEL: eski_.s2k ({len(project.math_model.frames)} çubuk)"

    # ------------------------------------------------------------------
    # PANEL / SELECTION
    # ------------------------------------------------------------------
    def prepare_panel(self, name: str, panel) -> None:
        keys = self.app.panels[name].get("context", [])
        panel.set_context(self._resolve_context(keys))

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

    def _resolve_context(self, keys: list[str]) -> dict:
        if not keys:
            return {}
        resolvers = self._context_resolvers()
        ctx = {}
        for key in keys:
            fn = resolvers.get(key)
            if fn is None:
                continue
            ctx[key] = fn()
        return ctx

    def _context_resolvers(self) -> dict:
        app = self.app
        eng = app.engine
        project = app.current_project
        scene = eng.scene if eng else project.scene if project else None
        math_model = (
            eng.math_model if eng
            else project.math_model if project else None
        )
        renderer = eng.renderer if eng else None
        camera = eng.cam if eng else None
        selection = (
            list(eng.sel_mgr.get_selected()) if eng and eng.sel_mgr
            else list(math_model.get_selected()) if math_model else []
        )
        catalog = app._catalog

        return {
            "engine": lambda: eng,
            "scene": lambda: scene,
            "math_model": lambda: math_model,
            "project": lambda: project,
            "catalog": lambda: catalog,
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
            "wind_analysis_ref": lambda: self.wind_state(),
        }

    def on_selection_changed(self, selected: list) -> None:
        app = self.app
        if app.engine and app.engine.renderer:
            app.engine.renderer.update_sel()
        if app.inspector:
            app.inspector.set_selection(selected)

        for name, entry in app.panels.items():
            p = entry["instance"]
            if not getattr(p, "visible", False):
                continue
            hook = getattr(p, "on_scene_selection_changed", None)
            if callable(hook):
                hook(selected)

        self._refresh_presentation_renderers()

        polys = [e for e in selected if isinstance(e, Polygon)]
        if polys:
            panel = app.panels.get("polygon_properties", {}).get("instance")
            if panel is not None:
                if not getattr(panel, "visible", False):
                    self.prepare_panel("polygon_properties", panel)
                panel.open(polygon=polys[0])

        try:
            from domain.line import Line
        except ImportError:
            Line = ()
        lines = [e for e in selected if isinstance(e, Line)]
        if lines:
            panel = app.panels.get("line_properties", {}).get("instance")
            if panel is not None:
                if not getattr(panel, "visible", False):
                    self.prepare_panel("line_properties", panel)
                    panel.open()
                panel.on_selection_changed(selected)

        self._refresh_presentation_renderers()

    def on_hover_changed(self, element) -> None:
        pass

    def _refresh_presentation_renderers(self):
        eng = self.app.engine
        project = self.app.current_project
        if not (eng and eng.presentation_renderer and project):
            return
        

    # ------------------------------------------------------------------
    # WIND
    # ------------------------------------------------------------------
    def wind_state(self) -> dict:
        analysis = self.app.current_project.analysis
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

    def _wind_key(self, w_dir) -> str:
        directions = self.wind_state()["directions"]
        for key, record in directions.items():
            candidate = getattr(record, "w_dir", None)
            if candidate is None and isinstance(record, dict):
                candidate = record.get("w_dir")
            if candidate is not None and np.allclose(candidate, w_dir, atol=1e-8):
                return str(key)
        numeric = []
        for key in directions:
            try:
                numeric.append(int(key))
            except (TypeError, ValueError):
                continue
        key = f"{max(numeric, default=0) + 1:02d}"
        directions[key] = WindDirectionResult(w_dir=tuple(w_dir))
        return key

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

    def _start_wind_analysis(self, direction_key: str, direction) -> None:
        project = self.app.current_project
        eng = self.app.engine
        scene = eng.math_model if eng else project.math_model
        if scene is None:
            return

        points, polygons, wind_config = WindSceneAdapter.build_inputs(project)

        self._wind_generation += 1
        generation = self._wind_generation
        self._wind_status = "Rüzgar analizi çalışıyor..."

        def analyze() -> None:
            try:
                zones, engine_data = WindSceneAdapter.analyze(
                    points, polygons, wind_config, direction,
                )
                self._wind_queue.put(
                    ("done", generation, project, scene, direction_key,
                     direction, zones, engine_data)
                )
            except Exception as exc:
                self._wind_queue.put(
                    ("error", generation, project, scene, direction_key,
                     direction, str(exc))
                )

        threading.Thread(target=analyze, daemon=True).start()

    def process_wind_queue(self) -> None:
        while True:
            try:
                message = self._wind_queue.get_nowait()
            except queue.Empty:
                return

            status, generation, project, scene, key, direction, *payload = message
            if generation != self._wind_generation:
                continue
            if project is not self.app.current_project:
                continue
            eng = self.app.engine
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
            panel = self.app.panels.get("wind", {}).get("instance")
            if panel is not None and hasattr(panel, "_invalidate_zones_cache"):
                panel._invalidate_zones_cache()

    # ------------------------------------------------------------------
    # UNIT
    # ------------------------------------------------------------------
    def set_unit_system(self, unit_system: UnitSystem) -> None:
        project = self.app.current_project
        old = project.unit_system
        if old == unit_system:
            return
        convert_project_units(project, unit_system, reason="ui")

        eng = self.app.engine
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

        panel = self.app.panels.get("grid", {}).get("instance")
        if panel is not None and hasattr(panel, "on_unit_changed"):
            panel.on_unit_changed()

    def on_plane_selected(self, plane) -> None:
        project = self.app.current_project
        if project is None:
            return
        if plane is None:
            project.deactivate_plane()
        else:
            project.activate_plane(plane)
        eng = self.app.engine
        if eng is None:
            return
        if eng.interaction_renderer:
            eng.interaction_renderer.preview_plane = None
        if eng.renderer is not None and eng.math_model is not None:
            eng.update_geo(project)   # ★ kalıyor — active_plane geometri filtresi
        if eng.sel_mgr:
            eng.sel_mgr.clear()

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
            panel = self.app.panels.get(panel_name, {}).get("instance")
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
        # for entry in self.app.panels.values():
        #     p = entry["instance"]
        #     if getattr(p, "visible", False):
        #         p.close()
        pdm.start_3pt()

    def toggle_local_axes(self):
        eng = self.app.engine
        if eng and eng.scene:
            eng.scene.show_local_axes = not eng.scene.show_local_axes

    def toggle_loads(self):
        self.set_loads_visible(not self.get_loads_visible())

    def get_loads_visible(self) -> bool:
        panel = getattr(self.app, "load_display_panel", None)
        if panel is not None:
            return bool(panel.show_loads)
        pres = self.app.engine.presentation_renderer if self.app.engine else None
        if pres and pres.loads:
            return bool(pres.loads.enabled)
        return False

    def set_loads_visible(self, enabled: bool):
        panel = getattr(self.app, "load_display_panel", None)
        pres = self.app.engine.presentation_renderer if self.app.engine else None
        math_model = self.app.engine.math_model if self.app.engine else None

        if panel is not None:
            panel.set_loads_visible(
                enabled,
                renderer=self.app.engine.renderer if self.app.engine else None,
                math_model=math_model,
            )
            return

        if pres and pres.loads:
            pres.loads.enabled = bool(enabled)
            if enabled and math_model:
                pres.update_loads(math_model, camera_scale=1.0, scene_size=1.0)

    def toggle_show_only(self):
        eng = self.app.engine
        if not eng or not eng.math_model:
            return
        scn = eng.math_model
        
        if getattr(self.app, "_show_only_ids", None) is None:
            selected = scn.get_selected()
            if not selected:
                return
            self.app._show_only_ids = {e.unique_id for e in selected}
        else:
            self.app._show_only_ids = None
            
        scn._render_filter = self.app._show_only_ids
        
        project = self.app.current_project
        if project:
            eng.update_geo(project)

    def toggle_hide_selected(self):
        eng = self.app.engine
        if not eng or not eng.math_model:
            return
        
        # Gizli ID'ler havuzunu başlat (eğer yoksa)
        if not hasattr(self.app, "_hidden_ids") or self.app._hidden_ids is None:
            self.app._hidden_ids = set()

        selected = eng.math_model.get_selected()
            
        if not selected:
            return
        
        # Seçilenlerin ID'lerini mevcut gizli havuzuna ekle (biriktir)
        new_hidden_ids = {getattr(e, "unique_id", id(e)) for e in selected}
        self.app._hidden_ids.update(new_hidden_ids)

        # Havuzdaki tüm elemanları görünmez yap
        hidden_set = self.app._hidden_ids
        for element in eng.math_model.all_elements.values():
            if element.unique_id not in hidden_set:
                continue
            if hasattr(element, "is_visible"):
                element.is_visible = False
            elif hasattr(element, "visible"):
                element.visible = False

        # Seçimi temizle
        if eng.sel_mgr:
            eng.sel_mgr.clear()

        # Görünürlüğü güncelle
        if eng.project:
            eng.update_geo(eng.project)

    def apply_frame_load(self, frames, load_set):
        if not frames or not load_set.segments:
            return
        pattern = load_set.pattern_name
        for frame in frames:
            frame.dist_load_sets[pattern] = _copy_load(load_set)
            frame.mark_dirty()
        self.set_loads_visible(True)
        eng = self.app.engine
        if eng and eng.math_model and eng.renderer:
            eng.renderer.update_geo(eng.math_model)
            eng.math_model.clear_dirty()

    def on_area_transfer_complete(self, frames):
        if not frames:
            return
        self.set_loads_visible(True)
        eng = self.app.engine
        if eng and eng.math_model and eng.renderer:
            eng.renderer.update_geo(eng.math_model)
            eng.math_model.clear_dirty()

    def convert_frames_to_links(self, link_prop_name="DefaultLink",
                                delete_original=True):
        from tools import frame_to_link
        eng = self.app.engine
        if not eng or not eng.math_model:
            return
        scn = eng.math_model
        frames = [e for e in scn.get_selected() if e.__class__.__name__ == "Frame"]
        if not frames:
            return
        report = frame_to_link.convert_frames_to_links(
            scene=scn,
            project=self.app.current_project,
            frames=frames,
            link_prop_name=link_prop_name,
            delete_original=delete_original,
        )
        if self.app._show_only_ids is not None:
            removed = {f.unique_id for f in frames}
            self.app._show_only_ids -= removed
            self.app._show_only_ids.update(l.unique_id for l in report["new_links"])
            scn._render_filter = self.app._show_only_ids
        if eng.sel_mgr:
            eng.sel_mgr.clear()

    def show_entire_model(self) -> None:
        project = self.app.current_project
        eng = self.app.engine
        if project is not None:
            project.deactivate_plane()  # Aktif düzlemi kapat, tüm model görünsün
            
        if eng is not None:
            # Render filtrelerini temizle
            self.app._show_only_ids = None
            if eng.math_model:
                eng.math_model._render_filter = None
                
            # Görünürlükleri sıfırla (gizlenenleri aç)
            if hasattr(self.app, "_hidden_ids"):
                self.app._hidden_ids = None
                
            # Model elemanlarını tekrar görünür yap
            if eng.math_model:
                for element in eng.math_model.all_elements.values():
                    if hasattr(element, "is_visible"):
                        element.is_visible = True
                    elif hasattr(element, "visible"):
                        element.visible = True
                    
            # Geometriyi ve görünümü güncelle
            eng.update_geo(project)
            eng.fit_view()