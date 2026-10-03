# main.py

import OpenGL
OpenGL.ERROR_CHECKING = False
OpenGL.ERROR_LOGGING = False

from logging_config import CadLogger
logger = CadLogger.get(__name__)

CadLogger.setup(
    "INFO",
    module_levels={
        "core.gl_engine": "INFO",
        "core.draw_manager": "DEBUG",
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
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.uix.floatlayout import FloatLayout
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp

from core.gl_engine import KivyCADWidget
from ui.prop_panel import PropertiesPanel
from ui.toolbar import Toolbar

Window.size = (1200, 800)


# ============================================================
# CAD APP
# ============================================================

class CADApp(App):

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
            ("S2K",     "folder",      self.import_s2k),
            ("Analiz",    "bar-chart-2",         self.run_analysis),
            ("Polygon", "hexagon",     self.draw_polygon),
            None,   # ayırıcı
            ("Reset",   "rotate-ccw",  self.reset_camera),
            ("Fit",     "maximize",    self.zoom_extents),
            None,
            ("Orbit",   "move",        self.orbit_mode),
            ("Pan",     "move",        self.pan_mode),
            None,
            ("Del",     "trash-2",     self.delete_selected),
            ("ClrSel",  "x-circle",    self.clear_selection),
            None,
            ("Node",    "circle",      self.draw_node),
            ("Line",    "minus",       self.draw_line),
            ("Area",    "square",      self.draw_area),
            None,
            ("Z+",      "zoom-in",     self.zoom_in),
            ("Z-",      "zoom-out",    self.zoom_out),
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


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    CADApp().run()