# core/engine_factory.py

import os
import sys
from logging_config import CadLogger

logger = CadLogger.get(__name__)

# Android ortamı mı yoksa masaüstü mü kontrolü

IS_ANDROID = "PYTHON_SERVICE_ARGUMENT" in os.environ or hasattr(sys, "getandroidapilevel")
ENABLE_3D_GRAPHICS = not IS_ANDROID

class DummyEngine:
    """Android / Headless modda 3D OpenGL motorunun yerini alan sahte motor."""
    def __init__(self, scene=None, **kwargs):
        self.scene = scene
        self.renderer = self
        self.cam = self
        self.sel_mgr = self
        self.draw_mgr = self
        self.properties = None
        self.properties_panel = None

    # --- Engine & Renderer ---
    def set_scene(self, scene):
        self.scene = scene

    def update_geo(self, scene):
        pass

    def request_redraw(self):
        pass

    def _update_grid(self):
        pass

    # --- Camera ---
    def update_bounds(self, center, size):
        pass

    def focus_on_model(self):
        pass

    def zoom(self, delta):
        pass

    def reset(self):
        pass

    # --- Selection / Draw ---
    def delete_selected(self):
        return 0, 0

    def clear(self):
        pass

    def start(self):
        pass


def create_cad_widget():
    if ENABLE_3D_GRAPHICS:
        try:
            import OpenGL
            OpenGL.ERROR_CHECKING = False
            OpenGL.ERROR_LOGGING = False
            
            from core.gl_engine import KivyCADWidget
            return KivyCADWidget()
        except ImportError:
            pass  # C kütüphaneleri eksikse fallback yap

    # Android veya OpenGL yüklenemediyse:
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label

    class DummyCADWidget(BoxLayout):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.engine = DummyEngine()
            
            # 3D ekranın yerine yakışıklı bir bilgilendirme
            self.add_widget(Label(
                text="[ 3D Görünüm Devre Dışı ]\n\nS2K / CAD Veri ve Analiz Modu Aktif",
                halign="center",
                color=(0.6, 0.7, 0.8, 1)
            ))

    return DummyCADWidget()