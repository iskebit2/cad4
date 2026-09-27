
import os
import threading

# ============================================================
# KIVY / OPENGL
# ============================================================

os.environ["KIVY_WINDOW"] = "sdl2"

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

from kivy_3d_widget import KivyCADWidget


Window.size = (1200, 800)


# ============================================================
# CAD APP
# ============================================================

class CADApp(App):

    def build(self):

        root = BoxLayout(
            orientation="vertical"
        )

        # ====================================================
        # TOOLBAR
        # ====================================================

        toolbar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=20,
            spacing=1,
            padding=1
        )

        toolbar.add_widget(self._button("S2K",     self.import_s2k))
        toolbar.add_widget(self._button("Test",    self.load_test_model))
        toolbar.add_widget(self._button("Polygon", self.draw_polygon))
        toolbar.add_widget(self._button("Reset",   self.reset_camera))
        toolbar.add_widget(self._button("Fit",     self.zoom_extents))
        toolbar.add_widget(self._button("Orbit",   self.orbit_mode))
        toolbar.add_widget(self._button("Pan",     self.pan_mode))
        toolbar.add_widget(self._button("Del",     self.delete_selected))
        toolbar.add_widget(self._button("ClrSel",  self.clear_selection))
        toolbar.add_widget(self._button("Node",    self.draw_node))
        toolbar.add_widget(self._button("Line",    self.draw_line))
        toolbar.add_widget(self._button("Area",    self.draw_area))
        toolbar.add_widget(self._button("Z+",      self.zoom_in))
        toolbar.add_widget(self._button("Z-",      self.zoom_out))
        # ====================================================
        # CAD VIEW
        # ====================================================

        self.cad_widget = KivyCADWidget()

        root.add_widget(toolbar)
        root.add_widget(self.cad_widget)

        return root

    # ========================================================
    # BUTTON HELPER
    # ========================================================

    def _button(self, text, callback):
        button = Button(
            text=text,
            size_hint_x=None,
            width=75,      # 95 → 85
            font_size=12,  # metin biraz küçülsün
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

                    print("S2K modeli yüklendi!")

                Clock.schedule_once(
                    apply_scene,
                    0
                )

            except Exception as e:

                print(
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

        print("Test modeli yüklendi!")

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

        print("Orbit modu")

    def pan_mode(self, *_):

        print("Pan modu")

    # ========================================================
    # EDIT
    # ========================================================

    def delete_selected(self, *_):

        if not self.engine:
            return

        selected = self.engine.sel_mgr.get_selected()

        if not selected:
            return

        print(
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

        print("Draw Node")

    def draw_line(self, *_):

        print("Draw Line")

    def draw_area(self, *_):

        print("Draw Area")

    def draw_polygon(self, *_):
        if not self.engine:
            return
        self.engine.draw_mgr.start()

    def delete_selected(self, *_):
        if not self.engine:
            return
        
        deleted, rejected = self.engine.sel_mgr.delete_selected()
        
        if deleted == 0 and rejected == 0:
            print("Silinecek eleman yok")
        elif deleted == 0:
            print(f"{rejected} eleman reddedildi (bağlı eleman var)")
        elif rejected == 0:
            print(f"{deleted} eleman silindi")
        else:
            print(f"{deleted} silindi, {rejected} reddedildi (bağlı)")


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.DEBUG,   # burayı değiştir level=logging.WARNING
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    )

    logging.getLogger().setLevel(logging.DEBUG)
    CADApp().run()