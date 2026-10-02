#main.py
import logging
from kivy.logger import Logger

# Kivy'nin kendi logger seviyesini ayarla
Logger.setLevel(logging.WARNING)

# Kivy'nin kendi handler'larını kaldır
for handler in list(Logger.handlers):
    Logger.removeHandler(handler)

from logging_config import setup_logging, set_level

setup_logging()
logger = logging.getLogger(__name__)

import os
import threading

# ============================================================
# KIVY / OPENGL
# ============================================================

# os.environ["KIVY_WINDOW"] = "sdl2"

from kivy.config import Config

Config.set(
    "input",
    "mouse",
    "mouse,disable_multitouch"
)

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.uix.floatlayout import FloatLayout

from core.gl_engine import KivyCADWidget
from ui.prop_panel import PropertiesPanel

Window.size = (1200, 800)
set_level("core.gl_engine", "INFO")
set_level("ui.prop_panel", "DEBUG")

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
        toolbar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=32,
            spacing=2,
            padding=2
        )

        toolbar.add_widget(self._button("☈ S2K",     self.import_s2k))
        toolbar.add_widget(self._button("☄ Test",    self.load_test_model))
        toolbar.add_widget(self._button("⬡ Polygon", self.draw_polygon))
        toolbar.add_widget(self._button("↻ Reset",   self.reset_camera))
        toolbar.add_widget(self._button("⟷ Fit",     self.zoom_extents))
        toolbar.add_widget(self._button("☌ Orbit",   self.orbit_mode))
        toolbar.add_widget(self._button("☍ Pan",     self.pan_mode))
        toolbar.add_widget(self._button("☓ Del",     self.delete_selected))
        toolbar.add_widget(self._button("☤ ClrSel",  self.clear_selection))
        toolbar.add_widget(self._button("● Node",    self.draw_node))
        toolbar.add_widget(self._button("─ Line",    self.draw_line))
        toolbar.add_widget(self._button("☐ Area",    self.draw_area))
        toolbar.add_widget(self._button("◱ Z+",      self.zoom_in))
        toolbar.add_widget(self._button("◳ Z-",      self.zoom_out))
        # ====================================================
        # CAD VIEW
        # ====================================================

        

        root.add_widget(toolbar)
        
        # 3. Properties panel (sağ üst, floating)
        self.properties = PropertiesPanel(
            pos_hint={'right': 1, 'top': 1},
        )
        self.properties.opacity = 0
        self.properties.disabled = True
        self.properties.pos_hint = {'right': 1, 'top': 0.96}   # toolbar altında
        root.add_widget(self.properties)
        
        # CAD widget'a referans ver
        self.cad_widget.properties_panel = self.properties
        
        return root

    # ========================================================
    # BUTTON HELPER
    # ========================================================

    def _button(self, text, callback):
        button = Button(
            text=text,
            size_hint_x=None,
            width=80,
            font_size=12,
            font_name="DejaVuSans.ttf",
            background_color=(0.25, 0.25, 0.28, 1.0),
            background_normal='',       # default resim kapat
            background_down='',         # basılı hali de aynı
        )
        button.bind(on_release=callback)
        return button

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

        self.engine.clear_scene()

        self.engine.load_prog = 0
        self.engine.load_done = False

        def load():

            try:

                from tools.s2kloader import S2KLoader

                self.engine.load_prog = 20

                scene = S2KLoader().load()

                self.engine.load_prog = 30

                # --------------------------------------------
                # Scene'i UI thread'e aktar
                # --------------------------------------------

                def apply_scene(dt):

                    self.engine.scene = scene

                    self.engine.renderer.update_geo(
                        scene
                    )

                    self.engine.load_done = True

                    self.cad_widget._fit_view()

                    logger.info("S2K modeli yüklendi!")

                Clock.schedule_once(
                    apply_scene,
                    0
                )

            except Exception as e:

                logger.info(
                    f"S2K yükleme hatası: {e}"
                )

                self.engine.load_done = True

        threading.Thread(
            target=load,
            daemon=True
        ).start()

        self.cad_widget._fit_view()

    # ========================================================
    # TEST MODEL
    # ========================================================

    def load_test_model(self, *_):

        if not self.engine:
            return

        from geometry.scenebuilder import SceneBuilder
        from tests.test_model import TestModelBuilder

        builder = SceneBuilder()

        TestModelBuilder.build(builder)

        self.engine.scene = builder.scene

        self.engine.renderer.update_geo(
            builder.scene
        )

        logger.info("Test modeli yüklendi!")

        self.cad_widget._fit_view()

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

        selected = self.engine.sel_mgr.get_selected()

        if not selected:
            return

        logger.info(
            f"Silinecek eleman sayısı: {len(selected)}"
        )

        # Burada mevcut delete mekanizmasını bağlayacağız.

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


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    CADApp().run()