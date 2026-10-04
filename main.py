# main.py

import OpenGL

from ui.panel_inspector import ModelInspectorPanel
OpenGL.ERROR_CHECKING = False
OpenGL.ERROR_LOGGING = False

from logging_config import CadLogger
logger = CadLogger.get(__name__)

CadLogger.setup(
    "INFO",
    module_levels={
        "core.gl_engine": "INFO",
        "core.draw_manager": "INFO",
        "OpenGL": "WARNING",
        "kivy": "WARNING",
    },
)



import threading

from kivy.config import Config
Config.set("input", "mouse", "mouse,disable_multitouch")

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.textinput import TextInput
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.uix.floatlayout import FloatLayout
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.popup import Popup

from core.gl_engine import KivyCADWidget
from ui.prop_panel import PropertiesPanel
from ui.toolbar import Toolbar


Window.size = (1200, 800)


# ============================================================
# CAD APP
# ============================================================

class CADApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cad_widget = None
        self.inspector_popup = None
        self.project_popup = None
        self._project_panel = None 
        self.current_path = ""

    def build(self):
        root = FloatLayout()
        
        # 1. CAD widget (arkada)
        self.cad_widget = KivyCADWidget(
            size_hint=(1, 1),
            pos_hint={'x': 0, 'y': 0},
        )
        root.add_widget(self.cad_widget)
        
        # 2. Toolbar (üstte)
        toolbar = Toolbar(actions=[
                        # --- File ---
                        ("Yeni",       "file",         self.action_new),                  # ← YENİ
                        ("Aç",         "folder",       self.action_open),                 # ← YENİ
                        ("Kaydet",     "save",         self.action_save),                 # ← YENİ
                        None,

                        # --- S2K ---
                        ("S2K",        "folder",       self.import_s2k),
                        ("S2K Tanım",  "list",         self.action_import_s2k_definition),  # ← YENİ
                        None,

                        # --- Analysis ---
                        ("Analiz",     "bar-chart-2",  self.run_analysis),
                        ("Inspector",  "briefcase",    self.show_inspector),
                        ("Project",    "database",     self.show_project_data),           # ← YENİ
                        None,

                        # --- Draw ---
                        ("Polygon",    "hexagon",      self.draw_polygon),
                        None,

                        # --- View ---
                        ("Reset",      "rotate-ccw",   self.reset_camera),
                        ("Fit",        "maximize",     self.zoom_extents),
                        None,

                        # --- Modes ---
                        ("Orbit",      "move",         self.orbit_mode),
                        ("Pan",        "move",         self.pan_mode),
                        None,

                        # --- Edit ---
                        ("Del",        "trash-2",      self.delete_selected),
                        ("ClrSel",     "x-circle",     self.clear_selection),
                        None,

                        # --- Draw primitives ---
                        ("Node",       "circle",       self.draw_node),
                        ("Line",       "minus",        self.draw_line),
                        ("Area",       "square",       self.draw_area),
                        None,

                        # --- Zoom ---
                        ("Z+",         "zoom-in",      self.zoom_in),
                        ("Z-",         "zoom-out",     self.zoom_out),
                    ])
        root.add_widget(toolbar)
        
        # 3. Properties panel (sağ üst, floating)
        self.properties = PropertiesPanel(
            pos_hint={'right': 1, 'top': 0.96},
        )
        self.properties.opacity = 0
        self.properties.disabled = True
        root.add_widget(self.properties)
        
        self.cad_widget.properties_panel = self.properties
        
        # 4. Sağ altta küçük yükleme göstergesi
        self.loading_indicator = self._make_loading_indicator()
        self.loading_indicator.opacity = 0
        self.loading_indicator.disabled = True
        root.add_widget(self.loading_indicator)
        
        return root

    # ========================================================
    # LOADING INDICATOR
    # ========================================================

    def _make_loading_indicator(self):
        """Sağ altta küçük yükleme göstergesi."""
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
        
        # İkon (feather loader)
        from pathlib import Path
        icon_path = Path("assets/icons/loader.png")
        
        if icon_path.exists():
            from kivy.uix.image import Image
            icon = Image(
                source=str(icon_path),
                size_hint=(None, None),
                size=(dp(18), dp(18)),
            )
        else:
            # Fallback: Unicode
            icon = Label(
                text="⟳",
                font_size=dp(20),
                size_hint=(None, 1),
                width=dp(24),
                color=(0.5, 0.8, 1.0, 1.0),
            )
        
        box.add_widget(icon)
        
        label = Label(
            text="Yükleniyor...",
            font_size=dp(11),
            color=(0.9, 0.9, 0.9, 1.0),
            halign='left',
            valign='middle',
        )
        label.bind(size=label.setter('text_size'))
        box.add_widget(label)
        
        box.icon = icon
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

    # ========================================================
    # ENGINE
    # ========================================================

    @property
    def engine(self):
        return self.cad_widget.engine

    # ========================================================
    # FILE
    # ========================================================

    def import_s2k(self, *_):
        if not self.engine:
            return
        
        self._show_loading("S2K yükleniyor...")
        
        def load_thread():
            try:
                from tools.s2kloader import S2KLoader
                scene = S2KLoader().load()
                
                Clock.schedule_once(
                    lambda dt: self._apply_scene(scene),
                    0
                )
            except Exception as e:
                logger.error(f"S2K yükleme hatası: {e}", exc_info=True)
                Clock.schedule_once(lambda dt: self._hide_loading(), 0)
        
        threading.Thread(target=load_thread, daemon=True).start()

    def _apply_scene(self, scene):
        try:
            self.engine.scene = scene
            self.engine.renderer.set_scene(scene)
            self.engine.renderer.update_geo(scene)
            
            c, s = self.engine.renderer.get_bounds()
            self.engine.cam.update_bounds(c, s)
            self.engine.cam.focus_on_model()
            self.engine.renderer._update_grid()
            
            self.engine.pending_anim = True
            
            logger.info("S2K modeli yüklendi!")
        except Exception as e:
            logger.error(f"_apply_scene hatası: {e}", exc_info=True)
        finally:
            Clock.schedule_once(lambda dt: self._hide_loading(), 0)

    # ========================================================
    # ANALİZ
    # ========================================================

    def show_inspector(self, *_):
        if not self.cad_widget.engine:
            logger.warning("Engine hazır değil")
            return

        if self.inspector_popup:
            return

        panel = ModelInspectorPanel(
            scene=self.cad_widget.engine.scene
        )

        self.inspector_popup = Popup(
            title="Model Inspector",
            content=panel,
            size_hint=(0.9, 0.9),
        )

        self.inspector_popup.bind(
            on_dismiss=self._inspector_closed
        )

        self.inspector_popup.open()


    def _inspector_closed(self, *_):
        self.inspector_popup = None

    def run_analysis(self, *_):
        """Analizleri çalıştır ve popup'ta göster."""
        if not self.engine:
            logger.warning("Engine hazır değil")
            return
        
        try:
            from core.analysis_bridge import scene_to_project_data
            from ui.analysis_popup import AnalysisPopup
            
            # Scene → proje_data
            data = scene_to_project_data(self.engine.scene)
            
            # Popup aç
            AnalysisPopup(proje_data=data).open()
            
            logger.info("Analiz popup açıldı")
        
        except Exception as e:
            logger.error(f"Analiz hatası: {e}", exc_info=True)

    # ========================================================
    # VIEW
    # ========================================================

    def zoom_in(self, *_):
        if self.engine:
            self.engine.cam.zoom(1.0)

    def zoom_out(self, *_):
        if self.engine:
            self.engine.cam.zoom(-1.0)

    def zoom_extents(self, *_):
        if self.engine:
            self.engine.fit_view()

    def reset_camera(self, *_):
        if self.engine:
            self.engine.cam.reset()

    # ========================================================
    # CAMERA MODES
    # ========================================================

    def orbit_mode(self, *_):
        logger.info("Orbit modu")

    def pan_mode(self, *_):
        logger.info("Pan modu")

    # ========================================================
    # EDIT
    # ========================================================

    def delete_selected(self, *_):
        if not self.engine:
            return
        
        deleted, rejected = self.engine.sel_mgr.delete_selected()
        
        if deleted == 0 and rejected == 0:
            logger.info("Silinecek eleman yok")
        elif deleted == 0:
            logger.info(f"{rejected} eleman reddedildi (bağlı eleman var)")
        elif rejected == 0:
            logger.info(f"{deleted} eleman silindi")
        else:
            logger.info(f"{deleted} silindi, {rejected} reddedildi (bağlı)")

    def clear_selection(self, *_):
        if self.engine:
            self.engine.sel_mgr.clear()

    # ========================================================
    # DRAW
    # ========================================================

    def draw_node(self, *_):
        logger.info("Draw Node")

    def draw_line(self, *_):
        logger.info("Draw Line")

    def draw_area(self, *_):
        logger.info("Draw Area")

    def draw_polygon(self, *_):
        if not self.engine:
            return
        self.engine.draw_mgr.start()

    def show_project_data(self, *_):
        """Definition verisini popup'ta göster."""
        if not self.engine:
            logger.warning("Engine hazır değil")
            return
        if self.project_popup:
            return

        from gui.project_data_panel import ProjectDataPanel

        scene = self.engine.scene
        manager = getattr(scene, "def_mgr", None)
        if manager is None:
            logger.warning("scene.def_mgr yok — boş panel açılıyor")
            from domain.definition_manager import DefinitionManager
            manager = DefinitionManager()

        panel = ProjectDataPanel(
            manager=manager,
            on_change=self._on_project_data_changed,
        )
        self._project_panel = panel   # referans tut

        self.project_popup = Popup(
            title="Project Data",
            content=panel,
            size_hint=(0.92, 0.92),
        )
        self.project_popup.bind(on_dismiss=self._project_closed)
        self.project_popup.open()


    def _project_closed(self, *_):
        self.project_popup = None
        self._project_panel = None


    def _on_project_data_changed(self):
        """DefinitionManager değişti → CAD'i yeniden çiz."""
        logger.info("[Main] Project data değişti, CAD yeniden çiziliyor")
        try:
            if hasattr(self.engine, "request_redraw"):
                self.engine.request_redraw()
            elif hasattr(self.engine.renderer, "update_geo"):
                self.engine.renderer.update_geo(self.engine.scene)
        except Exception as e:
            logger.warning(f"Redraw hatası: {e}")


    # ========================================================
    # FILE — New / Open / Save / Save As
    # ========================================================

    def action_new(self, *_):
        """Yeni proje — mevcut manager'ı YERİNDE sıfırla (referansı koparma)."""
        if not self.engine:
            return

        scene = self.engine.scene
        manager = getattr(scene, "def_mgr", None)
        if manager is None:
            return

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

        logger.info("[Main] Yeni proje")


    def action_open(self, *_):
        """JSON projeden yükle → mevcut manager'a in-place."""
        if not self.engine:
            return

        def on_file(path: str):
            try:
                from data.serializer import load_project
                scene = self.engine.scene
                manager = getattr(scene, "def_mgr", None)
                if manager is None:
                    from domain.definition_manager import DefinitionManager
                    manager = DefinitionManager()
                    scene.def_mgr = manager

                load_project(manager, path)
                self.current_path = path

                self._on_project_data_changed()
                if self._project_panel:
                    self._project_panel.refresh()

                logger.info(f"[Main] Proje açıldı: {path}")
            except Exception as e:
                logger.error(f"Proje açma hatası: {e}", exc_info=True)
                self._show_error(str(e))

        self._pick_file(
            mode="open",
            filters=["*.json"],
            on_select=on_file,
        )


    def action_save(self, *_):
        """Kaydet — path varsa direkt, yoksa Save As."""
        if self.current_path:
            try:
                from data.serializer import save_project
                save_project(self.engine.scene.def_mgr, self.current_path)
                logger.info(f"[Main] Kaydedildi: {self.current_path}")
            except Exception as e:
                logger.error(f"Kaydetme hatası: {e}", exc_info=True)
                self._show_error(str(e))
        else:
            self.action_save_as()


    def action_save_as(self, *_):
        def on_file(path: str):
            try:
                from data.serializer import save_project
                save_project(self.engine.scene.def_mgr, path)
                self.current_path = path
                logger.info(f"[Main] Kaydedildi: {path}")
            except Exception as e:
                logger.error(f"Kaydetme hatası: {e}", exc_info=True)
                self._show_error(str(e))

        self._pick_file(
            mode="save",
            filters=["*.json"],
            on_select=on_file,
            default_name="project.json",
        )


    # ========================================================
    # S2K IMPORT / EXPORT (definition tablosu)
    # ========================================================

    def action_import_s2k_definition(self, *_):
        """S2K'dan SADECE definition tablolarını içe aktar (geometri yok)."""
        if not self.engine:
            return

        def on_file(path: str):
            self._show_loading("S2K tanımları yükleniyor...")

            def worker():
                try:
                    from data.s2k_importer import S2KParser
                    scene = self.engine.scene
                    manager = getattr(scene, "def_mgr", None)
                    if manager is None:
                        from domain.definition_manager import DefinitionManager
                        manager = DefinitionManager()
                        scene.def_mgr = manager

                    S2KParser(path).import_to(manager)

                    Clock.schedule_once(
                        lambda dt: self._after_import_definition(), 0
                    )
                except Exception as e:
                    logger.error(f"S2K definition import hatası: {e}", exc_info=True)
                    Clock.schedule_once(lambda dt: self._hide_loading(), 0)

            threading.Thread(target=worker, daemon=True).start()

        self._pick_file(
            mode="open",
            filters=["*.s2k"],
            on_select=on_file,
        )


    def _after_import_definition(self):
        self._hide_loading()
        self._on_project_data_changed()
        if self._project_panel:
            self._project_panel.refresh()
        logger.info("[Main] S2K definition import tamam")


    def action_export_s2k_definition(self, *_):
        """Definition tablolarını S2K olarak dışa aktar."""
        if not self.engine:
            return

        def on_file(path: str):
            try:
                from data.s2k_exporter import S2KWriter
                S2KWriter(self.engine.scene.def_mgr).write(path)
                logger.info(f"[Main] S2K dışa aktarıldı: {path}")
            except Exception as e:
                logger.error(f"S2K export hatası: {e}", exc_info=True)
                self._show_error(str(e))

        self._pick_file(
            mode="save",
            filters=["*.s2k"],
            on_select=on_file,
            default_name="export.s2k",
        )


    # ========================================================
    # YARDIMCI: File dialog + Hata popup
    # ========================================================

    def _pick_file(self, mode: str, filters: list, on_select, default_name: str = ""):
        """
        mode: 'open' | 'save'
        on_select: (path: str) -> None
        """
        import os

        fc = FileChooserListView(filters=filters, path=os.getcwd())
        box = BoxLayout(orientation="vertical", spacing=4, padding=4)
        box.add_widget(fc)

        name_input = None
        if mode == "save":
            name_input = TextInput(
                text=default_name,
                size_hint_y=None, height=36,
                hint_text="Dosya adı",
            )
            box.add_widget(name_input)

        btn_row = BoxLayout(size_hint_y=None, height=44, spacing=6)
        ok_btn = Button(text="Tamam")
        cancel_btn = Button(text="İptal")
        btn_row.add_widget(ok_btn)
        btn_row.add_widget(cancel_btn)
        box.add_widget(btn_row)

        popup = Popup(title="Dosya Seç", content=box,
                    size_hint=(0.9, 0.9))

        def on_ok(*_):
            try:
                if mode == "save":
                    if not name_input.text:
                        return
                    base = fc.path or os.getcwd()
                    path = os.path.join(base, name_input.text)
                else:
                    if not fc.selection:
                        return
                    path = fc.selection[0]

                popup.dismiss()
                on_select(path)
            except Exception as e:
                logger.error(f"File dialog hatası: {e}", exc_info=True)

        ok_btn.bind(on_release=on_ok)
        cancel_btn.bind(on_release=lambda *_: popup.dismiss())
        popup.open()


    def _show_error(self, message: str):
        box = BoxLayout(orientation="vertical", padding=10, spacing=8)
        box.add_widget(Label(text=message))
        btn = Button(text="Tamam", size_hint_y=None, height=40)
        box.add_widget(btn)
        popup = Popup(title="Hata", content=box, size_hint=(0.6, 0.4))
        btn.bind(on_release=lambda *_: popup.dismiss())
        popup.open()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    CADApp().run()