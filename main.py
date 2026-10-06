import os
import sys
from pathlib import Path
import threading

from gui.prop_panel import PropertiesPanel

# --- PYDROID / TERMUX DİZİN VE HİYERARŞİ DÜZELTİCİ ---
FILE_DIR = Path(__file__).resolve().parent
if str(FILE_DIR) not in sys.path:
    sys.path.insert(0, str(FILE_DIR))
# ----------------------------------------------------

os.environ["KIVY_LOG_LEVEL"] = "warning"

from kivy.app import App
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.floatlayout import FloatLayout

from logging_config import CadLogger
logger = CadLogger.get(__name__)
logger.setup("INFO")

from core.engine_factory import create_cad_widget
from gui.panel_main_menu import MainMenuPanel
from gui.panel_inspector import ModelInspectorPanel
from gui.analysis_popup import AnalysisPopup
from gui.basecustompopup import BaseCustomPopup, FONT_DEFAULT



class MainApp(App):
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cad_widget = None
        self.inspector_popup = None
        self.project_popup = None
        self._project_panel = None 
        self.menu_popup = None
        self.current_path = ""
        self._picker_open = False
        
        
        # ANA VERİ
        from domain.scene import Scene
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
        
        # Ekran/Panel referans takibi
        self.menu_popup = None
        self.inspector_popup = None
        self.analysis_popup = None

        # Model/Sahne Verisi
        self.scene = self._load_initial_scene()

        

        # Üst Araç Çubuğu (Toolbar)
        toolbar = BoxLayout(
            size_hint_y=None,
            height=dp(48),
            spacing=dp(8),
            padding=(dp(8), dp(4))
        )

        # Hamburger / Ana Menü Butonu
        
        btn_menu = Button(
            text="☰",
            size_hint_x=None,
            width=dp(20),
            font_size=dp(14),
            font_name="DejaVuSans.ttf",
            background_normal="",
            background_color=(0.15, 0.20, 0.28, 1),
            color=(0.9, 0.9, 0.9, 1),
            bold=True
        )
        btn_menu.bind(on_release=self.open_main_menu)
        toolbar.add_widget(btn_menu)

        btn_import = Button(
                    text="-> Import",
                    size_hint_x=None,
                    width=dp(120),
                    font_size=dp(14),
                    font_name="DejaVuSans.ttf",
                    background_normal="",
                    background_color=(0.15, 0.20, 0.28, 1),
                    color=(0.9, 0.9, 0.9, 1),
                    bold=True
                )
        btn_import.bind(on_release=self._import_from_sap)
        toolbar.add_widget(btn_import)

        # Durum Başlığı
        lbl_info = Label(
            text="MODEL: AKTİF",
            halign="left",
            valign="middle",
            color=(0.6, 0.65, 0.72, 1)
        )
        lbl_info.bind(size=lbl_info.setter("text_size"))
        toolbar.add_widget(lbl_info)

        root.add_widget(toolbar)

        # Orta Alan (Viewport / Çizim Alanı Temsili)
        # viewport_placeholder = Label(
        #     text="[ CAD Viewport / Çizim Alanı ]\n\nÜst menüden veya Ana Menüden panelleri açabilirsiniz.",
        #     halign="center",
        #     valign="middle",
        #     color=(0.4, 0.45, 0.5, 1)
        # )
        # root.add_widget(viewport_placeholder)

        # 3. Properties panel (sağ üst, floating)
        self.properties = PropertiesPanel(pos_hint={'right': 1, 'top': 0.96},)
        root.add_widget(self.properties)
        self.properties.hide()     
        
        self.cad_widget.properties_panel = self.properties
        
        # 4. Yükleme göstergesi
        self.loading_indicator = self._make_loading_indicator()
        self.loading_indicator.opacity = 0
        self.loading_indicator.disabled = True
        root.add_widget(self.loading_indicator)

        return root

    def _load_initial_scene(self):
        """Örnek/Varsayılan sahne verisini hazırlar."""
        try:
            from structload.data.defaults import proje_data
            return proje_data
        except ImportError:
            return {
                "units": "kN-m",
                "snow_config": {},
                "earthquake_config": {},
                "polygons": {}
            }

    # ========================================================
    # LOADING INDICATOR
    # ========================================================

    def _make_loading_indicator(self):
        box = BoxLayout(
            orientation='horizontal',
            size_hint=(None, None),
            size=(dp(150), dp(34)),
            pos_hint={'right': 1, 'y': 0},
            spacing=dp(6),
            padding=(dp(8), dp(4)),
        )
        
        with box.canvas.before:
            Color(0.15, 0.18, 0.24, 0.9)
            box._bg = RoundedRectangle(
                pos=box.pos,
                size=box.size,
                radius=[dp(6)],
            )
        
        def _update_bg(*args):
            box._bg.pos = box.pos
            box._bg.size = box.size
        
        box.bind(pos=_update_bg, size=_update_bg)
        
        label = Label(
            text="Yükleniyor...",
            font_size=dp(11),
            color=(0.9, 0.9, 0.9, 1.0),
            halign='left',
            valign='middle',
        )
        label.bind(size=label.setter('text_size'))
        box.add_widget(label)
        
        box.label = label
        return box

    def _show_loading(self, text="Yükleniyor..."):
        if not hasattr(self, 'loading_indicator'):
            return
        self.loading_indicator.label.text = text
        self.loading_indicator.opacity = 1
        self.loading_indicator.disabled = False

    def _hide_loading(self):
        if not hasattr(self, 'loading_indicator'):
            return
        self.loading_indicator.opacity = 0
        self.loading_indicator.disabled = True

    # ============================================================
    # PANEL YÖNETİM METOTLARI (ÇİFTE POPUP OLMADAN DOĞRUDAN ÇAĞRILAR)
    # ============================================================

    def open_main_menu(self, *_):
        """Tüm araçları derli toplu gruplar halinde sunan ana menü."""
        logger.info("[UserAction] Hamburger Menü açıldı.")
        
        if self.menu_popup:
            return

        self.menu_popup = MainMenuPanel(on_action_selected=self.on_menu_choice)
        self.menu_popup.bind(on_dismiss=lambda *_: setattr(self, 'menu_popup', None))
        self.menu_popup.open()

    def on_menu_choice(self, action_key):
        """Ana menüdeki buton tıklamalarını ilgili panellere yönlendirir."""
        logger.info(f"[UserAction] Menü seçimi yapıldı: {action_key}")
        
        if action_key == "inspector":
            self.show_inspector()
        elif action_key == "analysis":
            self.show_analysis()
        elif action_key == "materials":
            logger.info("Malzeme/Kesit paneli yakında...")
        elif action_key == "reports":
            logger.info("Raporlama paneli yakında...")
        elif action_key == "files":
            self.import_s2k()
            logger.info("Dosya işlemleri paneli yakında...")
        elif action_key == "settings":
            logger.info("Ayarlar paneli yakında...")

    def show_inspector(self, *_):
        """Model Inspector panelini açar."""
        if self.inspector_popup:
            return

        logger.info("[UserAction] Model Inspector açılıyor.")
        self.inspector_popup = ModelInspectorPanel(scene=self.scene)
        self.inspector_popup.bind(on_dismiss=lambda *_: setattr(self, 'inspector_popup', None))
        self.inspector_popup.open()

    def show_analysis(self, *_):
        """Yapısal Analiz ve Yük Raporu panelini açar."""
        if self.analysis_popup:
            return

        logger.info("[UserAction] Analiz Raporu açılıyor.")
        self.analysis_popup = AnalysisPopup(proje_data=self.scene)
        self.analysis_popup.bind(on_dismiss=lambda *_: setattr(self, 'analysis_popup', None))
        self.analysis_popup.open()

    def import_s2k(self, *_):
        def on_file(path: str):
            logger.info(f"[UserAction] S2K Dosyası Seçildi -> {path}")
            self._show_loading("S2K yükleniyor...")
            
            def load_thread():
                try:
                    from tools.s2kloader import S2KLoader
                    scene = S2KLoader(path).load()
                    Clock.schedule_once(lambda dt: self._apply_scene(scene), 0)
                except Exception as e:
                    logger.error(f"S2K yükleme hatası: {e}", exc_info=True)
                    Clock.schedule_once(lambda dt: self._on_import_error(str(e)), 0)
            
            threading.Thread(target=load_thread, daemon=True).start()

        self._pick_file(mode="open", filters=["*.s2k"], on_select=on_file)

    def _on_import_error(self, error_msg: str):
        self._hide_loading()
        self._show_error(f"S2K Yüklenemedi:\n{error_msg}")

    def _apply_scene(self, scene):
        try:
            self.scene = scene
            if self.engine:
                self.engine.set_scene(scene)
                # self.engine.update_geo(scene)
                # self.engine.focus_on_model()
                
            logger.info("[Main] Sahne başarıyla güncellendi!")
        except Exception as e:
            logger.error(f"_apply_scene hatası: {e}", exc_info=True)
        finally:
            Clock.schedule_once(lambda dt: self._hide_loading(), 0)

    # ========================================================
    # VIEW & CAMERA
    # ========================================================

    def zoom_in(self, *_):
        if self.engine: self.engine.zoom(1.0)

    def zoom_out(self, *_):
        if self.engine: self.engine.zoom(-1.0)

    def zoom_extents(self, *_):
        if self.engine: self.engine.focus_on_model()

    def reset_camera(self, *_):
        if self.engine: self.engine.reset()

    # ========================================================
    # EDIT & DRAW
    # ========================================================

    def delete_selected(self, *_):
        if self.engine: self.engine.delete_selected()

    def clear_selection(self, *_):
        if self.engine: self.engine.clear()

    def draw_node(self, *_): pass
    def draw_line(self, *_): pass
    def draw_area(self, *_): pass

    def draw_polygon(self, *_):
        if self.engine: self.engine.start()

    # ========================================================
    # FILE ACTIONS
    # ========================================================

    def action_new(self, *_):
        manager = getattr(self.scene, "def_mgr", None)
        if manager:
            manager.materials.clear()
            manager.sections.clear()
            manager.link_props.clear()
            manager.load_patterns.clear()
            manager.load_cases.clear()
            manager.modal_cases.clear()
            manager.combinations.clear()
            manager.spectrum_functions.clear()
            manager.response_spectrum_cases.clear()
            manager.auto_seismics.clear()
            manager.mass_source_map.clear()

        self.current_path = ""
        self._on_project_data_changed()
        if self._project_panel:
            self._project_panel.refresh()

        logger.info("[UserAction] Yeni temiz proje başlatıldı.")

    def action_open(self, *_):
        def on_file(path: str):
            logger.info(f"[UserAction] JSON Proje Açılıyor -> {path}")
            try:
                from data.serializer import load_project
                manager = getattr(self.scene, "def_mgr", None)
                if manager is None:
                    from domain.definition_manager import DefinitionManager
                    manager = DefinitionManager()
                    self.scene.def_mgr = manager

                load_project(manager, path)
                self.current_path = path

                self._on_project_data_changed()
                if self._project_panel:
                    self._project_panel.refresh()

            except Exception as e:
                logger.error(f"Proje açma hatası: {e}", exc_info=True)
                self._show_error(str(e))

        self._pick_file(mode="open", filters=["*.json"], on_select=on_file)

    def action_save(self, *_):
        if self.current_path:
            try:
                from data.serializer import save_project
                manager = getattr(self.scene, "def_mgr", None)
                if manager:
                    save_project(manager, self.current_path)
                    logger.info(f"[UserAction] Proje Kaydedildi -> {self.current_path}")
            except Exception as e:
                logger.error(f"Kaydetme hatası: {e}", exc_info=True)
                self._show_error(str(e))
        else:
            self.action_save_as()

    def action_save_as(self, *_):
        def on_file(path: str):
            try:
                from data.serializer import save_project
                manager = getattr(self.scene, "def_mgr", None)
                if manager:
                    save_project(manager, path)
                    self.current_path = path
                    logger.info(f"[UserAction] Proje Farklı Kaydedildi -> {path}")
            except Exception as e:
                logger.error(f"Kaydetme hatası: {e}", exc_info=True)
                self._show_error(str(e))

        self._pick_file(mode="save", filters=["*.json"], on_select=on_file, default_name="project.json")

    # ========================================================
    # FILE PICKER
    # ========================================================

    def _pick_file(self, mode: str, filters: list, on_select, default_name: str = ""):
        if getattr(self, "_picker_open", False):
            return
        
        self._picker_open = True
        logger.info(f"[UserAction] Dosya Seçici Açıldı (Mod: {mode}, Filtre: {filters})")

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
                multiline=False
            )
            box.add_widget(name_input)

        # Buton Satırı
        btn_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        
        ok_btn = Button(
            text="Tamam",
            font_name=FONT_DEFAULT,
            background_normal="",
            background_color=(0.18, 0.50, 0.32, 1), # Yeşil ton
            color=(1, 1, 1, 1),
            bold=True
        )
        cancel_btn = Button(
            text="İptal",
            font_name=FONT_DEFAULT,
            background_normal="",
            background_color=(0.40, 0.40, 0.40, 1),
            color=(1, 1, 1, 1)
        )
        
        btn_row.add_widget(ok_btn)
        btn_row.add_widget(cancel_btn)
        box.add_widget(btn_row)

        # BaseCustomPopup parametre imzasını doğru kullanarak oluşturuyoruz
        popup = BaseCustomPopup(
            title_text="Dosya Seç",
            content_widget=box,
            size_hint=(0.90, 0.90)
        )

        processed = [False]

        def finish_and_close(selected_path=None):
            if processed[0]:
                return
            processed[0] = True
            self._picker_open = False
            popup.dismiss()
            if selected_path:
                on_select(selected_path)

        def on_ok(*_):
            if mode == "save":
                if not name_input or not name_input.text.strip(): 
                    return
                base = fc.path or os.getcwd()
                path = os.path.join(base, name_input.text.strip())
                finish_and_close(path)
            else:
                if fc.selection:
                    finish_and_close(fc.selection[0])

        def on_cancel(*_):
            logger.info("[UserAction] Dosya seçimi iptal edildi.")
            finish_and_close(None)

        ok_btn.bind(on_release=on_ok)
        cancel_btn.bind(on_release=on_cancel)
        fc.bind(on_submit=lambda instance, selection, touch: on_ok())

        # Pencere sağ üstteki [X] butonundan veya dışarıdan kapatılırsa bayrağı sıfırla
        popup.bind(on_dismiss=lambda *_: setattr(self, '_picker_open', False))

        popup.open()

    def _import_from_sap(self, *_):
        from tools.sap_connect import cSap
        from exchange.cad4_sap_exchange import import_sap_to_scene

        sap = cSap()
        sap.set_units(9)                    # N, mm, C

        counts = import_sap_to_scene(
            sap,
            self.engine.scene,              # ← mevcut sahne
            # selection_only=True,
            # on_done=lambda: self._after_sap_import(),
        )
        print(counts)


        if counts:
            self.engine.renderer.update_geo(self.engine.scene)
            self.engine.fit_view()




if __name__ == "__main__":
    MainApp().run()