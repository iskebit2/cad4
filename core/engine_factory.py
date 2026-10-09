# core/engine_factory.py
"""
Engine factory — Platform algılaması + fallback.

Android veya OpenGL yüklenemediğinde DummyCADWidget döner.
Masaüstünde gerçek KivyCADWidget döner.
"""

import os
import sys
from logging_config import CadLogger

logger = CadLogger.get(__name__)


# ----------------------------------------------------------------
# PLATFORM ALGILAMA
# ----------------------------------------------------------------
IS_ANDROID = (
    "PYTHON_SERVICE_ARGUMENT" in os.environ
    or hasattr(sys, "getandroidapilevel")
)

ENABLE_3D_GRAPHICS = not IS_ANDROID


# ----------------------------------------------------------------
# DUMMY ENGINE (Android / Headless)
# ----------------------------------------------------------------
class DummyEngine:
    """
    Android veya OpenGL yüklenemediğinde KivyCADWidget yerine geçer.
    MainApp'in çağırdığı tüm engine API'lerini karşılar.
    """

    def __init__(self, scene=None, **kwargs):
        self.scene = scene
        self.w = 0
        self.h = 0

        # Renderer benzeri alt bileşenler (hepsi self'e işaret eder)
        self.renderer = self
        self.cam = self
        self.sel_mgr = self
        self.draw_mgr = self
        self.input = self

        # Paneller
        self.properties = None
        self.properties_panel = None

        # Durum bayrakları
        self.is_active = False
        self.pending_pick_check = False
        self.pending_anim = False
        self.loading = False
        self.hover_id = 0

        # Selection manager callback
        self.on_selection_changed = None

    # --- Engine lifecycle ---
    def init_gl(self):
        pass

    def resize(self, w, h):
        self.w, self.h = max(1, w), max(1, h)

    def set_scene(self, scene):
        self.scene = scene

    def load_model(self, builder):
        self.scene = getattr(builder, "scene", None)

    def clear_scene(self):
        from domain.scene import Scene
        self.scene = Scene()

    def redraw_scene(self, full_rebuild: bool = True):
        pass

    # --- Renderer benzeri ---
    def update_geo(self, scene):
        pass

    def apply_plane_filter(self, plane=None, offset=0.0, direction="positive"):
        pass

    def request_redraw(self):
        pass

    def get_element_from_id(self, pick_id):
        return None

    def _update_grid(self):
        pass

    # --- Kamera ---
    def update_bounds(self, center, size):
        pass

    def focus_on_model(self):
        pass

    def fit_view(self):
        pass

    def zoom(self, delta):
        pass

    def reset(self):
        pass

    def set_view_preset(self, name):
        pass

    def clear_plane_filter(self):
        pass

    def set_plane_filter(self, plane, offset=0.0, direction="positive"):
        pass

    # --- Selection / Draw ---
    def delete_selected(self):
        return 0, 0

    def clear(self):
        pass

    def select(self, element, additive=False):
        pass

    def get_selected(self):
        return []

    def undo(self):
        return False

    def redo(self):
        return False

    # --- Draw Manager ---
    def close(self):
        pass

    def start(self):
        pass

    def cancel(self):
        pass

    # --- Input ---
    def update_modifiers(self, modifiers):
        pass

    def handle_key_up(self, key):
        pass


# ----------------------------------------------------------------
# DUMMY WIDGET (Android / Fallback)
# ----------------------------------------------------------------
def _create_dummy_widget():
    """Android veya OpenGL yüklenemediğinde kullanılacak widget."""
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label

    class DummyCADWidget(BoxLayout):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.engine = DummyEngine()
            self.properties_panel = None
            self.view_panel = None
            self.initialized = True

            self.add_widget(Label(
                text=(
                    "[ 3D Görünüm Devre Dışı ]\n\n"
                    "S2K / CAD Veri ve Analiz Modu Aktif"
                ),
                halign="center",
                color=(0.6, 0.7, 0.8, 1),
            ))

    return DummyCADWidget()


# ----------------------------------------------------------------
# PUBLIC API
# ----------------------------------------------------------------
def create_cad_widget():
    """
    Platform ve OpenGL durumuna göre uygun CAD widget'ı döner.

    Returns:
        KivyCADWidget  → masaüstü, OpenGL OK
        DummyCADWidget → Android veya OpenGL yüklenemedi
    """
    if not ENABLE_3D_GRAPHICS:
        logger.info("Android algılandı — 3D devre dışı, DummyCADWidget dönüyor")
        return _create_dummy_widget()

    # OpenGL yüklenebiliyor mu?
    try:
        import OpenGL
        OpenGL.ERROR_CHECKING = False
        OpenGL.ERROR_LOGGING = False

        # Yeni konum: widgets.cad_widget
        from widgets.cad_widget import KivyCADWidget
        return KivyCADWidget()

    except ImportError as e:
        logger.warning(f"OpenGL yüklenemedi ({e}) — DummyCADWidget dönüyor")
        return _create_dummy_widget()

    except Exception as e:
        logger.exception(f"KivyCADWidget oluşturulamadı: {e}")
        return _create_dummy_widget()