# app/cad_app.py
import os
import time
import glfw
from OpenGL.GL import *

from app.cad_window import CadWindow
from core.gl_engine import PureKivyEngine
from app.event_router import EventRouter

from domain.element import PolygonType
from ui.toolbar import Toolbar
from ui.main_menu import MainMenuPopup
from ui.file_dialog import ImGuiFileDialog
from ui.visibility_panel import VisibilityPanel
from ui.view_filter_panel import ViewFilterPanel
from ui.inspector_panel import InspectorPanel
from ui.zones_panel import ZonesPanel
from ui.definition_panel import DefinitionPanel
from ui.project_panels import ProjectInfoPanel, ProjectConfigPanel, AnalysisManagerPanel
from ui.imgui_backend import UiBackend
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
        self.inspector = InspectorPanel(on_apply = self._on_inspector_apply)
        self.main_menu = MainMenuPopup(on_action = self._on_main_menu_action)
        self.visibility_panel = VisibilityPanel(on_apply=self._on_visibility_applied)
        self.file_dialog = ImGuiFileDialog()
        self.view_filter = ViewFilterPanel(on_apply=self._on_view_filter_apply)
        self.zones_panel = ZonesPanel(on_run_analysis=self._on_run_wind_analysis,
                                      on_select_direction= self.on_select_wind_direction)
        
        # Yönetim Panelleri
        self.definition_panel = DefinitionPanel()
        self.project_info_panel = ProjectInfoPanel()
        self.project_config_panel = ProjectConfigPanel()
        self.analysis_panel = AnalysisManagerPanel()


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

        self.toolbar = Toolbar({
            "menu": self._on_toolbar_menu,
            "open": self._on_toolbar_open,
            "save": self._on_toolbar_save,
            "draw": self._toggle_draw_mode,
            "definitions": lambda: self.definition_panel.open(self.current_project.definitions),
            "project_info": lambda: self.project_info_panel.open(self.current_project.info),
            "project_config": lambda: self.project_config_panel.open(self.current_project.config),
            "analysis": lambda: self.analysis_panel.open(self.current_project.analysis),
            "report": lambda: self.report_panel.open(self.current_project.report),
            "visibility": self._on_toolbar_visibility,
            "wind": self._on_toolbar_wind,
        })

        import queue
        self._wind_queue = queue.Queue()
        
        # Zones panel callback'i
        self.zones_panel.on_run_analysis = self._on_run_wind_analysis

    def _ensure_engine(self):
        if self.initialized:
            return
        w, h = self.window.fb_width, self.window.fb_height
        if w <= 1 or h <= 1:
            return
        try:
            logger.info("[INIT] Engine başlıyor...")
            self.engine = PureKivyEngine(w, h)
            self.engine.init_gl()
            self.engine.on_hover_changed_callback = self._on_hover_changed
            self.engine.sel_mgr.on_selection_changed = self._on_selection_changed
            self.initialized = True
            logger.info("Engine ilklendirildi.")
        except Exception:
            logger.exception("INIT HATASI")
            self.initialized = True

    def set_project(self, project: Project):
        """Proje nesnesini sisteme uygular, verileri panellere dağıtır."""
        self.current_project = project
        if self.engine:
            self.engine.set_scene(project.scene)
        
        # Panelleri besle
        self.inspector.scene = project.scene
        self.visibility_panel.scene = project.scene
        self.definition_panel.open(project.definitions)
        self.project_info_panel.open(project.info)
        self.project_config_panel.open(project.config)
        self.analysis_panel.open(project.analysis)


    def frame(self, dt):
        self._ensure_engine()
        if not self.initialized:
            return

        self.ui_backend.begin_frame()

        draw_active = bool(self.engine and self.engine.draw_mgr and self.engine.draw_mgr.is_active)
        self.toolbar.draw(model_text=self._model_text, draw_active=draw_active)

        self.main_menu.draw()
        self.visibility_panel.draw()
        self.view_filter.draw()
        self.inspector.draw()
        self.zones_panel.draw()
        
        # Yönetim Panellerini Çiz
        self.definition_panel.draw()
        self.project_info_panel.draw()
        self.project_config_panel.draw()
        self.analysis_panel.draw()


        self.file_dialog.draw()
        self.router.process_pending()
        # Rüzgar analizi kuyruk kontrolü
        self._process_wind_queue()

        # Sahne çizimi
        self._render_scene(dt)

        self.ui_backend.end_frame()

        # Pick kontrolü (Yedek koddan geri eklendi)
        if self.engine and self.engine.pending_pick_check:
            self.engine.check_pick_result()

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

    def _save_project(self, path: str):
        try:
            if self.engine and self.engine.scene:
                self.current_project.scene = self.engine.scene
                # Scene içerisindeki definition manager'ı project seviyesine senkronize et
                if hasattr(self.engine.scene, "def_mgr"):
                    self.current_project.definitions = self.engine.scene.def_mgr
            
            self.current_project.save(path)
            self._model_text = f"MODEL: {os.path.basename(path)}"
            logger.info("[File] Proje kaydedildi: %s", path)
        except Exception:
            logger.exception("Proje kaydetme hatası")

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

    def _on_view_filter_apply(self, plane, offset, direction):
        if self.engine:
            self.engine.apply_plane_filter(plane, offset, direction)

    def _on_run_wind_analysis(self):
        pass

    def _on_toolbar_menu(self):
        self.main_menu.open()
        logger.info("[Toolbar] Menü açılıyor")

    def open_inspector(self, element):
        """Seçilen eleman için inspector panelini aç."""
        if element is None:
            return
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

    def shutdown(self):
        self.ui_backend.shutdown()