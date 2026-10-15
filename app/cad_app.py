# app/cad_app.py
import os
import time
import glfw
from OpenGL.GL import *
import glm

from app.cad_window import CadWindow
from core.gl_engine import Engine
from app.event_router import EventRouter

from domain.definition import AreaUniformToFrameLoad, DistType, LoadDirection, UnitSystem
from domain.element import PolygonType
from ui.toolbar import Toolbar
from ui.main_menu import MainMenuPopup
from ui.file_dialog import ImGuiFileDialog
from ui.visibility_panel import VisibilityPanel
from ui.view_filter_panel import ViewFilterPanel
from ui.inspector_panel import InspectorPanel
from ui.zones_panel import ZonesPanel
from ui.definition_panel import DefinitionPanel
from ui.project_panels import ProjectInfoPanel, ProjectConfigPanel, AnalysisManagerPanel, ReportPanel
from ui.grid_panel import GridPanel
from ui.imgui_backend import UiBackend
from ui.load_assign_panel import LoadAssignPanel
from domain.element import Polygon
from domain.project import Project

from logging_config import CadLogger
logger = CadLogger.get(__name__)


class CadApp:
    def __init__(self, window: CadWindow):
        self.window = window
        self.engine = None
        self.initialized = False
        self._model_text = "MODEL: YENİ SAHNE"
        self.current_project = Project()  # Bütünsel Proje Nesnesi
        self.hover_visual_enabled = True

        # Paneller
        self.grid_panel = GridPanel(
                                    on_change=self._on_grid_change,
                                    on_work_plane_activate=self._on_work_plane_activate,
                                )
        self.inspector = InspectorPanel(on_apply = self._on_inspector_apply)
        self.main_menu = MainMenuPopup(on_action = self._on_main_menu_action)
        self.visibility_panel = VisibilityPanel(on_apply=self._on_visibility_applied)
        self.file_dialog = ImGuiFileDialog()
        self.view_filter = ViewFilterPanel(on_apply=self._on_view_filter_apply)
        self.zones_panel = ZonesPanel(on_run_analysis=self._on_run_wind_analysis,
                                      on_select_direction= self.on_select_wind_direction)
        
        # Yönetim Panelleri
        self.report_panel = ReportPanel()
        self.definition_panel = DefinitionPanel()
        self.project_info_panel = ProjectInfoPanel()
        self.project_config_panel = ProjectConfigPanel()
        self.analysis_panel = AnalysisManagerPanel()
        self.load_assign_panel = LoadAssignPanel(on_apply=self._apply_load_to_selected_polygon)


        self.ui_backend = UiBackend(window.window)
        self.ui_backend.setup()
        window._wire_callbacks()

        self.router = EventRouter(self)
        window.on_key_down = self.router.on_key_down
        window.on_key_up = self.router.on_key_up
        window.on_mouse_button = self.router.on_mouse_button
        window.on_mouse_move = self.router.on_mouse_move
        window.on_scroll = self.router.on_scroll
        window.on_resize = self._on_resize
        window.on_char = self.router.on_char
        window.on_focus = self.router.on_window_focus

        self.toolbar = Toolbar(
            callbacks={
                "menu": self._on_toolbar_menu,
                "open": self._on_toolbar_open,
                "save": self._on_toolbar_save,
                "draw": self._toggle_draw_mode,
                
                # --- Toggle Mantığına Uyarlanan Panel Callback'leri ---
                "visibility": lambda: self.visibility_panel.close() if self.visibility_panel.visible else self._on_toolbar_visibility(),
                "view_filter": self.toggle_view_filter_panel, # Bu zaten kendi içinde open/close yapıyor
                "grid": lambda: self.grid_panel.close() if self.grid_panel.visible else self.open_grid(),
                "grid_labels": lambda: setattr(self.engine.renderer.grid_labels, "enabled",
                                not self.engine.renderer.grid_labels.enabled),
                "inspector": lambda: self.inspector.close() if self.inspector.visible else self.open_inspector(),
                
                "render_mode": lambda: self.engine.renderer.toggle_render_mode() if self.engine and self.engine.renderer else None,
                "smart_plane": lambda: setattr(self.engine, "active_smart_plane_mode", not self.engine.active_smart_plane_mode) if self.engine else None,
                
                "definitions": lambda: self.definition_panel.close() if self.definition_panel.visible else self.definition_panel.open(self.current_project.definitions),
                "project_info": lambda: self.project_info_panel.close() if self.project_info_panel.visible else self.project_info_panel.open(self.current_project.info),
                "project_config": lambda: self.project_config_panel.close() if self.project_config_panel.visible else self.project_config_panel.open(self.current_project.config),
                "analysis": lambda: self.analysis_panel.close() if self.analysis_panel.visible else self.analysis_panel.open(self.current_project.analysis),
                "report": lambda: self.report_panel.close() if self.report_panel.visible else self.report_panel.open(self.current_project.report),
                
                "wind": lambda: self.zones_panel.close() if self.zones_panel.visible else self._on_toolbar_wind(),
                "on_unit_change": self.set_unit_system,
                "assign_area_load": lambda: self._toggle_load_assign_panel(),
                "distribute_polygon_loads": self._distribute_selected_polygon_loads,
                "local_axes": lambda: self._toggle_local_axes(),
                "local_axes_selected_only": self._toggle_local_axes_selected_only,
                "align_frames_to_polygon": self._align_frames_to_selected_polygons,
                "check_load_balance": self._check_load_balance,
                
            },
            panel_states={
                "visibility": lambda: self.visibility_panel.visible,
                "view_filter": lambda: self.view_filter.visible,
                "grid": lambda: self.grid_panel.visible,
                "inspector": lambda: self.inspector.visible,
                "smart_plane": lambda: getattr(self.engine, "active_smart_plane_mode", False) if self.engine else False,
                "report": lambda: self.report_panel.visible,
                "definitions": lambda: self.definition_panel.visible,
                "project_info": lambda: self.project_info_panel.visible,
                "project_config": lambda: self.project_config_panel.visible,
                "analysis": lambda: self.analysis_panel.visible,
                "wind": lambda: self.zones_panel.visible,
                "assign_area_load": lambda: self.load_assign_panel.visible,
                "local_axes": lambda: self.engine.scene.show_local_axes if self.engine and self.engine.scene else False,
                "local_axes_selected_only": lambda: self.engine.scene.show_local_axes_for_selected if self.engine and self.engine.scene else True,
            }
        )

        import queue
        self._wind_queue = queue.Queue()
        
        # Zones panel callback'i
        self.zones_panel.on_run_analysis = self._on_run_wind_analysis
        self.show_loads = True

    def _ensure_engine(self):
        if self.initialized:
            return
        w, h = self.window.fb_width, self.window.fb_height
        if w <= 1 or h <= 1:
            return
        try:
            logger.info("[INIT] Engine başlıyor...")
            self.engine = Engine(w, h)
            self.engine.init_gl()
            self.engine.on_hover_changed_callback = self._on_hover_changed
            self.engine.sel_mgr.on_selection_changed = self._on_selection_changed
            self.initialized = True
            logger.info("Engine ilklendirildi.")
        except Exception:
            logger.exception("INIT HATASI")
            self.initialized = True

    def frame(self, dt):
        self._ensure_engine()
        if not self.initialized:
            return

        self.ui_backend.begin_frame()

        draw_active = bool(self.engine and self.engine.draw_mgr and self.engine.draw_mgr.is_active)
        current_unit = self.current_project.unit_system if self.current_project else None
        self.toolbar.draw(model_text=self._model_text, draw_active=draw_active, current_unit=current_unit)


        self.file_dialog.draw()
        self.router.process_pending()
        
        # Rüzgar analizi kuyruk kontrolü
        self._process_wind_queue()

        # Sahne kirli (dirty) ise GPU'yu güncelle ve temizle
        active_scene = self.engine.scene if self.engine else None
        if active_scene and hasattr(active_scene, 'is_dirty') and active_scene.is_dirty():
            if self.engine.renderer:
                self.engine.renderer.update_geo(active_scene)
            active_scene.clear_dirty()
            
        # Sahne çizimi
        self._render_scene(dt)

        # Tüm aktif/görünür panelleri tek bir metod altında yönetelim
        self._draw_panels()
        

        self.ui_backend.end_frame()

        # Pick kontrolü
        if self.engine and self.engine.pending_pick_check:
            self.engine.check_pick_result()

    def _draw_panels(self):
        """Sadece görünür (açık) olan panelleri render döngüsüne sokar."""
        self.main_menu.draw()
        self.visibility_panel.draw()
        self.view_filter.draw()
        self.inspector.draw()
        self.zones_panel.draw()
        
        # Yönetim ve Araç Panelleri (BasePanel altındaki visible kontrolü zaten kapalıyken çizimi engeller)
        self.report_panel.draw()
        self.definition_panel.draw()
        self.project_info_panel.draw()
        self.project_config_panel.draw()
        self.analysis_panel.draw()
        self.grid_panel.draw()
        self.load_assign_panel.draw()

    def _render_scene(self, dt):
        w, h = self.window.fb_width, self.window.fb_height
        glViewport(0, 0, w, h)

        try:
            glEnable(GL_DEPTH_TEST)
            glClearColor(0.08, 0.10, 0.16, 1.0)
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

            self.engine.renderer.set_dt(dt)
            self.engine.renderer.render(self.engine.cam)
            
            # Snap ve Hover göstergeleri (Yedek koddan geri eklendi)
            self._draw_snap_indicator(w, h)

            if self.engine.draw_mgr.is_active:
                mvp = (self.engine.cam.get_projection_matrix()
                       @ self.engine.cam.get_view_matrix())
                self.engine.draw_mgr.render_preview(mvp, self.engine.preview_s)

            if self.engine.active_smart_plane_mode:
                self.engine.smart_analyzer.render()
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

    def _draw_grid_labels(self):
        """Grid etiketlerini 2D overlay olarak çizer."""
        if not self.engine or not self.engine.renderer:
            return
        if not getattr(self.engine.renderer.show, 'grid', False):
            return
        
        grid = self.engine.renderer.grid
        if grid is None:
            return
        
        cam = self.engine.cam
        if cam is None:
            return
        
        # 3D grid ile aynı mvp (model_mat dahil)
        mvp = (cam.get_projection_matrix()
            * cam.get_view_matrix()
            * self.engine.renderer.model_mat)
        
        w, h = self.window.fb_width, self.window.fb_height
        self.engine.renderer.grid_labels.draw(grid, mvp, w, h)

    def _draw_snap_indicator(self, w, h):
        snap = self.engine.snap
        if snap is None:
            return
        if not getattr(self.engine, "hover_visual_enabled", True):
            return

        inp = self.engine.input
        mx = inp.mouse_pos.x
        my = inp.mouse_pos.y

        if self.engine.draw_mgr.is_active:
            snap.draw_snap(mx, my, w, h, active=True)
            return

        if self.engine.hover_id > 0:
            snap.draw_snap(mx, my, w, h, active=True)

    def _on_resize(self, w, h):
        if self.engine:
            self.engine.resize(max(1, w), max(1, h))

    def _on_toolbar_open(self):
        self.file_dialog.open(
            mode="open", filters=[".cd4"], title="Proje Aç (.cd4)",
            initial_dir=os.getcwd(), on_select=self._load_project
        )

    def _on_toolbar_save(self):
        self.file_dialog.open(
            mode="save", filters=[".cd4"], title="Projeyi Kaydet (.cd4)",
            initial_dir=os.getcwd(), default_name="model_projesi.cd4",
            on_select=self._save_project
        )

    def _load_project(self, path: str):
        try:
            project = Project.load(path)
            self.set_project(project)
            if self.engine:
                self.engine.fit_view()
            self._model_text = f"MODEL: {os.path.basename(path)}"
            logger.info("[File] Proje yüklendi: %s", path)
        except Exception:
            logger.exception("Proje yükleme hatası")

    

    def _on_toolbar_visibility(self):
        if self.visibility_panel.visible:
            self.visibility_panel.close()
        else:
            scene = self.engine.scene if self.engine else (self.current_project.scene if self.current_project else None)
            self.visibility_panel.open(scene)

    def _on_toolbar_wind(self):
        if self.zones_panel.visible:
            self.zones_panel.close()
        else:
            scene = self.engine.scene if self.engine else (self.current_project.scene if self.current_project else None)
            # Rüzgar analiz yöneticisini (WindAnalysisResult) panele bağlıyoruz ki ağlamasın :)
            wind_analysis_data = self.current_project.analysis.wind
            self.zones_panel.open(scene=scene, wind_analysis=wind_analysis_data)

    def _toggle_draw_mode(self):
        if self.engine and self.engine.draw_mgr:
            if self.engine.draw_mgr.is_active:
                self.engine.draw_mgr.close()
            else:
                self.engine.draw_mgr.start()

    def _toggle_local_axes(self):
        if not self.engine or not self.engine.renderer:
            return
        self.engine.renderer.toggle_local_axes()

    def _toggle_local_axes_selected_only(self):
        if not self.engine or not self.engine.renderer:
            return
        self.engine.renderer.toggle_local_axes_selected_only()

    def _on_main_menu_action(self, key: str):
        """Ana menüden bir öğe seçildi."""
        logger.info("[Menu] Aksiyon: %s", key)

        dispatch = {
            "inspector":    self.inspector.open_element,
            # "analysis":     self._menu_open_analysis,
            "new_project":  self._menu_new_project,
            "open_project": self._on_toolbar_open,
            "save_project": self._on_toolbar_save,
            "import_s2k":   self._menu_import_s2k,
            "visibility":   self._on_toolbar_visibility,
        }
        fn = dispatch.get(key)
        if callable(fn):
            fn()

    def _menu_import_s2k(self):
        """S2K import — ImGui dosya seçici ile."""
        self.file_dialog.open(
            mode="open",
            filters=[".s2k", ".S2K", ".$2k"],
            title="S2K İçe Aktar",
            initial_dir=os.getcwd(),
            on_select=self._import_s2k,
        )

    def _menu_new_project(self):
        """Yepyeni boş bir proje başlatır."""
        self.set_project(Project())
        self._model_text = "MODEL: YENİ SAHNE"
        logger.info("[Project] Yeni proje oluşturuldu.")

    def _import_s2k(self, path, merge_to_current=False):
        """
        Seçilen S2K dosyasını yükler. 
        merge_to_current=True ise mevcut projeye ekler, False ise yeni proje başlatır.
        """
        try:
            from tools.s2kloader import S2KLoader
            logger.info("[S2K] Yükleniyor: %s (Merge: %s)", path, merge_to_current)

            loader = S2KLoader(path)
            if merge_to_current and self.current_project and self.current_project.scene:
                # Mevcut projeye yükleme yapmak için geçici bir proje açıp loader'a veriyoruz
                temp_project = Project()
                loaded_project = loader.load(temp_project)
                
                if loaded_project and loaded_project.scene:
                    current_scene = self.current_project.scene
                    
                    # Elemanları mevcut sahneye aktar
                    for n_id, node in loaded_project.scene.nodes.items():
                        current_scene.nodes[n_id] = node
                    for f_id, frame in loaded_project.scene.frames.items():
                        current_scene.frames[f_id] = frame
                    for a_id, area in loaded_project.scene.areas.items():
                        current_scene.areas[a_id] = area
                        
                    if self.engine:
                        self.engine.renderer.update_geo(current_scene)
                    logger.info("[S2K] Mevcut projeye elemanlar başarıyla eklendi.")
            else:
                # Yepyeni proje olarak yükle (S2KLoader zaten Project döndürüyor)
                loaded_project = loader.load()
                if loaded_project is None or not loaded_project.scene:
                    logger.warning("[S2K] Yüklenen proje boş")
                    return

                # Sahne toplam eleman kontrolü
                scene = loaded_project.scene
                total = sum(len(getattr(scene, coll, {}) or {})
                            for coll in ("nodes", "frames", "areas", "links", "polygons"))
                logger.info("[S2K] Proje yüklendi. Toplam eleman: %d", total)

                if total == 0:
                    logger.warning("[S2K] Dosya boş, sahne değiştirilmedi")
                    return

                # Merkezi set_project metodu ile tüm panelleri ve engine'i besle
                self.set_project(loaded_project)
                self._model_text = f"MODEL: {os.path.basename(path)}"

        except Exception:
            logger.exception("[S2K] Yükleme/İçe aktarma hatası: %s", path)

    def _on_selection_changed(self, selected_elements):
        if self.engine and self.engine.renderer:
            self.engine.renderer.update_sel()
        if not self.inspector.visible:
            return
        if len(selected_elements) == 1:
            self.inspector.open_element(selected_elements[0])
        elif len(selected_elements) > 1:
            self.inspector.open_multi(selected_elements)
        else:
            self.inspector.clear()

    def _on_hover_changed(self, element):
        pass

    def _on_inspector_apply(self, target, values):
        from ui.adapters import values_to_element
        if isinstance(target, list):
            for el in target:
                values_to_element(el, values)
        else:
            values_to_element(target, values)
        if self.engine and self.engine.scene:
            self.engine.renderer.update_geo(self.engine.scene)

    def _on_visibility_applied(self):
        if self.engine and self.engine.scene:
            self.engine.renderer.update_geo(self.engine.scene)

    def _on_view_filter_apply(self, mode, min_s, max_s):
        """
        mode: "off" | "range" | "before" | "after"
        min_s, max_s: kullanıcı skalerleri (mm)
        """
        if not self.engine:
            return

        cam = self.engine.cam
        grid = self.engine.grid

        if mode == "off":
            cam.clear_section_filter()
        else:
            # Aktif UCS: user plane varsa ondan, yoksa global XY'den
            normal, origin = self._get_active_ucs_plane()
            if mode == "range":
                cam.set_section_filter(normal, origin, min_s, max_s)
            elif mode == "before":
                cam.set_section_filter(normal, origin, -1e30, max_s)
            elif mode == "after":
                cam.set_section_filter(normal, origin, min_s, 1e30)

        # Sahneyi yeniden filtrele
        self.engine.renderer.apply_plane_filter(cam)


    def _get_active_ucs_plane(self):
        """Aktif UCS'nin (normal, origin) döner."""
        grid = self.engine.grid
        if grid.active_user_plane:
            pdef = grid.get_user_plane(grid.active_user_plane)
            if pdef:
                return pdef.normal, pdef.origin
        # Varsayılan: global XY
        return (0.0, 0.0, 1.0), (grid.origin.x, grid.origin.y, grid.origin.z)
    def _on_run_wind_analysis(self):
        pass

    def _on_toolbar_menu(self):
        self.main_menu.open()
        logger.info("[Toolbar] Menü açılıyor")

    def open_grid(self):
        """Tanımlar sekmesini aç."""
        self.grid_panel.open(self.engine.renderer.grid, self.engine.cam)

    def open_inspector(self, element= None):
        """Seçilen eleman için inspector panelini aç."""
        # if element is None:
        #     return
        self.inspector.open_element(element)

    def open_definitions(self):
        """Tanımlar sekmesini aç."""
        self.definition_panel.open()

    def toggle_view_filter_panel(self):
        """View filter panelini aç/kapa."""
        if self.view_filter.visible:
            self.view_filter.close()
        else:
            self.view_filter.open(self.engine.cam if self.engine else None)
    def _on_run_wind_analysis(self):
        """Rüzgar analizi asenkron tetikleyici."""
        import threading
        from tools.wind_service import WindSceneAdapter

        logger.info("[Zones] Rüzgar analizi başlatılıyor...")
        # İsteğe bağlı bir yüklenme durumu veya log gösterilebilir
        
        def _async():
            try:
                scene = self.engine.scene if self.engine else self.current_project.scene
                if not scene:
                    self._wind_queue.put(("error", "Analiz için aktif sahne bulunamadı."))
                    return
                    
                zones = WindSceneAdapter.run_wind_analysis_and_update_scene(
                    scene=scene,
                    w_dir= [1,0,0],      # Varsayılan rüzgar yönü veya ayarlardan alınabilir
                    engine_kwargs={},
                    
                )
                self._wind_queue.put(("done", len(zones)))
            except Exception as e:
                logger.error(f"Rüzgar analizi hatası: {e}", exc_info=True)
                self._wind_queue.put(("error", str(e)))

        threading.Thread(target=_async, daemon=True).start()

    def _process_wind_queue(self):
        """Thread'den gelen rüzgar analizi sonuçlarını ana thread'de (frame içinde) işle."""
        import queue
        try:
            while True:
                msg_type, data = self._wind_queue.get_nowait()
                if msg_type == "done":
                    zone_count = data
                    logger.info(f"{zone_count} adet rüzgar bölgesi oluşturuldu")
                    if self.engine and self.engine.renderer:
                        scene = self.engine.scene
                        if scene:
                            self.engine.renderer.update_geo(scene)
                            # Paneli güncel sahne ile tazele
                            self.zones_panel.open(scene)
                elif msg_type == "error":
                    logger.error(f"Rüzgar Hesabı Hatası: {data}")
                self._wind_queue.task_done()
        except queue.Empty:
            pass

    def on_select_wind_direction(self, w_dir: tuple):
        """
        Kullanıcı rüzgar yönleri panelinden bir yön seçtiğinde tetiklenir.
        O yöne ait sonuçları sahneye yansıtır, yoksa analizi çalıştırır.
        """
        if not self.current_project or not self.engine:
            return

        # 1. Projedeki rüzgar analiz sonuçlarında bu yön var mı kontrol et
        wind_res = self.current_project.analysis.wind
        wind_res.active_direction = w_dir
        
        dir_key = str(w_dir)
        
        # Eğer bu yön için daha önce hesaplanmış sonuçlar varsa onları yükle,
        # yoksa o an bu yön için rüzgar analizini çalıştırıp sonuçları kaydet.
        from tools.wind_service import WindSceneAdapter
        
        # Sahnedeki eski rüzgar zone poligonlarını ve node'larını temizle
        old_zone_ids = [
            pid for pid, poly in self.current_project.scene.polygons.items() 
            if getattr(poly, "poly_type", None) == PolygonType.ZONE or poly.label.startswith("ZONE_")
        ]
        for pid in old_zone_ids:
            poly = self.current_project.scene.polygons.pop(pid, None)
            if poly:
                for node in poly.nodes:
                    if node.label.startswith("W_NODE_") and node.unique_id in self.current_project.scene.nodes:
                        self.current_project.scene.nodes.pop(node.unique_id, None)

        # Seçilen yön için adapter üzerinden analizi çalıştır ve sahneye/projelere işle
        WindSceneAdapter.run_wind_analysis_and_update_scene(
            scene=self.current_project.scene,
            w_dir=w_dir
        )
        
        # Ekranı güncellemeyi tetikle
        self.engine.set_scene(self.current_project.scene)

    # Grid ve kamera bağlantısı
    def _on_grid_change(self):
        """Grid değişince SADECE grid sistemini ve kamerayı yenile (sahneyi rahat bırak)."""
        if self.engine and self.engine.grid:
            self.engine.grid.rebuild_all()
            if self.engine.cam and self.grid_panel.grid:
                center, size = self.grid_panel.grid.get_bounds()
                self.engine.cam.update_bounds(center, size)

    def set_unit_system(self, unit_system: UnitSystem):
        """Global birim sistemini değiştirir ve sistemi günceller."""
        if self.current_project:
            self.current_project.unit_system = unit_system
        
        logger.info(f"[Units] Birim sistemi değiştirildi: {unit_system.name} ({unit_system.force_unit}, {unit_system.length_unit})")
        
        # Grid spacing veya birim-bağımlı arayüz elemanları güncellenebilir
        if self.engine and self.engine.grid:
            # Örneğin birim metre tabanlıdan mm tabanlıya geçerse grid boyutları ölçeklenebilir
            self.engine.grid.rebuild_all()

    def set_project(self, project: Project):
        """Proje nesnesini sisteme uygular, verileri panellere ve grid sistemine dağıtır."""
        self.current_project = project
        if self.engine:
            self.engine.set_scene(project.scene)
            if hasattr(project, "grid") and project.grid and self.engine.grid:
                g_conf = project.grid
                self.engine.grid.set_coords(g_conf.x_coords, g_conf.y_coords, g_conf.z_coords)
                self.engine.grid.set_origin(g_conf.origin_x, g_conf.origin_y, g_conf.origin_z)
                for plane_name, vis in g_conf.planes_visibility.items():
                    from domain.definition import GridPlane
                    try:
                        self.engine.grid.set_plane(GridPlane[plane_name], visible=vis)
                    except KeyError:
                        pass
                center, size = self.engine.grid.get_bounds()
                self.engine.cam.update_bounds(center, size)
                self.engine.cam.focus_on_model()
        self.inspector.scene = project.scene
        self.visibility_panel.scene = project.scene
        if self.view_filter:
            self.view_filter.ucs_name = "Global XY"

    def _save_project(self, path: str):
        try:
            if self.engine and self.engine.scene:
                self.current_project.scene = self.engine.scene
                if hasattr(self.engine.scene, "def_mgr"):
                    self.current_project.definitions = self.engine.scene.def_mgr
                
                if self.engine.grid and hasattr(self.current_project, "grid") and self.current_project.grid:
                    g = self.engine.grid
                    g_conf = self.current_project.grid
                    g_conf.x_coords = g.x_coords
                    g_conf.y_coords = g.y_coords
                    g_conf.z_coords = g.z_coords
                    g_conf.origin_x = g.origin.x
                    g_conf.origin_y = g.origin.y
                    g_conf.origin_z = g.origin.z
                    g_conf.planes_visibility = {plane.name: p["visible"] for plane, p in g.planes.items()}
            
            self.current_project.save(path)
            self.current_file_path = path  # <-- Aktif dosya yolunu sakla
            self._model_text = f"MODEL: {os.path.basename(path)}"
            logger.info("[File] Proje kaydedildi: %s", path)
        except Exception:
            logger.exception("Proje kaydetme hatası")

    def _quick_save(self):
        if not self.current_file_path:
            self._on_toolbar_save()  # Yol yoksa dialog aç
        else:
            self._save_project(self.current_file_path)  # Üzerine yaz (overwrite)

    def _save_as_project(self):
        self._on_toolbar_save()  # Her zaman dialog aç (Save As)

    def set_work_plane_view(self, plane_def):
        """Work plane'i aktifleştir + kamerayı ona dik getir."""
        if not self.engine:
            return

        from domain.definition import GridPlane
        # Aktif plane'i grid'e işle
        self.engine.grid.set_active_user_plane(plane_def.name)

        # Kamera
        origin, u, v, n = plane_def.get_uv_frame()
        fit_r = max(plane_def.count_u * plane_def.spacing_u,
                    plane_def.count_v * plane_def.spacing_v) * 1.2
        self.engine.cam.look_at_plane(origin, u, v, n, fit_radius=fit_r)

        # Grid'i yenile (aktif user plane çizilsin)
        self.engine.grid.rebuild_all()

        if self.view_filter.visible:
            self.view_filter.ucs_name = plane_def.name

    def _on_work_plane_activate(self, pdef):
        self.set_work_plane_view(pdef)
        if self.view_filter and self.view_filter.visible:
            self.view_filter.ucs_name = pdef.name
            # Section filter aktifse yeniden uygula — yeni UCS'ye göre
            if self.view_filter._section_mode != "off":
                self._on_view_filter_apply(
                    self.view_filter._section_mode,
                    self.view_filter._section_min,
                    self.view_filter._section_max,
                )


    def create_work_plane_from_selection(self):
        """Seçili frame'den eğik work plane oluştur, kamera oraya hizalansın."""
        if not self.engine or not self.engine.scene:
            return False

        selected = self.engine.scene.get_selected()
        if not selected:
            logger.info("[WorkPlane] Seçili eleman yok.")
            return False

        # Sadece frame kabul et (şimdilik)
        from domain.element import Frame
        frames = [e for e in selected if isinstance(e, Frame)]
        if not frames:
            logger.info("[WorkPlane] Seçili frame yok.")
            return False

        frame = frames[0]
        return self._build_work_plane_from_frame(frame)


    def _build_work_plane_from_frame(self, frame):
        """Verilen frame'den GridPlaneDef üret, ekle, aktifleştir, kamerayı hizala."""
        import glm
        from domain.definition import GridPlaneDef

        origin = frame.get_midpoint()
        u_axis = glm.vec3(*frame.get_axis())

        # Normal seçimi: U dünya Z'sine çok yakınsa (dikey çubuk) global Y kullan,
        # değilse global Z kullan (yatay/eğik çubuk)
        world_z = glm.vec3(0.0, 0.0, 1.0)
        world_x = glm.vec3(1.0, 0.0, 0.0)

        if abs(glm.dot(u_axis, world_z)) > 0.95:
            # Dikey çubuk → normal olarak dünya Y'yi kullan
            ref = glm.vec3(0.0, 1.0, 0.0)
        else:
            # Yatay/eğik çubuk → normal olarak dünya Z'yi kullan
            ref = world_z

        # Normal = U'ya dik, ref'e en yakın yön
        normal = ref - u_axis * glm.dot(ref, u_axis)
        if glm.length(normal) < 1e-6:
            # Dejenere — yedek
            normal = world_x - u_axis * glm.dot(world_x, u_axis)
        normal = glm.normalize(normal)

        # V ekseni = cross(normal, U) — Frame'in "yukarı" ekseni (grid'in V yönü)
        v_axis = glm.cross(normal, u_axis)

        # Grid boyutu frame uzunluğuna göre
        length = frame.get_length() or 1000.0
        spacing = max(100.0, length / 10.0)  # en az 100 mm, kabaca 10 hücre

        pdef = GridPlaneDef(
            name=f"FRAME-{frame.element_id}",
            origin=(origin[0], origin[1], origin[2]),
            normal=(normal.x, normal.y, normal.z),
            u_axis=(u_axis.x, u_axis.y, u_axis.z),
            spacing_u=spacing,
            spacing_v=spacing,
            count_u=10,
            count_v=10,
            visible=True,
            color=(0.6, 0.55, 0.75),   # hafif mor — kullanıcı tanımlı olduğu belli olsun
        )

        # Grid'e ekle + aktif et
        self.engine.grid.add_user_plane(pdef)
        self.engine.grid.set_active_user_plane(pdef.name)

        # Kamerayı düzleme dik getir
        fit_r = max(pdef.count_u * spacing, pdef.count_v * spacing) * 1.3
        self.engine.cam.look_at_plane(
            origin=pdef.origin,
            u=pdef.u_axis,
            v=(v_axis.x, v_axis.y, v_axis.z),
            n=pdef.normal,
            fit_radius=fit_r,
        )

        # Grid'i yenile
        self.engine.grid.rebuild_all()

        # Panel'i bilgilendir (açıksa güncellensin)
        if self.grid_panel.visible:
            self.grid_panel.grid = self.engine.grid

        logger.info(f"[WorkPlane] '{pdef.name}' oluşturuldu "
                    f"(uzunluk={length:.0f}, spacing={spacing:.0f})")
        return True

    def _toggle_load_assign_panel(self):
        if self.load_assign_panel.visible:
            self.load_assign_panel.close()
        else:
            # Güncel load pattern isimlerini definitions içinden alıp panele verelim
            patterns = list(self.current_project.definitions.load_patterns.keys()) if hasattr(self.current_project.definitions, "load_patterns") else ["DEAD", "LIVE"]
            if not patterns:
                patterns = ["DEAD", "LIVE"]
            self.load_assign_panel.open(load_patterns=patterns)

    def _apply_load_to_selected_polygon(self, pattern_name: str, value: float, direction, dist_type):
        """Ekranda seçili olan poligona (Polygon tipindekilere) yükü assign eder."""
        if not self.engine or not self.engine.scene:
            logger.warning("[Assign] Aktif sahne bulunamadı.")
            return

        selected = self.engine.scene.get_selected()
        polygons = [e for e in selected if isinstance(e, Polygon) and getattr(e, "poly_type", None) == PolygonType.SURFACE]
        
        if not polygons:
            logger.info("[Assign] Seçili geçerli bir Surface Polygon bulunamadı.")
            return

        count = 0
        for poly in polygons:
            # Doğrudan polygon içine yükü ekliyoruz
            poly.add_uniform_to_frame_load(
                pattern_name=pattern_name,
                value=value,
                direction=direction,
                dist_type=dist_type
            )
            count += 1

        # Sahneyi ve renderer'ı güncelle
        self.engine.renderer.update_geo(self.engine.scene)
        logger.info(f"[Assign] {count} adet poligona '{pattern_name}' (Değer: {value}) yükü atandı.")

    def _distribute_selected_polygon_loads(self):
        """Ekranda seçili olan poligon üzerindeki alan yüklerini çevreleyen frame'lere dağıtır."""
        if not self.engine or not self.engine.scene:
            logger.warning("[Distribute] Aktif sahne bulunamadı.")
            return

        selected = self.engine.scene.get_selected()
        from domain.element import Polygon, PolygonType
        polygons = [e for e in selected if isinstance(e, Polygon) and getattr(e, "poly_type", None) == PolygonType.SURFACE]

        if not polygons:
            logger.info("[Distribute] Seçili geçerli bir Surface Polygon bulunamadı.")
            return

        from tools.load_distribution_service import LoadDistributionService
        total_assigned = 0
        for poly in polygons:
            count = LoadDistributionService.distribute_polygon_loads(self.engine.scene, poly, target_step=200.0)
            total_assigned += count

        self.engine.renderer.update_geo(self.engine.scene)
        logger.info(f"[Distribute] Seçili poligonlardaki yükler başarıyla {total_assigned} adet frame'e dağıtıldı.")

    def _toggle_local_axes(self):
        if not self.engine or not self.engine.scene: return
        sc = self.engine.scene
        sc.show_local_axes = not sc.show_local_axes
        logger.info(f"[Axes] Local axes: {sc.show_local_axes}")

    def _align_frames_to_polygon_planes(self):
        """
        Seçili polygon(lar) üzerindeki/çevresindeki frame'leri, 
        poligon düzlemi normaline göre local 3-ekseni hizalar.
        """
        from domain.local_axes import align_frame_to_polygon, polygon_plane_axes
        from domain.element import Polygon, PolygonType, Frame
        
        scene = self.engine.scene
        selected = scene.get_selected()
        polygons = [e for e in selected 
                    if isinstance(e, Polygon) 
                    and e.poly_type == PolygonType.SURFACE]
        if not polygons:
            logger.warning("[Align] Seçili surface polygon yok.")
            return
        
        affected = 0
        for poly in polygons:
            u, v, n = polygon_plane_axes(poly.nodes)
            # Poligon düzleminde olan frame'leri bul
            for frame in scene.frames.values():
                mid = frame.get_midpoint()
                # Midpoint polygon düzleminde mi? (nokta-düzlem mesafesi)
                d = glm.dot(glm.vec3(mid[0]-poly.nodes[0].x,
                                    mid[1]-poly.nodes[0].y,
                                    mid[2]-poly.nodes[0].z), n)
                if abs(d) < 10.0:  # 10 mm tolerans
                    # Frame 1-ekseni polygon düzleminde mi?
                    e1 = glm.vec3(*frame.get_axis())
                    if abs(glm.dot(e1, n)) < 0.99:  # düşey frame'leri atla
                        align_frame_to_polygon(frame, poly.nodes, (u, v, n))
                        affected += 1
        
        logger.info(f"[Align] {affected} frame hizalandı.")
        self.engine.renderer.update_geo(scene)

    def _align_frames_to_selected_polygons(self):
        """
        Seçili polygon(lar)ın düzlemindeki frame'leri poligon normaline hizalar.
        """
        if not self.engine or not self.engine.scene:
            logger.warning("[Align] Aktif sahne yok.")
            return

        from domain.element import Polygon, PolygonType
        scene = self.engine.scene
        selected = scene.get_selected()

        polygons = [
            e for e in selected
            if isinstance(e, Polygon) and e.poly_type == PolygonType.SURFACE
        ]
        if not polygons:
            logger.info("[Align] Seçili Surface Polygon yok.")
            return

        from tools.alignment_service import AlignmentService
        n = AlignmentService.align_frames_to_polygons(
            scene=scene,
            polygons=polygons,
            tolerance=10.0,
            skip_vertical=True,
        )

        if n > 0:
            self.engine.renderer.update_geo(scene)
        logger.info(f"[Align] Toplam {n} frame hizalandı.")

    def _check_load_balance(self):
        """
        Tüm polygonlar için yük dengesini kontrol eder.
        Log'a rapor basar, özet bilgi döner.
        """
        if not self.engine or not self.engine.scene:
            logger.warning("[LoadBalance] Aktif sahne yok.")
            return

        from tools.load_balance_report import LoadBalanceReport

        scene = self.engine.scene
        failed = LoadBalanceReport.log_report(scene, tolerance_ratio=0.005)

        if failed == 0:
            logger.info("[LoadBalance] ✓ Tüm poligon yükleri dengede.")
        else:
            logger.warning(f"[LoadBalance] ✗ {failed} pattern başarısız — kontrol edin.")

    def _toggle_selected_visibility(self):
        if not self.engine or not self.engine.scene:
            return
        selected = self.engine.scene.get_selected()
        if not selected:
            logger.info("[Visibility] Seçili eleman yok.")
            return
        for el in selected:
            el.is_visible = not getattr(el, "is_visible", True)
        self.engine.renderer.update_geo(self.engine.scene)
        logger.info(f"[Visibility] {len(selected)} elemanın görünürlüğü değiştirildi.")

    def _toggle_loads_visibility(self):
        self.show_loads = not self.show_loads
        if self.engine and self.engine.renderer:
            if hasattr(self.engine.renderer, "show_loads"):
                self.engine.renderer.show_loads = self.show_loads
        logger.info(f"[Loads] Yük görünürlüğü: {'Açık' if self.show_loads else 'Kapalı'}")

    def shutdown(self):
        self.ui_backend.shutdown()