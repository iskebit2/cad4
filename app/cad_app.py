# app/cad_app.py
"""
CadApp — uygulama orkestratörü.

Sorumluluk:
    - Registry (panels, shortcuts, actions)
    - Engine yaşam döngüsü (lazy init)
    - GLFW event → engine köprüsü
    - Proje yükleme/kaydetme
    - Toolbar komutları

DEĞİL: pencere/ImGui kurulumu (CadWindow), render (Engine), panel içeriği.
"""
from __future__ import annotations

import copy
import os
import queue
import threading
import time

import glfw
import numpy as np
from imgui_bundle import imgui
from OpenGL.GL import (
    GL_ARRAY_BUFFER,
    GL_BLEND,
    GL_COLOR_BUFFER_BIT,
    GL_CULL_FACE,
    GL_DEPTH_BUFFER_BIT,
    GL_DEPTH_TEST,
    GL_ELEMENT_ARRAY_BUFFER,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_SRC_ALPHA,
    glBindBuffer,
    glBindVertexArray,
    glBlendFunc,
    glClear,
    glClearColor,
    glDisable,
    glEnable,
    glUseProgram,
    glViewport,
)

from app.cad_window import CadWindow
from app.panel_registry import PANEL_SPECS
from app.toolbar import Toolbar
from app.ui_capture import (
    keyboard_captured_by_ui,
    mods_to_dict,
    mouse_over_ui,
    sync_modifiers_from_glfw,
)
from core.gl_engine import Engine
from core.input_manager import (
    MOUSE_BUTTON_LEFT,
    MOUSE_BUTTON_MIDDLE,
    MOUSE_BUTTON_RIGHT,
)
from core.plane_draw_manager import PlaneCreationTool
from core.units import UnitSystem, convert_project_units
from data.enums import GridPlane
from domain.definition import Section, WindDirectionResult
from domain.element import Area, Frame, Link, Node, Polygon
from domain.project import Project
from inspector import InspectorWindow
from inspector.catalog_project import ProjectCatalog
from logging_config import CadLogger
from tools import frame_to_link
from tools.s2k.loader import S2KLoader
from tools.wind_scene_adapter import WindSceneAdapter
from ui.file_dialog import ImGuiFileDialog

logger = CadLogger.get(__name__)


class CadApp:

    MIDDLE_DOUBLE_CLICK_INTERVAL = 0.25
    MIDDLE_DOUBLE_CLICK_MAX_DRAG = 4.0

    # ==================================================================
    # INIT
    # ==================================================================
    def __init__(self, window: CadWindow):
        self._init_state(window)
        self._init_registry()
        self._init_shortcuts()
        self._init_actions()

        self.toolbar = Toolbar(
            commands=self._build_toolbar_commands(),
            panel_states=self._build_panel_states(),
        )
        self.file_dialog = ImGuiFileDialog()

        self._load_section_catalog()
        self._wire_window_callbacks()

    def _init_state(self, window: CadWindow) -> None:
        # Window / engine
        self.window = window
        self.engine: Engine | None = None
        self.initialized = False

        # Proje
        self.current_project = Project()
        self.current_file_path: str | None = None
        self._model_text = "MODEL: YENİ SAHNE"
        self._catalog = ProjectCatalog(self.current_project)

        # Katalog / görünüm
        self.section_catalog: dict[str, Section] = {}
        self.hover_visual_enabled = True

        # Mouse
        self._pending: list[tuple] = []
        self._mouse_pressed: set[str] = set()
        self._last_middle_click_time = 0.0
        self._middle_press_pos = (0.0, 0.0)
        self._middle_dragged = False
        self._show_only_ids: set[int] | None = None
        self._wind_queue: queue.Queue = queue.Queue()
        self._wind_analysis_generation = 0
        self._wind_analysis_status = ""

        # Güvenlik ağı: panel yüklenemezse erişim çalışsın
        self.inspector: InspectorWindow | None = None

        # Lazy cache
        self._io: object | None = None

    def _wire_window_callbacks(self) -> None:
        w = self.window
        w.on_key_down     = self.on_key_down
        w.on_key_up       = self.on_key_up
        w.on_mouse_button = self.on_mouse_button
        w.on_mouse_move   = self.on_mouse_move
        w.on_scroll       = self.on_scroll
        w.on_resize       = self._on_resize
        w.on_char         = self.on_char
        w.on_focus        = self.on_window_focus

    # ==================================================================
    # REGISTRY
    # ==================================================================
    def _init_registry(self) -> None:
        self.panels: dict[str, dict] = {}
        self._panels_by_category: dict[str, list[str]] = {}
        self._shortcut_map: dict[str, str] = {}

        for spec in PANEL_SPECS:
            if spec.get("kind", "panel") != "panel":
                continue

            name = spec["name"]
            try:
                inst = spec["cls"]()
            except Exception:
                logger.exception("[Registry] Panel başlatılamadı: %s", name)
                continue

            inst.app = self

            self.panels[name] = {
                "instance":   inst,
                "title":      spec["title"],
                "category":   spec["category"],
                "quick":      spec.get("quick", False),
                "shortcut":   spec.get("shortcut"),
                "menu_label": spec.get("menu_label"),
                "icon":       spec.get("icon"),
                "context":    spec.get("context", []),
            }
            self._panels_by_category.setdefault(spec["category"], []).append(name)
            if spec.get("shortcut"):
                self._shortcut_map[spec["shortcut"]] = name

            # Kısayol attribute erişimi: self.s2k_panel, self.inspector...
            setattr(self, name, inst)

        self._wire_panel_hooks()

    def _wire_panel_hooks(self) -> None:
        """Panele özel callback enjeksiyonları (BasePanel dışı)."""
        frame_load = self.panels.get("assign_frame_distributed_load")
        if frame_load:
            frame_load["instance"].on_apply = self._apply_frame_distributed_load

        area_to_frame = self.panels.get("area_to_frame")
        if area_to_frame:
            area_to_frame["instance"].on_transfer_complete = (
                self._on_area_load_transfer_complete
            )

        render_settings = self.panels.get("render_settings")
        if render_settings:
            inst = render_settings["instance"]
            inst.get_loads_visible = self._get_loads_visible
            inst.set_loads_visible = self._set_loads_visible

        s2k = self.panels.get("s2k_panel")
        if s2k:
            inst = s2k["instance"]
            inst.on_import_complete    = self._on_s2k_import_complete
            inst.get_project           = lambda: self.current_project
            inst.get_selected_elements = self._selected

        ins = self.panels.get("inspector")
        if ins:
            inst = ins["instance"]
            inst.app = self
            inst.set_catalog(self._catalog)

        wind = self.panels.get("wind")
        if wind:
            inst = wind["instance"]
            inst.on_run_analysis = self._on_run_wind_analysis
            inst.on_select_direction = self.on_select_wind_direction

    def _wind_analysis_state(self) -> dict:
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
                first_direction = first.get("w_dir", (1.0, 0.0, 0.0))
            else:
                first_direction = getattr(first, "w_dir", (1.0, 0.0, 0.0))
            wind["active_direction"] = tuple(
                first_direction
            )
        return wind

    def _wind_direction_key(self, w_dir: tuple[float, float, float]) -> str:
        directions = self._wind_analysis_state()["directions"]
        for key, record in directions.items():
            candidate = getattr(record, "w_dir", None)
            if candidate is None and isinstance(record, dict):
                candidate = record.get("w_dir")
            if candidate is not None and np.allclose(candidate, w_dir, atol=1e-8):
                return str(key)

        numeric_keys = []
        for key in directions:
            try:
                numeric_keys.append(int(key))
            except (TypeError, ValueError):
                continue
        key = f"{max(numeric_keys, default=0) + 1:02d}"
        directions[key] = WindDirectionResult(w_dir=tuple(w_dir))
        return key

    def _on_run_wind_analysis(self) -> None:
        wind = self._wind_analysis_state()
        active = wind.get("active_direction")
        if active is None:
            active = next(iter(wind["directions"].values())).w_dir
        direction = tuple(float(value) for value in active)
        key = self._wind_direction_key(direction)
        self._start_wind_analysis(key, direction)

    def on_select_wind_direction(self, w_dir: tuple[float, float, float]) -> None:
        try:
            direction = tuple(float(value) for value in w_dir)
            if len(direction) != 3 or not np.isfinite(direction).all():
                raise ValueError("Rüzgar yönü üç sonlu koordinat içermelidir.")
            if np.linalg.norm(direction[:2]) < 1e-12:
                raise ValueError("Rüzgar yönünün yatay bileşeni sıfır olamaz.")
        except (TypeError, ValueError):
            logger.exception("[Zones] Geçersiz rüzgar yönü: %r", w_dir)
            self._wind_analysis_status = "Geçersiz rüzgar yönü."
            return

        wind = self._wind_analysis_state()
        wind["active_direction"] = direction
        key = self._wind_direction_key(direction)
        record = wind["directions"][key]
        if hasattr(record, "w_dir"):
            record.w_dir = direction
        elif isinstance(record, dict):
            record["w_dir"] = direction
        self._start_wind_analysis(key, direction)

    def _start_wind_analysis(
        self, direction_key: str, direction: tuple[float, float, float],
    ) -> None:
        project = self.current_project
        scene = self.engine.scene if self.engine else project.scene
        if scene is None:
            logger.error("[Zones] Rüzgar analizi için aktif sahne bulunamadı.")
            self._wind_analysis_status = "Aktif sahne bulunamadı."
            return

        try:
            points, polygons, wind_config = WindSceneAdapter.build_inputs(scene, project)
        except Exception:
            logger.exception("[Zones] Rüzgar analizi girdisi oluşturulamadı.")
            self._wind_analysis_status = "Analiz girdisi oluşturulamadı."
            return

        self._wind_analysis_generation += 1
        generation = self._wind_analysis_generation
        self._wind_analysis_status = "Rüzgar analizi çalışıyor..."

        def analyze() -> None:
            try:
                zones, engine_data = WindSceneAdapter.analyze(
                    points, polygons, wind_config, direction
                )
                self._wind_queue.put(
                    ("done", generation, project, scene, direction_key,
                     direction, zones, engine_data)
                )
            except Exception as exc:
                logger.exception("[Zones] Rüzgar analizi başarısız.")
                self._wind_queue.put(
                    ("error", generation, project, scene, direction_key,
                     direction, str(exc))
                )

        threading.Thread(target=analyze, daemon=True).start()

    def _process_wind_queue(self) -> None:
        while True:
            try:
                message = self._wind_queue.get_nowait()
            except queue.Empty:
                return

            status, generation, project, scene, direction_key, direction, *payload = message
            if generation != self._wind_analysis_generation or project is not self.current_project:
                continue
            if self.engine and self.engine.scene is not scene:
                continue

            if status == "error":
                error = payload[0]
                self._wind_analysis_status = f"Rüzgar analizi başarısız: {error}"
                logger.error("[Zones] %s", self._wind_analysis_status)
                continue

            zones, engine_data = payload
            try:
                wind = self._wind_analysis_state()
                record = wind["directions"].get(direction_key)
                if record is None:
                    record = WindDirectionResult(w_dir=direction)
                    wind["directions"][direction_key] = record
                if isinstance(record, dict):
                    record = WindDirectionResult(**record)
                    wind["directions"][direction_key] = record
                record.w_dir = direction
                WindSceneAdapter.update_direction_result(record, zones, engine_data)
                WindSceneAdapter.store_zones(
                    project, direction_key, zones, engine_data, direction,
                )
                self._wind_analysis_status = f"{len(zones)} rüzgar bölgesi hesaplandı."
                panel = self.panels.get("wind", {}).get("instance")
                if panel is not None:
                    panel._invalidate_zones_cache()
                logger.info("[Zones] %s", self._wind_analysis_status)
            except Exception:
                logger.exception("[Zones] Rüzgar sonuçları sahneye kaydedilemedi.")
                self._wind_analysis_status = "Rüzgar sonuçları sahneye kaydedilemedi."

    def _init_shortcuts(self) -> None:
        self._key_shortcuts: dict[int, tuple] = {}
        for shortcut, panel_name in self._shortcut_map.items():
            parts = shortcut.split("+")
            key_name = parts[-1]
            mods = {p.upper() for p in parts[:-1]}

            glfw_key = getattr(glfw, f"KEY_{key_name}", None)
            if glfw_key is None:
                logger.warning("[Shortcut] Geçersiz: %s", shortcut)
                continue

            self._key_shortcuts[glfw_key] = (
                panel_name,
                "CTRL"  in mods,
                "SHIFT" in mods,
            )

    def _init_actions(self) -> None:
        self._actions = {
            "save_project": self._save_project,
            "update_geo":   self._on_update_geo,
        }

    # ------------------------------------------------------------------
    # CONTEXT RESOLVERS
    # ------------------------------------------------------------------
    def _context_resolvers(self) -> dict[str, callable]:
        eng = self.engine
        scn = eng.scene if eng else self.current_project.scene
        renderer = eng.renderer if eng else None
        camera = eng.cam if eng else None
        selection = list(scn.get_selected()) if scn else []
        project = self.current_project
        catalog = self._catalog

        return {
            "scene":            lambda: scn,
            "project":          lambda: project,
            "catalog":          lambda: catalog,
            "selection":        lambda: selection,
            "selection_frames": lambda: [e for e in selection if isinstance(e, Frame)],
            "selection_areas":  lambda: [e for e in selection if isinstance(e, Area)],
            "selection_polygons": lambda: [
                e for e in selection if isinstance(e, Polygon)
            ],
            "selection_links":  lambda: [e for e in selection if isinstance(e, Link)],
            "selection_nodes":  lambda: [e for e in selection if isinstance(e, Node)],
            "patterns":         lambda: list(getattr(project, "load_patterns", {}).keys()),
            "sections":         lambda: list(getattr(project, "sections", {}).keys()),
            "materials":        lambda: list(getattr(project, "materials", {}).keys()),
            "renderer":         lambda: renderer,
            "camera":           lambda: camera,
            "wind_analysis_ref": lambda: self._wind_analysis_state(),
        }

    def _resolve_panel_context(self, keys: list[str]) -> dict:
        if not keys:
            return {}
        resolvers = self._context_resolvers()
        ctx = {}
        for key in keys:
            fn = resolvers.get(key)
            if fn is None:
                logger.warning("[Context] Bilinmeyen anahtar: %s", key)
                continue
            try:
                ctx[key] = fn()
            except Exception:
                logger.exception("[Context] %s çözümlenemedi", key)
        return ctx

    def _prepare_panel_before_open(self, name: str, panel) -> None:
        keys = self.panels[name].get("context", [])
        panel.set_context(self._resolve_panel_context(keys))

    def toggle_panel(self, name: str) -> None:
        entry = self.panels.get(name)
        if not entry:
            return
        p = entry["instance"]
        if getattr(p, "visible", False):
            p.close()
            return
        self._prepare_panel_before_open(name, p)
        p.open()

    def _selected(self):
        if self.engine and self.engine.scene:
            return self.engine.scene.get_selected()
        return []

    # ==================================================================
    # FRAME
    # ==================================================================
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
            self.engine.on_hover_changed_callback = self._on_hover_changed
            self.engine.sel_mgr.on_selection_changed = self._on_selection_changed
            self.engine.plane_draw_mgr = PlaneCreationTool(self.engine)
            if self.engine.renderer:
                self.engine.renderer.set_plane_draw_mgr(self.engine.plane_draw_mgr)
            self.initialized = True

            if self.current_project:
                self.set_project(self.current_project)
        except Exception:
            logger.exception("[Init] Engine başlatma hatası")
            self.initialized = True

    def _active_working_plane(self):
        project = self.current_project
        if project is None or project.scene is None:
            return None
        return project.plane_mgr.active_plane

    def frame(self, dt: float) -> None:
        self._ensure_engine()
        if not self.initialized:
            return

        if self._io is None:
            self._io = imgui.get_io()

        # 1) Toolbar
        current_unit = self.current_project.unit_system if self.current_project else None
        self.toolbar.draw(
            model_text=self._model_text,
            current_unit=current_unit,
            project=self.current_project,
        )
        self.file_dialog.draw()

        # 2) Bekleyen event'ler
        self.process_pending()
        self._process_wind_queue()

        # 3) Sahne dirty ise renderer güncelle
        self._update_scene_if_dirty()

        # 4) Render
        self._render_scene(dt)

        # 5) Paneller
        self._draw_panels()

        # 6) Pick
        if self.engine and self.engine.pending_pick_check:
            self.engine.check_pick_result()

    def _update_scene_if_dirty(self) -> None:
        scn = self.engine.scene if self.engine else None
        if scn and hasattr(scn, "is_dirty") and scn.is_dirty():
            if self.engine.renderer:
                self.engine.renderer.update_geo(scn)
            scn.clear_dirty()

    def _draw_panels(self) -> None:
        for entry in self.panels.values():
            panel = entry["instance"]
            if getattr(panel, "visible", False) and hasattr(panel, "draw"):
                panel.draw()

    def _render_scene(self, dt: float) -> None:
        w, h = self.window.fb_width, self.window.fb_height
        glViewport(0, 0, w, h)
        try:
            glEnable(GL_DEPTH_TEST)
            glClearColor(0.08, 0.10, 0.16, 1.0)
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

            self.engine.renderer.set_dt(dt)
            self.engine.renderer.render(self.engine.cam)

            self._draw_snap_indicator(w, h)

            if self.engine.draw_mgr.is_active:
                mvp = (self.engine.cam.get_projection_matrix()
                       @ self.engine.cam.get_view_matrix())
                self.engine.draw_mgr.render_preview(mvp, self.engine.preview_s)

            pdm = getattr(self.engine, "plane_draw_mgr", None)
            if pdm and pdm.is_active:
                self._draw_pdm_hud(pdm)
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

    # ==================================================================
    # TOOLBAR COMMANDS / STATES
    # ==================================================================
    def _build_toolbar_commands(self) -> dict[str, callable]:
        cmds = {
            "new_project": self._new_project,
            "open":        self._on_toolbar_open,
            "save":        self._quick_save,
            "save_as":     self._save_as_project,
            "close_app":   lambda: glfw.set_window_should_close(self.window.window, True),
            "s2k_import":  self._open_s2k_panel_import,
            "s2k_export":  self._open_s2k_panel_export,
            "draw_poly":   self._toggle_draw_mode,
            "draw_plane":  self._toggle_plane_draw,
            "render_mode":      lambda: self.engine.renderer.toggle_render_mode() if self.engine else None,
            "toggle_loads_vis": self._toggle_loads_visibility,
            "local_axes":       self._toggle_local_axes,
            "show_only":        self.toggle_show_only,
            "convert_to_link":  lambda: self.convert_selected_frames_to_links("DefaultLink"),
            "on_unit_change":   self.set_unit_system,
        }
        for name in self.panels:
            cmds[name] = (lambda n=name: self.toggle_panel(n))
        return cmds

    def _build_panel_states(self) -> dict[str, callable]:
        states = {
            "draw_poly":  lambda: bool(self.engine and self.engine.draw_mgr and self.engine.draw_mgr.is_active),
            "draw_plane": lambda: bool(self.engine and getattr(self.engine, "plane_draw_mgr", None) and self.engine.plane_draw_mgr.is_active),
            "local_axes": lambda: bool(self.engine and self.engine.scene and self.engine.scene.show_local_axes),
            "show_loads": lambda: bool(
                self._get_loads_visible()
            ),
            "show_only":  lambda: self._show_only_ids is not None,
        }
        for name, entry in self.panels.items():
            inst = entry["instance"]
            states[name] = (lambda i=inst: getattr(i, "visible", False))
        return states

    # ==================================================================
    # FILE ACTIONS
    # ==================================================================
    def _new_project(self) -> None:
        self.set_project(Project())
        self.current_file_path = None
        self._model_text = "MODEL: YENİ SAHNE"
        logger.info("[File] Yeni proje")

    def _load_project(self, path: str) -> None:
        try:
            self.set_project(Project.load(path))
            if self.engine:
                self.engine.fit_view()
                self.engine.sel_mgr.clear()
            self.current_file_path = path
            self._model_text = f"MODEL: {os.path.basename(path)}"
        except Exception:
            logger.exception("[File] Proje yükleme hatası")

    def _save_project(self, path: str) -> None:
        try:
            self.current_project.save(path)
            self.current_file_path = path
            self._model_text = f"MODEL: {os.path.basename(path)}"
        except Exception:
            logger.exception("[File] Proje kaydetme hatası")

    def _quick_save(self) -> None:
        if self.current_file_path:
            self._save_project(self.current_file_path)
        else:
            self._on_toolbar_save()

    def _save_as_project(self) -> None:
        self._on_toolbar_save()

    def _on_toolbar_open(self) -> None:
        self.file_dialog.open(
            mode="open", filters=[".cd4"], title="Proje Aç (.cd4)",
            initial_dir=os.getcwd(), on_select=self._load_project,
        )

    def _on_toolbar_save(self) -> None:
        self.file_dialog.open(
            mode="save", filters=[".cd4"], title="Projeyi Kaydet (.cd4)",
            initial_dir=os.getcwd(), default_name="model_projesi.cd4",
            on_select=self._save_project,
        )

    # ------------------------------------------------------------------
    # S2K
    # ------------------------------------------------------------------
    def _open_s2k_panel_import(self) -> None:
        entry = self.panels.get("s2k_panel")
        if entry:
            p = entry["instance"]
            p.open(mode=getattr(p, "MODE_IMPORT", "import"))

    def _open_s2k_panel_export(self) -> None:
        entry = self.panels.get("s2k_panel")
        if entry:
            p = entry["instance"]
            p.open(mode=getattr(p, "MODE_EXPORT", "export"))

    def _on_s2k_import_complete(self, project: Project) -> None:
        self.set_project(project)
        self._model_text = f"MODEL: S2K import ({len(project.scene.frames)} çubuk)"
        logger.info("[S2K] Import tamam")

    def _import_s2k_direct(self) -> None:
        """F10 test yolu."""
        candidates = [
            os.path.join(os.getcwd(), "tests", "eski_.s2k"),
            r"D:\Program\cad4\tests\eski_.s2k",
        ]
        path = next((p for p in candidates if os.path.exists(p)), None)
        if not path:
            logger.error("[Direct] Dosya yok: %s", candidates)
            return
        try:
            project = S2KLoader(path).load(Project())
            self.set_project(project)
            self._model_text = f"MODEL: eski_.s2k ({len(project.scene.frames)} çubuk)"
        except Exception:
            logger.exception("[Direct] Hata")

    # ==================================================================
    # PROJE / SAHNE
    # ==================================================================
    def set_project(self, project: Project) -> None:
        self.current_project = project
        self._wind_analysis_state()
        self._catalog = ProjectCatalog(project)  # cache yenile

        if not self.engine:
            logger.warning("[set_project] engine yok — sadece proje atandı")
            return
        if project.scene is None:
            return

        scn = project.scene
        self.engine.set_scene(scn)

        if self.inspector:
            self.inspector.set_catalog(self._catalog)
            self.inspector.set_scene(scn)

        if self.engine.renderer:
            try:
                self.engine.renderer.update_geo(scn)
            except Exception:
                logger.exception("[set_project] update_geo hatası")

        g = getattr(project, "grid", None)
        if g and self.engine.grid:
            self.engine.grid.set_coords(g.x_coords, g.y_coords, g.z_coords)
            self.engine.grid.set_origin(g.origin_x, g.origin_y, g.origin_z)
            for plane_name, vis in g.planes_visibility.items():
                try:
                    self.engine.grid.set_plane(GridPlane[plane_name], visible=vis)
                except KeyError:
                    pass
            self.engine.grid.set_user_planes(
                getattr(g, "user_planes", [])
            )
        else:
            self.engine.fit_view()

        if self.engine.sel_mgr:
            self.engine.sel_mgr.clear()


    def _on_update_geo(self) -> None:
        if self.engine and self.engine.renderer and self.engine.scene:
            self.engine.renderer.update_geo(self.engine.scene)

    def set_unit_system(self, unit_system: UnitSystem) -> None:
        old = self.current_project.unit_system
        if old == unit_system:
            return

        n = convert_project_units(self.current_project, unit_system, reason="ui")
        logger.info("[Units] %s → %s (%d alan)", old.value, unit_system.value, n)

        # --- GridSystem'i Project.grid'ten yeniden besle ---
        g = getattr(self.current_project, "grid", None)
        if self.engine and self.engine.grid and g:
            self.engine.grid.set_coords(g.x_coords, g.y_coords, g.z_coords)
            self.engine.grid.set_origin(g.origin_x, g.origin_y, g.origin_z)

        # --- Renderer yenile ---
        if self.engine and self.engine.scene and self.engine.renderer:
            self.engine.scene.mark_dirty()
            self.engine.renderer.update_geo(self.engine.scene)

        # --- Kamera bounds ---
        if self.engine and self.engine.cam and self.engine.grid:
            try:
                center, size = self.engine.grid.get_bounds()
                self.engine.cam.update_bounds(center, size)
            except Exception:
                pass

        # --- GridPanel text cache ---
        panel = self.panels.get("grid", {}).get("instance")
        if panel is not None and hasattr(panel, "on_unit_changed"):
            panel.on_unit_changed()

    def _on_section_changed(self) -> None:
        if self.engine and self.engine.scene:
            scn = self.engine.scene
            scn.mark_dirty()
            if self.engine.renderer:
                self.engine.renderer.update_geo(scn)
                scn.clear_dirty()

    # ==================================================================
    # SELECTION / HOVER
    # ==================================================================
    def _on_selection_changed(self, selected_elements) -> None:
        if self.engine and self.engine.renderer:
            self.engine.renderer.update_sel()
        if self.inspector:
            self.inspector.set_selection(selected_elements)

        for name, entry in self.panels.items():
            p = entry["instance"]
            if not getattr(p, "visible", False):
                continue
            hook = getattr(p, "on_scene_selection_changed", None)
            if callable(hook):
                try:
                    hook(selected_elements)
                except Exception:
                    logger.exception("[Selection] %s hook hatası", name)

    def _on_hover_changed(self, element) -> None:
        pass

    # ==================================================================
    # GÖRÜNÜM MODLARI
    # ==================================================================
    def _toggle_draw_mode(self) -> None:
        if not self.engine or not self.engine.draw_mgr:
            return
        mgr = self.engine.draw_mgr
        mgr.close() if mgr.is_active else mgr.start()

    def _toggle_plane_draw(self) -> None:
        pdm = getattr(self.engine, "plane_draw_mgr", None)
        if pdm is None:
            return
        if pdm.is_active:
            pdm.cancel()
            return
        # Aktif panelleri kapat (modal)
        for entry in self.panels.values():
            p = entry["instance"]
            if getattr(p, "visible", False):
                try:
                    p.close()
                except Exception:
                    pass
        pdm.start()

    def _toggle_local_axes(self) -> None:
        if self.engine and self.engine.scene:
            self.engine.scene.show_local_axes = not self.engine.scene.show_local_axes

    def _toggle_loads_visibility(self) -> None:
        self._set_loads_visible(not self._get_loads_visible())

    def _get_loads_visible(self) -> bool:
        panel = getattr(self, "load_display_panel", None)
        if panel is not None:
            return bool(panel.show_loads)
        renderer = self.engine.renderer if self.engine else None
        load_renderer = getattr(renderer, "load_renderer", None)
        return bool(load_renderer and load_renderer.enabled)

    def _set_loads_visible(self, enabled: bool) -> None:
        panel = getattr(self, "load_display_panel", None)
        renderer = self.engine.renderer if self.engine else None
        scene = self.engine.scene if self.engine else None
        if panel is not None:
            panel.set_loads_visible(enabled, renderer=renderer, scene=scene)
        elif renderer and renderer.load_renderer:
            renderer.set_loads_enabled(enabled)

    def _apply_frame_distributed_load(self, frames, load_set) -> None:
        if not frames or not load_set.segments:
            return

        pattern = load_set.pattern_name
        for frame in frames:
            frame.dist_load_sets[pattern] = copy.deepcopy(load_set)
            # frame.dist_loads'e YAZMA — property türetir
            frame.mark_dirty()

        self._set_loads_visible(True)
        if self.engine and self.engine.scene and self.engine.renderer:
            self.engine.renderer.update_geo(self.engine.scene)
            self.engine.scene.clear_dirty()

    def _on_area_load_transfer_complete(self, frames) -> None:
        if not frames:
            return
        self._set_loads_visible(True)
        if self.engine and self.engine.scene and self.engine.renderer:
            self.engine.renderer.update_geo(self.engine.scene)
            self.engine.scene.clear_dirty()

    def toggle_show_only(self) -> None:
        if not self.engine or not self.engine.scene:
            return
        scn = self.engine.scene
        if self._show_only_ids is None:
            selected = scn.get_selected()
            if not selected:
                return
            self._show_only_ids = {e.unique_id for e in selected}
        else:
            self._show_only_ids = None

        scn._render_filter = self._show_only_ids
        if self._show_only_ids is not None:
            self.engine.renderer.update_geo(scn)
        else:
            self.engine.set_scene(scn)

    def convert_selected_frames_to_links(
        self, link_prop_name: str = "DefaultLink", delete_original: bool = True,
    ) -> None:
        if not self.engine or not self.engine.scene:
            return
        scn = self.engine.scene
        frames = [e for e in scn.get_selected() if isinstance(e, Frame)]
        if not frames:
            return

        report = frame_to_link.convert_frames_to_links(
            scene=scn, project=self.current_project,
            frames=frames, link_prop_name=link_prop_name,
            delete_original=delete_original,
        )

        if self._show_only_ids is not None:
            removed = {f.unique_id for f in frames}
            self._show_only_ids -= removed
            self._show_only_ids.update(l.unique_id for l in report["new_links"])
            scn._render_filter = self._show_only_ids

        if self.engine.sel_mgr:
            self.engine.sel_mgr.clear()

    # ==================================================================
    # EVENT HANDLERS (GLFW → pending → process)
    # ==================================================================
    def on_char(self, codepoint):
        # GlfwRenderer io.add_input_character'ı hallediyor
        return True

    def on_key_down(self, key, scancode, mods):
        self._pending.append(("key_down", (key, scancode, mods)))
        return True

    def on_key_up(self, key, scancode):
        self._pending.append(("key_up", (key, scancode)))
        return True

    def on_mouse_button(self, button, action, mods):
        self._pending.append(("button", (button, action, mods)))
        return True

    def on_mouse_move(self, x, y):
        self._pending.append(("move", (x, y)))
        return True

    def on_scroll(self, xoffset, yoffset):
        # GlfwRenderer io.mouse_wheel'i hallediyor — burada sadece sahne zoom
        self._pending.append(("scroll", (xoffset, yoffset)))
        return True

    def on_window_focus(self, focused: bool):
        if not focused and self.engine and self.engine.input:
            self.engine.input.clear_modifiers()

    def process_pending(self) -> None:
        if not self._pending:
            return
        events = self._pending
        self._pending = []
        for kind, args in events:
            try:
                if kind == "move":
                    self._handle_move(*args)
                elif kind == "button":
                    self._handle_button(*args)
                elif kind == "scroll":
                    self._handle_scroll(*args)
                elif kind == "key_down":
                    self._handle_key_down(*args)
                elif kind == "key_up":
                    self._handle_key_up(*args)
            except Exception:
                logger.exception("Event işleme hatası: %s %s", kind, args)

    # ------------------------------------------------------------------
    def _handle_button(self, button, action, mods):
        eng = self.engine
        if eng is None:
            return
        self._sync_from_glfw_mods(mods)

        x, y = self.window.get_mouse_pos()
        if mouse_over_ui():
            return

        # Plane Draw önceliği
        pdm = getattr(eng, "plane_draw_mgr", None)
        if pdm is not None and pdm.is_active:
            if action == glfw.PRESS and button == glfw.MOUSE_BUTTON_LEFT:
                if pdm.on_mouse_click(x, y):
                    return

        if button == glfw.MOUSE_BUTTON_LEFT:
            kivy_btn, name = MOUSE_BUTTON_LEFT, "left"
        elif button == glfw.MOUSE_BUTTON_RIGHT:
            kivy_btn, name = MOUSE_BUTTON_RIGHT, "right"
        elif button == glfw.MOUSE_BUTTON_MIDDLE:
            kivy_btn, name = MOUSE_BUTTON_MIDDLE, "middle"
        else:
            return

        if eng.input:
            eng.input.update_mouse_position(x, y)
            eng.input.set_button_state(kivy_btn, action == glfw.PRESS)

        if action == glfw.PRESS:
            self._mouse_pressed.add(name)
            self._on_down(name, x, y)
        elif action == glfw.RELEASE:
            self._mouse_pressed.discard(name)
            self._on_up(name, x, y)

    def _on_down(self, name, x, y):
        eng = self.engine
        if eng.active_smart_plane_mode:
            eng.smart_analyzer.handle_mouse_click((x, y))
            return
        if name == "middle":
            self._middle_down(x, y)
        elif name == "right":
            self._right_down()
        elif name == "left":
            self._left_down(x, y)

    def _on_up(self, name, x, y):
        eng = self.engine
        if name == "left":
            self._left_up(x, y)
        elif name == "right":
            eng.pending_pick_check = False
        elif name == "middle":
            eng.pending_pick_check = False
            eng.clear_hover()

    def _left_down(self, x, y):
        eng = self.engine
        if eng.draw_mgr.is_active:
            eng.draw_mgr.on_mouse_click(x, y)
            return
        if eng.input.is_shift_pressed():
            return
        eng.marquee.start_selection(x, y)
        eng.update_world_pos(x, y)
        eng.start_hover_pick(int(x), int(y))

    def _left_up(self, x, y):
        eng = self.engine
        if eng.draw_mgr.is_active or eng.input.is_shift_pressed():
            return
        if eng.marquee.is_active:
            was_drag = eng.marquee.end_selection()
            if not was_drag:
                eng.handle_pick_from_hover(eng.input.is_ctrl_pressed())

    def _right_down(self):
        eng = self.engine
        if eng.hover_id > 0:
            element = eng.renderer.get_element_from_id(eng.hover_id)
            if element:
                self.toggle_panel("inspector")

    def _middle_down(self, x: float, y: float):
        eng = self.engine
        eng.pending_pick_check = False
        eng.clear_hover()
        if eng.input.begin_middle_click(x, y, time.time()):
            eng.fit_view()

    def _middle_move(self, dx, dy, x, y):
        eng = self.engine
        eng.input.update_middle_drag(x, y)
        if eng.input.is_shift_pressed():
            eng.cam.orbit(dx, dy)
        else:
            eng.cam.pan(dx, dy)
        eng.pending_pick_check = False
        eng.clear_hover()

    def _handle_move(self, x, y):
        eng = self.engine
        if eng is None or mouse_over_ui():
            return

        if eng.input:
            eng.input.update_mouse_position(x, y)
        dx = eng.input.mouse_delta.x if eng.input else 0
        dy = eng.input.mouse_delta.y if eng.input else 0

        self._sync_modifiers()

        # Plane Draw önceliği
        pdm = getattr(eng, "plane_draw_mgr", None)
        if pdm and pdm.is_active:
            pdm.on_mouse_move(x, y)
            eng.update_world_pos(x, y)
            eng.start_hover_pick(int(x), int(y))
            return

        if "middle" in self._mouse_pressed:
            self._middle_move(dx, dy, x, y)
            return
        if "left" in self._mouse_pressed and eng.input.is_shift_pressed():
            eng.cam.orbit(dx, dy)
            if eng.hover_id != 0:
                eng.clear_hover()
            return
        if eng.draw_mgr.is_active:
            eng.draw_mgr.on_mouse_move(x, y)
            return
        if "right" in self._mouse_pressed:
            return
        if eng.marquee and eng.marquee.is_active:
            eng.marquee.update_selection(x, y)
            return

        eng.update_world_pos(x, y)
        eng.start_hover_pick(int(x), int(y))

        if eng.active_smart_plane_mode:
            view = np.array(eng.cam.get_view_matrix(), dtype=float)
            proj = np.array(eng.cam.get_projection_matrix(), dtype=float)
            eng.smart_analyzer.handle_mouse_move(
                (x, y), view, proj,
                (self.window.fb_width, self.window.fb_height),
            )

    def _handle_scroll(self, xoffset, yoffset):
        eng = self.engine
        if eng is None or mouse_over_ui():
            return
        if yoffset > 0:
            eng.cam.zoom(1.0)
        elif yoffset < 0:
            eng.cam.zoom(-1.0)

    def _handle_key_down(self, key, scancode, mods):
        eng = self.engine
        if not eng:
            return
        self._sync_from_glfw_mods(mods)

        if keyboard_captured_by_ui():
            if key == glfw.KEY_ESCAPE:
                self._on_escape()
            return

        pdm = getattr(eng, "plane_draw_mgr", None)
        if pdm and pdm.is_active and pdm.on_key_press(key):
            return

        for entry in self.panels.values():
            panel = entry["instance"]
            handler = getattr(panel, "on_key_press", None)
            if (
                getattr(panel, "visible", False)
                and callable(handler)
                and handler(key)
            ):
                return

        if eng.input:
            eng.input.handle_key_down(key)

        if eng.active_smart_plane_mode and eng.smart_analyzer.handle_key_press(key):
            return

        self._dispatch_key(key, eng)

    def _handle_key_up(self, key, scancode):
        eng = self.engine
        if eng is None:
            return
        if eng.input:
            eng.input.handle_key_up(key)
        self._sync_modifiers()

    def _dispatch_key(self, key, eng):
        if key == glfw.KEY_ESCAPE:
            return self._on_escape()

        entry = self._key_shortcuts.get(key)
        if entry:
            panel_name, needs_ctrl, needs_shift = entry
            if (eng.input.is_ctrl_pressed() == needs_ctrl
                    and eng.input.is_shift_pressed() == needs_shift):
                self.toggle_panel(panel_name)
                return

        if key == glfw.KEY_F3:
            return eng.renderer.toggle_render_mode()
        if key == glfw.KEY_D and not eng.input.is_ctrl_pressed():
            return self._toggle_draw_mode()
        if key == glfw.KEY_W and eng.input.is_shift_pressed():
            return self._toggle_plane_draw()
        if key == glfw.KEY_C and eng.draw_mgr.is_active:
            return eng.draw_mgr.close()
        if key == glfw.KEY_L and not eng.input.is_ctrl_pressed():
            return self._toggle_loads_visibility()
        if key == glfw.KEY_DELETE:
            deleted, rejected = eng.sel_mgr.delete_selected()
            logger.info("[Key] Silindi=%s Reddedildi=%s", deleted, rejected)
            return

        if eng.input.is_ctrl_pressed():
            if key == glfw.KEY_J: return self.toggle_show_only()
            if key == glfw.KEY_Z: return eng.sel_mgr.undo()
            if key == glfw.KEY_Y: return eng.sel_mgr.redo()
            if key == glfw.KEY_S:
                return (self._save_as_project()
                        if eng.input.is_shift_pressed() else self._quick_save())
            if key == glfw.KEY_O: return self._on_toolbar_open()
            if key == glfw.KEY_E: return self._open_s2k_panel_export()

    def _on_escape(self) -> None:
        eng = self.engine
        if eng is None:
            return
        pdm = getattr(eng, "plane_draw_mgr", None)
        if pdm and pdm.is_active:
            pdm._step_back()
            return
        if eng.draw_mgr.is_active:
            eng.draw_mgr.cancel()
            return
        if eng.marquee and eng.marquee.is_active:
            eng.marquee.cancel_selection()
            eng.clear_hover()
            return
        eng.pending_pick_check = False
        eng.clear_hover()
        eng.sel_mgr.clear()

    # ==================================================================
    # HUD / YARDIMCI
    # ==================================================================
    def _draw_snap_indicator(self, w, h) -> None:
        if not self.engine:
            return
        snap = self.engine.snap
        if snap is None or not getattr(self.engine, "hover_visual_enabled", True):
            return
        mx, my = self.engine.input.mouse_pos.x, self.engine.input.mouse_pos.y
        if not self.engine.draw_mgr:
            return
        if self.engine.draw_mgr.is_active or self.engine.hover_id > 0:
            snap.draw_snap(
                mx, my, w, h, active=True,
                hover_node=self.engine.hover_element_type == "node",
            )

    def _draw_pdm_hud(self, pdm) -> None:
        stage_text = {
            pdm.STAGE_P0: "p0: İlk noktayı seç",
            pdm.STAGE_P1: "p1: U vektörünü belirle",
            pdm.STAGE_P2: "p2: V vektörünü belirle",
            pdm.STAGE_DEPTH_PLUS:  f"depth_plus: mouse yukarı/aşağı ({pdm.depth_plus:.0f}mm) — tıkla → sonraki",
            pdm.STAGE_DEPTH_MINUS: f"depth_minus: mouse aşağı/yukarı ({pdm.depth_minus:.0f}mm) — tıkla → onayla",
        }.get(pdm.stage, "")

        io = imgui.get_io()
        w, h = io.display_size
        imgui.set_next_window_pos(imgui.ImVec2(w / 2 - 200, 20))
        imgui.set_next_window_size(imgui.ImVec2(400, 40))
        imgui.push_style_var(
            imgui.StyleVar_.window_padding, imgui.ImVec2(8, 8)
        )
        try:
            expanded, _ = imgui.begin(
                "##pdm_hud", False,
                imgui.WindowFlags_.no_title_bar | imgui.WindowFlags_.no_resize |
                imgui.WindowFlags_.no_scrollbar | imgui.WindowFlags_.no_inputs,
            )
            try:
                if expanded:
                    imgui.text_colored(imgui.ImVec4(1.0, 0.9, 0.4, 1.0), stage_text)
            finally:
                imgui.end()
        finally:
            imgui.pop_style_var()

    def _on_resize(self, w, h) -> None:
        if self.engine:
            self.engine.resize(max(1, w), max(1, h))

    def _sync_modifiers(self) -> None:
        eng = self.engine
        if eng is None or eng.input is None:
            return
        eng.input.update_modifiers(sync_modifiers_from_glfw(self.window.window))

    def _sync_from_glfw_mods(self, mods: int) -> None:
        eng = self.engine
        if eng and eng.input:
            eng.input.update_modifiers(mods_to_dict(mods))

    def _load_section_catalog(self) -> None:
        from pathlib import Path

        from data.section_catalog import load_catalog_from_dir

        data_dir = Path(__file__).parent.parent / "data"
        try:
            self.section_catalog = load_catalog_from_dir(data_dir)
            logger.info("[CadApp] Kesit kataloğu: %d kesit", len(self.section_catalog))
        except Exception:
            logger.exception("[CadApp] Katalog yüklenemedi")
            self.section_catalog = {}

    # ==================================================================
    # SHUTDOWN
    # ==================================================================
    def shutdown(self) -> None:
        # CadWindow.shutdown() zaten ImGui/GLFW temizliğini yapıyor
        pass