# main.py




import os

# ⬅️ Kivy loglarını tamamen sustur
os.environ["KIVY_LOG_LEVEL"] = "error"        # veya "critical"
os.environ["KIVY_NO_CONSOLELOG"] = "1"        # konsola hiç log basma
os.environ["KIVY_NO_FILELOG"] = "1"           # dosyaya da log basma
os.environ["KIVY_NO_ARGS"] = "1"              # Kivy args parsing'i kapat

import sys
from pathlib import Path
import threading

# --- PYDROID / TERMUX DİZİN VE HİYERARŞİ DÜZELTİCİ ---
FILE_DIR = Path(__file__).resolve().parent
if str(FILE_DIR) not in sys.path:
    sys.path.insert(0, str(FILE_DIR))
# ----------------------------------------------------



from kivy.app import App
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.popup import Popup

from logging_config import CadLogger
CadLogger.setup("INFO")
logger = CadLogger.get(__name__)

logger.debug("DEBUG testi")
logger.info("INFO testi")
logger.warning("WARNING testi")
logger.error("ERROR testi")

from core.engine_factory import create_cad_widget
from gui.panel_main_menu import MainMenuPanel
from gui.panel_inspector import ModelInspectorPanel
from gui.analysis_popup import AnalysisPopup
from gui.basecustompopup import FONT_DEFAULT
from gui.prop_panel import PropertiesPanel
from gui.panel_visibility import VisibilityPanel
from domain.scene import Scene

from debug_lines import debug_layout
class MainApp(App):
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cad_widget = None
        self.inspector_popup = None
        self.analysis_popup = None
        self.menu_popup = None
        self.current_path = ""
        self._picker_open = False
        
        # ANA VERİ - Sahne
        self.scene = Scene()

    @property
    def engine(self):
        return getattr(self.cad_widget, "engine", None)

    def build(self):
        root = FloatLayout()
        self.cad_widget = create_cad_widget()
        self.cad_widget.size_hint = (1, 1)
        self.cad_widget.pos_hint = {'x': 0, 'y': 0}
        root.add_widget(self.cad_widget)

        self.title = "Yapısal Analiz ve CAD Paneli"

        # Üst Araç Çubuğu (Toolbar)
        toolbar = BoxLayout(
            size_hint_y=None,
            height=dp(48),
            pos_hint={'top': 1, 'x': 0},  # ← EKRANIN EN ÜSTÜNE SABİTLE
            spacing=dp(6),
            padding=(dp(6), dp(4))
        )

        # 1. Hamburger / Ana Menü Butonu
        btn_menu = Button(
            text="☰",
            size_hint_x=None,
            width=dp(36),
            font_size=dp(16),
            font_name= FONT_DEFAULT,
            background_normal="",
            background_color=(0.15, 0.20, 0.28, 1),
            color=(0.9, 0.9, 0.9, 1),
            bold=True
        )
        btn_menu.bind(on_release=self.open_main_menu)
        toolbar.add_widget(btn_menu)

        # 2. Hızlı Aç Butonu (Open)
        btn_open = Button(
            text="Aç",
            size_hint_x=None,
            width=dp(65),
            font_size=dp(13),
            font_name=FONT_DEFAULT,
            background_normal="",
            background_color=(0.18, 0.35, 0.55, 1),
            color=(1, 1, 1, 1),
            bold=True
        )
        btn_open.bind(on_release=self.action_open)
        toolbar.add_widget(btn_open)

        # 3. Hızlı Kaydet Butonu (Save)
        btn_save = Button(
            text="Kaydet",
            size_hint_x=None,
            width=dp(75),
            font_size=dp(13),
            font_name=FONT_DEFAULT,
            background_normal="",
            background_color=(0.18, 0.50, 0.32, 1),
            color=(1, 1, 1, 1),
            bold=True
        )
        btn_save.bind(on_release=self.action_save)
        toolbar.add_widget(btn_save)

        # 4. Çizim Modu Butonu (Draw Mode)
        self.btn_draw_mode = Button(
            text="✏ Çizim (D)",
            size_hint_x=None,
            width=dp(95),
            font_size=dp(12),
            font_name=FONT_DEFAULT,
            background_normal="",
            background_color=(0.22, 0.28, 0.38, 1),
            color=(0.9, 0.9, 0.9, 1),
            bold=True
        )
        self.btn_draw_mode.bind(on_release=self.toggle_draw_mode)
        toolbar.add_widget(self.btn_draw_mode)

        # 5. SAP2000 Import
        btn_import = Button(
            text="SAP Import",
            size_hint_x=None,
            width=dp(95),
            font_size=dp(12),
            font_name=FONT_DEFAULT,
            background_normal="",
            background_color=(0.25, 0.22, 0.38, 1),
            color=(1, 1, 1, 1),
            bold=True
        )
        btn_import.bind(on_release=self._import_from_sap)
        toolbar.add_widget(btn_import)

        # Durum Başlığı
        self.lbl_info = Label(
            text="MODEL: YENİ SAHNE",
            halign="left",
            valign="middle",
            color=(0.6, 0.65, 0.72, 1),
            font_size=dp(12)
        )
        self.lbl_info.bind(size=self.lbl_info.setter("text_size"))
        toolbar.add_widget(self.lbl_info)
        
        btn_visibility = Button(
            text="👁 Filtre",
            size_hint_x=None,
            width=dp(80),
            font_size=dp(12),
            font_name=FONT_DEFAULT,
            background_normal="",
            background_color=(0.20, 0.40, 0.50, 1),
            color=(1, 1, 1, 1),
            bold=True
        )
        btn_visibility.bind(on_release=self.show_visibility_panel)
        toolbar.add_widget(btn_visibility)

        btn_wind = Button(
            text="💨 Rüzgar Zones",
            size_hint_x=None,
            width=dp(105),
            font_size=dp(12),
            font_name=FONT_DEFAULT,
            background_normal="",
            background_color=(0.15, 0.45, 0.60, 1),
            color=(1, 1, 1, 1),
            bold=True
        )
        btn_wind.bind(on_release=self.show_wind_config_panel)
        toolbar.add_widget(btn_wind)

        root.add_widget(toolbar)

        # Properties Panel
        self.properties = PropertiesPanel(pos_hint={'right': 1, 'top': 0.96})
        root.add_widget(self.properties)
        self.properties.hide()     
        self.cad_widget.properties_panel = self.properties
        
        # Yükleme Göstergesi
        self.loading_indicator = self._make_loading_indicator()
        self.loading_indicator.opacity = 0
        self.loading_indicator.disabled = True
        root.add_widget(self.loading_indicator)

        # Çizim modu durumunu sürekli güncel tutan periyodik denetleyici
        Clock.schedule_interval(self._update_draw_btn_ui, 0.2)

        debug_layout(root)

        return root

    # ========================================================
    # DRAW MODE İŞLEMLERİ
    # ========================================================

    def toggle_draw_mode(self, *_):
        """Çizim modunu buton üzerinden açar veya kapatır."""
        if not self.engine or not self.engine.draw_mgr:
            return

        if self.engine.draw_mgr.is_active:
            self.engine.draw_mgr.close()
            logger.info("[UserAction] Çizim modu kapatıldı.")
        else:
            self.engine.draw_mgr.start()
            logger.info("[UserAction] Çizim modu başlatıldı.")
        
        self._update_draw_btn_ui()

    def _update_draw_btn_ui(self, *_):
        """Engine tarafındaki draw_mgr durumuna göre butonun rengini ve yazısını günceller."""
        if not self.engine or not hasattr(self.engine, "draw_mgr") or not self.btn_draw_mode:
            return

        if self.engine.draw_mgr.is_active:
            self.btn_draw_mode.background_color = (0.20, 0.60, 0.35, 1)  # Aktifken Yeşil
            self.btn_draw_mode.text = "✏ Çizim [AÇIK]"
        else:
            self.btn_draw_mode.background_color = (0.22, 0.28, 0.38, 1)  # Pasifken Standart
            self.btn_draw_mode.text = "✏ Çizim (D)"

    # ========================================================
    # YÜKLEME GÖSTERGESİ (LOADING INDICATOR)
    # ========================================================

    def _make_loading_indicator(self):
        box = BoxLayout(
            orientation='horizontal',
            size_hint=(None, None),
            size=(dp(160), dp(36)),
            pos_hint={'right': 0.98, 'y': 0.02},
            spacing=dp(6),
            padding=(dp(8), dp(4)),
        )
        label = Label(
            text="İşlem yapılıyor...",
            font_size=dp(11),
            font_name=FONT_DEFAULT,
            color=(0.9, 0.9, 0.9, 1.0),
            halign='center',
            valign='middle',
        )
        label.bind(size=label.setter('text_size'))
        box.add_widget(label)
        box.label = label
        return box

    def _show_loading(self, text="İşlem yapılıyor..."):
        if hasattr(self, 'loading_indicator'):
            self.loading_indicator.label.text = text
            self.loading_indicator.opacity = 1
            self.loading_indicator.disabled = False

    def _hide_loading(self):
        if hasattr(self, 'loading_indicator'):
            self.loading_indicator.opacity = 0
            self.loading_indicator.disabled = True

    # ============================================================
    # PANEL VE MENÜ YÖNETİMİ
    # ============================================================

    def open_main_menu(self, *_):
        if self.menu_popup:
            return
        self.menu_popup = MainMenuPanel(on_action_selected=self.on_menu_choice)
        self.menu_popup.bind(on_dismiss=lambda *_: setattr(self, 'menu_popup', None))
        self.menu_popup.open()

    def on_menu_choice(self, action_key):
        if action_key == "inspector":
            self.show_inspector()
        elif action_key == "analysis":
            self.show_analysis()
        elif action_key == "open_project":
            self.action_open()
        elif action_key == "save_project":
            self.action_save()
        elif action_key == "import_s2k":
            self.import_s2k()
        elif action_key == "new_project":
            self.action_new()
        elif action_key == "visibility":
            self.show_visibility_panel()

    def show_inspector(self, *_):
        if self.inspector_popup:
            return
        self.inspector_popup = ModelInspectorPanel(scene=self.scene)
        self.inspector_popup.bind(on_dismiss=lambda *_: setattr(self, 'inspector_popup', None))
        self.inspector_popup.open()

    def show_analysis(self, *_):
        if self.analysis_popup:
            return
        self.analysis_popup = AnalysisPopup(proje_data=self.scene)
        self.analysis_popup.bind(on_dismiss=lambda *_: setattr(self, 'analysis_popup', None))
        self.analysis_popup.open()

    # ========================================================
    # PROJE DOSYA İŞLEMLERİ (JSON SAVE / LOAD)
    # ========================================================

    def action_new(self, *_):
        """Yeni boş bir sahne başlatır."""
        self.scene = Scene()
        self.current_path = ""
        self._apply_scene(self.scene)
        self.lbl_info.text = "MODEL: YENİ SAHNE"
        logger.info("[UserAction] Yeni temiz proje başlatıldı.")

    def action_open(self, *_):
        """Diskteki JSON dosyasını Scene.load_from_json ile okur."""
        def on_file_selected(path: str):
            logger.info(f"[UserAction] JSON Proje Açılıyor -> {path}")
            self._show_loading("Model yükleniyor...")

            def load_thread():
                try:
                    loaded_scene = Scene.load_from_json(path)
                    Clock.schedule_once(lambda dt: self._on_project_loaded(loaded_scene, path), 0)
                except Exception as e:
                    logger.error(f"Proje açma hatası: {e}", exc_info=True)
                    Clock.schedule_once(lambda dt: self._show_error(f"Dosya Açılamadı:\n{e}"), 0)

            threading.Thread(target=load_thread, daemon=True).start()

        self._pick_file(mode="open", filters=["*.json"], on_select=on_file_selected)

    def _on_project_loaded(self, loaded_scene, path):
        self.scene = loaded_scene
        self.current_path = path
        self._apply_scene(self.scene)
        
        filename = os.path.basename(path)
        self.lbl_info.text = f"MODEL: {filename}"
        self._hide_loading()
        logger.info(f"[Main] Model başarıyla yüklendi: {path}")

    def action_save(self, *_):
        """Mevcut sahneyi doğrudan veya farklı kaydet seçeneğiyle yazar."""
        if self.current_path:
            try:
                self.scene.save_to_json(self.current_path)
                filename = os.path.basename(self.current_path)
                self.lbl_info.text = f"MODEL: {filename} (Kaydedildi)"
                logger.info(f"[UserAction] Proje Kaydedildi -> {self.current_path}")
            except Exception as e:
                logger.error(f"Kaydetme hatası: {e}", exc_info=True)
                self._show_error(f"Kaydedilemedi:\n{e}")
        else:
            self.action_save_as()

    def action_save_as(self, *_):
        """Farklı kaydet seçeneği ile dosya seçiciyi açar."""
        def on_file_selected(path: str):
            try:
                if not path.endswith(".json"):
                    path += ".json"

                self.scene.save_to_json(path)
                self.current_path = path
                filename = os.path.basename(path)
                self.lbl_info.text = f"MODEL: {filename}"
                logger.info(f"[UserAction] Proje Farklı Kaydedildi -> {path}")
            except Exception as e:
                logger.error(f"Kaydetme hatası: {e}", exc_info=True)
                self._show_error(f"Kaydedilemedi:\n{e}")

        self._pick_file(
            mode="save", 
            filters=["*.json"], 
            on_select=on_file_selected, 
            default_name="model_projesi.json"
        )

    def import_s2k(self, *_):
        def on_file(path: str):
            logger.info(f"[UserAction] S2K Dosyası Seçildi -> {path}")
            self._show_loading("S2K yükleniyor...")
            
            def load_thread():
                try:
                    from tools.s2kloader import S2KLoader
                    imported_scene = S2KLoader(path).load()
                    Clock.schedule_once(lambda dt: self._apply_scene(imported_scene), 0)
                except Exception as e:
                    logger.error(f"S2K yükleme hatası: {e}", exc_info=True)
                    Clock.schedule_once(lambda dt: self._show_error(f"S2K Yüklenemedi:\n{e}"), 0)
            
            threading.Thread(target=load_thread, daemon=True).start()

        self._pick_file(mode="open", filters=["*.s2k"], on_select=on_file)

    def _apply_scene(self, new_scene):
        """Yüklenen yeni sahneyi engine ve renderer'a entegre eder."""
        try:
            self.scene = new_scene
            if self.engine:
                self.engine.set_scene(new_scene)
                if hasattr(self.engine, 'renderer') and self.engine.renderer:
                    self.engine.renderer.update_geo(new_scene)
                if hasattr(self.engine, 'focus_on_model'):
                    self.engine.focus_on_model()
        except Exception as e:
            logger.error(f"_apply_scene hatası: {e}", exc_info=True)
        finally:
            self._hide_loading()

    def _show_error(self, message: str):
        self._hide_loading()
        lbl = Label(
            text=str(message),
            font_name=FONT_DEFAULT,
            font_size=dp(12),
            color=(1, 0.4, 0.4, 1),
            halign="center",
            valign="middle"
        )
        popup = Popup(
            title_text="HATA",
            content_widget=lbl,
            size_hint=(0.7, 0.4)
        )
        popup.open()

    # ========================================================
    # FILE PICKER (DOSYA SEÇİCİ POPUP)
    # ========================================================

    def _pick_file(self, mode: str, filters: list, on_select, default_name: str = ""):
        if getattr(self, "_picker_open", False):
            return
        self._picker_open = True

        fc = FileChooserListView(filters=filters, path=os.getcwd())

        box = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(6))
        box.add_widget(fc)

        name_input = None
        if mode == "save":
            name_input = TextInput(
                text=default_name,
                size_hint_y=None,
                height=dp(40),
                hint_text="Dosya adı girin...",
                font_name=FONT_DEFAULT,
                multiline=False,
            )
            box.add_widget(name_input)

        btn_row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))

        ok_btn = Button(
            text="Tamam",
            font_name=FONT_DEFAULT,
            background_normal="",
            background_color=(0.18, 0.50, 0.32, 1),
            color=(1, 1, 1, 1),
            bold=True,
        )
        cancel_btn = Button(
            text="İptal",
            font_name=FONT_DEFAULT,
            background_normal="",
            background_color=(0.40, 0.40, 0.40, 1),
            color=(1, 1, 1, 1),
        )

        btn_row.add_widget(ok_btn)
        btn_row.add_widget(cancel_btn)
        box.add_widget(btn_row)

        popup = Popup(
            title="Dosya Seç",
            content=box,
            size_hint=(0.85, 0.85),
            auto_dismiss=False,
            separator_height=0,
        )

        processed = [False]

        def _finish(selection=None):
            if processed[0]:
                return
            processed[0] = True
            self._picker_open = False
            popup.dismiss()
            if selection:
                on_select(selection)

        def _on_ok(*_):
            sel = fc.selection[0] if fc.selection else None
            if mode == "save" and name_input is not None:
                name = name_input.text.strip()
                if name:
                    folder = fc.path
                    sel = os.path.join(folder, name)
            if not sel:
                return
            _finish(sel)

        def _on_cancel(*_):
            _finish(None)

        def _on_dismiss(*_):
            self._picker_open = False
            if not processed[0]:
                processed[0] = True

        ok_btn.bind(on_release=_on_ok)
        cancel_btn.bind(on_release=_on_cancel)
        popup.bind(on_dismiss=_on_dismiss)

        popup.open()

    def _import_from_sap(self, *_):
        try:
            from tools.sap_connect import cSap
            from exchange.cad4_sap_exchange import import_sap_to_scene

            sap = cSap()
            sap.set_units(9)  # N, mm, C

            counts = import_sap_to_scene(
                sap,
                self.engine.scene,
            )
            if counts and self.engine:
                self.engine.renderer.update_geo(self.engine.scene)
                self.engine.focus_on_model()
        except Exception as e:
            logger.error(f"SAP Import hatası: {e}", exc_info=True)
            self._show_error(f"SAP2000 Bağlantı Hatası:\n{e}")

    def show_visibility_panel(self, *_):
        
        
        def on_changed():
            # Görünürlük değiştiğinde OpenGL render çantasını yenile
            if self.engine and hasattr(self.engine, 'renderer'):
                self.engine.renderer.update_geo(self.scene)

        panel = VisibilityPanel(scene=self.scene, on_visibility_changed=on_changed)
        panel.open()



    def _on_wind_done(self, count):
        if self.engine and hasattr(self.engine, 'renderer'):
            self.engine.renderer.update_geo(self.scene)
            self.engine.fit_view()
        self._hide_loading()
        logger.info(f"[Wind] {count} adet Rüzgar Zone poligonu ekrana çizildi.")

    def show_wind_config_panel(self, *_):
        from gui.panel_wind_config import WindConfigPanel

        def on_confirm_run(w_dir, config):
            self.run_wind_analysis_ui(w_dir, config)

        panel = WindConfigPanel(on_run_analysis=on_confirm_run, scene = self.scene)
        panel.open()

    def run_wind_analysis_ui(self, w_dir, config):
        from tools.wind_service import WindSceneAdapter

        self._show_loading("Rüzgar bölgeleri hesaplanıyor...")

        def _async_wind():
            try:
                created_zones = WindSceneAdapter.run_wind_analysis_and_update_scene(
                    scene=self.scene,
                    w_dir=w_dir,
                    wind_config=config
                )
                Clock.schedule_once(lambda dt: self._on_wind_done(len(created_zones)), 0)
            except Exception as e:
                logger.error(f"Rüzgar analizi hatası: {e}", exc_info=True)
                Clock.schedule_once(lambda dt: self._show_error(f"Rüzgar Hesabı Hatası:\n{e}"), 0)

        threading.Thread(target=_async_wind, daemon=True).start()

if __name__ == "__main__":
    MainApp().run()