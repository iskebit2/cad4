# app/cad_app.py
"""
CadApp — eski KivyCADWidget'ın ImGui karşılığı.

Sorumluluğu SADECE:
  - Engine yaşam döngüsü
  - Frame render (GL)
  - Input event'lerini Engine API'sine yönlendirme
  - Panel aç/kapa
"""
import os
import time

import glfw
from OpenGL.GL import (
    glEnable, glDisable, glClear, glClearColor, glViewport,
    glUseProgram, glBindVertexArray, glBindBuffer, glBlendFunc,
    GL_DEPTH_TEST, GL_CULL_FACE, GL_BLEND,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
    GL_ARRAY_BUFFER, GL_ELEMENT_ARRAY_BUFFER,
    GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA,
)

from app.cad_window import CadWindow
from core.gl_engine import PureKivyEngine
from core.input_manager import (
    MOUSE_BUTTON_LEFT, MOUSE_BUTTON_RIGHT, MOUSE_BUTTON_MIDDLE,
)
from app.event_router import EventRouter

from ui import (
    InspectorPanel,
    schema_for,
    element_to_values,
    values_to_element,
)
from ui.theme import load_fonts, apply_dark_theme
from ui.imgui_backend import UiBackend  # önceki mesajdaki backend
from ui.toolbar import Toolbar
from ui.main_menu import MainMenuPopup
from ui.file_dialog import ImGuiFileDialog
from ui import VisibilityPanel
from ui.view_filter_panel import ViewFilterPanel
from ui import InspectorPanel
from ui import ZonesPanel

from logging_config import CadLogger
logger = CadLogger.get(__name__)


class CadApp:

    MIDDLE_DOUBLE_CLICK_INTERVAL = 0.25
    MIDDLE_DOUBLE_CLICK_MAX_DRAG = 4.0

    def __init__(self, window: CadWindow):
        self.window = window

        self.engine = None
        self.initialized = False
        self._last_time = time.time()
        self._pressed_keys = set()

        self._last_middle_click_time = 0.0
        self._middle_press_pos = (0.0, 0.0)
        self._middle_dragged = False

        self.hover_visual_enabled = True

        # Panels
        self.inspector = InspectorPanel(
                width=380, height=620,
                on_apply_element=self._on_inspector_apply,
            )
        self._inspector_element = None
        self.main_menu = MainMenuPopup(on_action=self._on_main_menu_action)
        self.visibility_panel = VisibilityPanel(on_apply=self._on_visibility_applied)
        self.file_dialog = ImGuiFileDialog()
        self.view_filter = ViewFilterPanel(on_apply=self._on_view_filter_apply)
        self.zones_panel = ZonesPanel(on_run_analysis=self._on_run_wind_analysis)

        # UI backend (ImGui)
        self.ui_backend = UiBackend(window.window)
        self.ui_backend.setup()

        window._wire_callbacks()

        # Event router
        self.router = EventRouter(self)

        # Window callbacks
        window.on_key_down     = self.router.on_key_down
        window.on_key_up       = self.router.on_key_up
        window.on_mouse_button = self.router.on_mouse_button
        window.on_mouse_move   = self.router.on_mouse_move
        window.on_scroll       = self.router.on_scroll
        window.on_resize       = self._on_resize   # bu CadApp'te kalsın
        window.on_char         = self.router.on_char


        # --- DEBUG: Event bağlantıları ---
        logger.info("=== Event Router Bağlantı Kontrolü ===")
        logger.info("window.on_mouse_button: %s", window.on_mouse_button)
        logger.info("window.on_mouse_move:   %s", window.on_mouse_move)
        logger.info("window.on_scroll:       %s", window.on_scroll)
        logger.info("window.on_key_down:     %s", window.on_key_down)
        logger.info("router:                 %s", self.router)
        logger.info("router.app:             %s", self.router.app)
        logger.info("router.engine:          %s", self.router.engine)
        logger.info("======================================")

        self.toolbar = Toolbar({
            "menu":        self._on_toolbar_menu,
            "open":        self._on_toolbar_open,
            "save":        self._on_toolbar_save,
            "draw":        self._toggle_draw_mode,
            "import_sap":  self._on_toolbar_import_sap,
            "visibility":  self._on_toolbar_visibility,
            "wind":        self._on_toolbar_wind,
            "print":       self._on_toolbar_print,
        })

        # Model metni ve draw state için basit state
        self._model_text = "MODEL: YENİ SAHNE"

        window.on_focus = self.router.on_window_focus

    # ------------------------------------------------------------------
    # ENGINE LIFECYCLE
    # ------------------------------------------------------------------
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

    def set_scene(self, scene):
        """Sahneyi değiştir + bağımlı UI'ları tazele."""
        if not self.engine:
            return
        self.engine.set_scene(scene)

        # Inspector panel'in sahne referansını güncelle
        self.inspector.scene = scene

        # Tanımlar sekmesi açıksa içeriği tazele
        if self.inspector.visible:
            self.inspector.definitions_tab.refresh(scene)

    # ------------------------------------------------------------------
    # FRAME LOOP
    # ------------------------------------------------------------------
    def frame(self, dt):
        self._ensure_engine()
        if not self.initialized:
            return

        # ImGui frame başlangıcı
        self.ui_backend.begin_frame()

        # --- Toolbar çiz ---
        draw_active = bool(
            self.engine and self.engine.draw_mgr
            and self.engine.draw_mgr.is_active
        )
        self.toolbar.draw(
            model_text=self._model_text,
            draw_active=draw_active,
        )

        self.main_menu.draw()

        self.visibility_panel.draw()
        self.view_filter.draw()
        # --- Inspector panel çiz ---
        self.inspector.draw()
        self.zones_panel.draw()

        # Dosya seçici
        self.file_dialog.draw()

        self.router.process_pending()

        # --- Sahne çiz ---
        self._render_scene(dt)

        # ImGui frame sonu
        self.ui_backend.end_frame()

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
            self._draw_snap_indicator(w, h)

            if self.engine.draw_mgr.is_active:
                mvp = (self.engine.cam.get_projection_matrix()
                       @ self.engine.cam.get_view_matrix())
                self.engine.draw_mgr.render_preview(mvp, self.engine.preview_s)

            # if self.engine.snap is not None and self.engine.draw_mgr.is_active:
            #     snap_node = self.engine.draw_mgr.hover_node
            #     self.engine.snap.draw_snap(
            #         self.engine.input.mouse_pos.x,
            #         self.engine.input.mouse_pos.y,
            #         w, h,
            #         active=(snap_node is not None),
            #     )
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

        # Draw modu → her zaman göster
        if self.engine.draw_mgr.is_active:
            snap.draw_snap(mx, my, w, h, active=True)
            return

        # Normal mod → hover varsa göster
        if self.engine.hover_id > 0:
            snap.draw_snap(mx, my, w, h, active=True)
            
    # ------------------------------------------------------------------
    # RESIZE
    # ------------------------------------------------------------------
    def _on_resize(self, w, h):
        if self.engine:
            self.engine.resize(max(1, w), max(1, h))

    # ------------------------------------------------------------------
    # INSPECTOR ←→ ENGINE
    # ------------------------------------------------------------------
    def open_inspector(self, element):
        if element is None:
            return
        self.inspector.open_element(element)

    def open_multi_inspector(self, elements):
        if not elements:
            return
        self.inspector.open_multi(elements)

    def open_definitions(self):
        """Tanımlar sekmesini aç."""
        self.inspector.open_definitions(self.engine.scene if self.engine else None)

    def open_new_element_dialog(self, element_type, defaults=None, repeat=False):
        """Yeni eleman formunu inspector'da aç."""
        from ui import schema_for
        self._inspector_element = None
        self._new_element_type = element_type
        self._new_element_repeat = repeat
        self.inspector.open(
            schema_for(element_type),
            defaults or {},
            title=f"YENİ: {element_type}" + (" (çoklu)" if repeat else ""),
        )

    def toggle_view_filter_panel(self):
        """View filter panelini aç/kapa."""
        if self.view_filter.visible:
            self.view_filter.close()
        else:
            self.view_filter.open(self.engine.cam if self.engine else None)


    # def _drain_inspector_result(self):
    #     if not self.inspector.has_result():
    #         return
    #     res = self.inspector.consume_result()
    #     if res["action"] != "apply":
    #         return

    #     from ui import values_to_element

    #     # Çoklu seçim
    #     if self._inspector_elements:
    #         # "[KARIŞIK]" olan alanları atla
    #         cleaned = self._strip_mixed(res["values"])
    #         if not cleaned:
    #             return
    #         for el in self._inspector_elements:
    #             try:
    #                 values_to_element(el, cleaned)
    #             except Exception:
    #                 logger.exception("Çoklu update hatası: %r", el)
    #         self._inspector_elements = None

    #     # Tek eleman
    #     elif self._inspector_element is not None:
    #         cleaned = self._strip_mixed(res["values"])
    #         values_to_element(self._inspector_element, cleaned)
    #         self._inspector_element = None

    #     # Sahneyi tazele
    #     if self.engine and self.engine.scene:
    #         try:
    #             self.engine.renderer.update_geo(self.engine.scene)
    #         except Exception:
    #             logger.exception("update_geo hatası")


    def _strip_mixed(self, values: dict) -> dict:
        """
        '[KARIŞIK]' işaretli alanları atla. Nested dict'leri de kontrol et.
        """
        if not isinstance(values, dict):
            return values
        out = {}
        for k, v in values.items():
            if v == "[KARIŞIK]":
                continue
            if isinstance(v, dict):
                sub = self._strip_mixed(v)
                if sub:
                    out[k] = sub
            else:
                out[k] = v
        return out

    def _on_selection_changed(self, selected_elements):
        # 1) Her zaman seçim renklerini güncelle
        if self.engine and self.engine.renderer:
            try:
                self.engine.renderer.update_sel()
            except Exception:
                logger.exception("update_sel hatası")

        # 2) Panel açık değilse → dokunma
        if not self.inspector.visible:
            return

        # 3) Panel açıksa → içeriği seçime göre güncelle
        if not selected_elements:
            self.inspector.inspector_tab.clear()
            return

        if len(selected_elements) == 1:
            self.inspector.open_element(selected_elements[0])
        else:
            self.inspector.open_multi(selected_elements)

    def _on_hover_changed(self, element):
       
        pass

    # ------------------------------------------------------------------
    # TOOLBAR CALLBACK'LERİ
    # ------------------------------------------------------------------
    def _on_toolbar_menu(self):
        """Ana menüyü aç."""
        self.main_menu.open()
        logger.info("[Toolbar] Menü açılıyor")

    def _on_toolbar_open(self):
        """Proje aç — ImGui dosya seçici."""
        self.file_dialog.open(
            mode="open",
            filters=[".json"],
            title="Proje Aç",
            initial_dir=os.getcwd(),
            on_select=self._load_project,
        )
        # TODO: ImGui dosya seçici penceresi

    def _on_toolbar_save(self):
        """Proje kaydet — ImGui dosya seçici."""
        self.file_dialog.open(
            mode="save",
            filters=[".json"],
            title="Projeyi Kaydet",
            initial_dir=os.getcwd(),
            default_name="model_projesi.json",
            on_select=self._save_project,
        )
        # TODO: ImGui dosya kaydetme penceresi

    def _on_toolbar_import_sap(self):
        """SAP2000'den import."""
        logger.info("[Toolbar] SAP Import (yapılacak)")
        # TODO: Burada engine.scene'i SAP'den dolduracak kod

    def _on_toolbar_visibility(self):
        if self.visibility_panel.visible:
            self.visibility_panel.close()
        else:
            self.visibility_panel.open(self.engine.scene if self.engine else None)
        # TODO: ImGui visibility paneli

    def _on_toolbar_wind(self):
        if self.zones_panel.visible:
            self.zones_panel.close()
        else:
            scene = self.engine.scene if self.engine else None
            self.zones_panel.open(scene)
        # TODO: ImGui wind paneli

    def _on_toolbar_print(self):
        """Seçili elemanları yazdır."""
        logger.info("[Toolbar] Print — seçili elemanlar konsola yazılıyor")
        # Engine'den seçili elemanları al
        if not self.engine or not self.engine.sel_mgr:
            return
        selected = self.engine.sel_mgr.get_selected()
        for elem in selected:
            logger.info("  • %s", elem)

    def _toggle_draw_mode(self):
        """Toolbar 'draw' butonu için."""
        eng = self.engine
        if not eng or not eng.draw_mgr:
            return
        if eng.draw_mgr.is_active:
            eng.draw_mgr.close()
        else:
            eng.draw_mgr.start()

    def _on_main_menu_action(self, key: str):
        """Ana menüden bir öğe seçildi."""
        logger.info("[Menu] Aksiyon: %s", key)

        dispatch = {
            "inspector":    self._menu_open_inspector,
            "analysis":     self._menu_open_analysis,
            "new_project":  self._menu_new_project,
            "open_project": self._on_toolbar_open,
            "save_project": self._on_toolbar_save,
            "import_s2k":   self._menu_import_s2k,
            "visibility":   self._on_toolbar_visibility,
        }
        fn = dispatch.get(key)
        if callable(fn):
            fn()

    def _menu_open_inspector(self):
        """Seçili elemanın inspector'ını aç."""
        if not self.engine or not self.engine.sel_mgr:
            return
        selected = self.engine.sel_mgr.get_selected()
        if not selected:
            logger.info("[Menu] Inspector — seçili eleman yok")
            return
        if len(selected) == 1:
            self.open_inspector(selected[0])
        else:
            self.open_multi_inspector(selected)

    def _menu_open_analysis(self):
        logger.info("[Menu] Analysis — yapılacak")

    def _menu_new_project(self):
        """Sahneyi sıfırla, yeni boş proje."""
        logger.info("[Menu] Yeni proje")

        # Yeni boş sahne
        from domain.scene import Scene
        new_scene = Scene()

        # Merkezi metot: engine.set_scene + UI tazele
        self.set_scene(new_scene)

        # Kamera sıfırla
        if self.engine and self.engine.cam:
            self.engine.cam.reset()

        # Model etiketini güncelle
        self._model_text = "MODEL: YENİ SAHNE"

        # Panelleri kapat
        self.inspector.close()
        if hasattr(self, "visibility_panel"):
            self.visibility_panel.close()
        if hasattr(self, "view_filter"):
            self.view_filter.close()

        logger.info("[Menu] Yeni proje oluşturuldu")

    def _menu_import_s2k(self):
        """S2K import — ImGui dosya seçici ile."""
        self.file_dialog.open(
            mode="open",
            filters=[".s2k", ".S2K"],
            title="S2K İçe Aktar",
            initial_dir=os.getcwd(),
            on_select=self._import_s2k,
        )


    def _load_project(self, path: str):
        """Seçilen JSON dosyasını yükle."""
        try:
            from domain.scene import Scene
            scene = Scene.load_from_json(path)
            if self.engine:
                self.set_scene(scene)
                self.engine.fit_view()
            self._model_text = f"MODEL: {os.path.basename(path)}"
            logger.info("[File] Yüklendi: %s", path)
        except Exception as e:
            logger.exception("Proje yükleme hatası")
            # İstersen bir ImGui hata popup'ı açabilirsin

    def _save_project(self, path: str):
        """Sahneyi JSON olarak kaydet."""
        try:
            if not self.engine or not self.engine.scene:
                logger.warning("[File] Kaydedilecek sahne yok")
                return
            self.engine.scene.save_to_json(path)
            self._model_text = f"MODEL: {os.path.basename(path)}"
            logger.info("[File] Kaydedildi: %s", path)
        except Exception as e:
            logger.exception("Proje kaydetme hatası")

    def _on_visibility_applied(self):
        """Visibility panelinden apply sonrası çağrılır."""
        if self.engine and self.engine.scene:
            try:
                self.engine.renderer.update_geo(self.engine.scene)
            except Exception:
                logger.exception("update_geo hatası (visibility)")

    def _on_view_filter_apply(self, plane, offset, direction):
        """ViewFilterPanel'den Apply geldiğinde çağrılır."""
        if not self.engine:
            return
        if plane is None:
            self.engine.apply_plane_filter(None)   # filtreyi kaldır
        else:
            self.engine.apply_plane_filter(plane, offset, direction)

    def toggle_inspector(self):
        """Ctrl+P → inspector aç/kapa."""
        if self.inspector.visible:
            self.inspector.close()
            return

        # Açılış: seçili eleman varsa göster, yoksa hover'daki eleman
        eng = self.engine
        if eng is None:
            return

        selected = eng.sel_mgr.get_selected() if eng.sel_mgr else []
        if len(selected) == 1:
            self.open_inspector(selected[0])
        elif len(selected) > 1:
            self.open_multi_inspector(selected)
        elif eng.hover_id > 0:
            element = eng.renderer.get_element_from_id(eng.hover_id)
            if element:
                self.open_inspector(element)


    def _on_inspector_apply(self, target, values):
        """InspectorTab Apply → element(ler)e uygula."""
        from ui import values_to_element

        # Çoklu seçim
        if isinstance(target, list):
            for el in target:
                try:
                    values_to_element(el, values)
                except Exception:
                    logger.exception("Çoklu update hatası: %r", el)
        # Tek eleman
        else:
            values_to_element(target, values)

        # Sahneyi tazele
        if self.engine and self.engine.scene:
            try:
                self.engine.renderer.update_geo(self.engine.scene)
            except Exception:
                logger.exception("update_geo hatası")

    def _import_s2k(self, path):
        """Seçilen S2K dosyasını yükle ve sahneyi değiştir."""
        try:
            from tools.s2kloader import S2KLoader
            logger.info("[S2K] Yükleniyor: %s", path)

            scene = S2KLoader(path).load()
            if scene is None:
                logger.warning("[S2K] Boş sahne döndü")
                return

            # Sahnede hiç eleman var mı kontrol et
            total = sum(len(getattr(scene, coll, {}) or {})
                        for coll in ("nodes", "frames", "areas", "links", "polygons"))
            logger.info("[S2K] Yüklendi: %d eleman", total)

            if total == 0:
                logger.warning("[S2K] Dosya boş, sahne değiştirilmedi")
                return

            # Merkezi metot: engine + UI tazele
            self.set_scene(scene)

            # Model etiketini güncelle
            self._model_text = f"MODEL: {os.path.basename(path)}"

        except Exception:
            logger.exception("[S2K] Yükleme hatası: %s", path)

    def _on_run_wind_analysis(self):
        """Rüzgar analizi çalıştır — panel daha sonra."""
        logger.info("[Zones] Rüzgar analizi başlatılacak (yapılacak)")
        # TODO: WindSceneAdapter.run_wind_analysis_and_update_scene(...)
        # Sonrasında: self.zones_panel.open(self.engine.scene) ile yeniden aç

    def _all_panels(self):
        """Tüm aktif paneller."""
        panels = []
        for name in ("toolbar", "main_menu", "file_dialog", "inspector",
                    "visibility_panel", "view_filter", "zones_panel"):
            p = getattr(self, name, None)
            if p is not None:
                panels.append(p)
        return panels
       
    # ------------------------------------------------------------------
    def shutdown(self):
        self.ui_backend.shutdown()