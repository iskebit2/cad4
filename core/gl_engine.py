# core/gl_engine.py
"""
Pure OpenGL + Domain Engine — Kivy bağımsız.

KivyCADWidget bu sınıfı kullanır ama bu sınıf Kivy'yi bilmez.
"""

import time
from pathlib import Path
import glm
from OpenGL.GL import glGetString, GL_VERSION

from render.shaderprogram import ShaderProgram
from core.camera import Camera
from domain.scene import Scene
from core.input_manager import (
    InputManager,
    MOUSE_BUTTON_LEFT,
    MOUSE_BUTTON_RIGHT,
    MOUSE_BUTTON_MIDDLE,
)
from core.selection_policy import SelectionPolicy
from tools.gridsystem import GridSystem
from render.scenerenderer import SceneRenderer
from core.selection_manager import SelectionManager
from core.marquee_selector import MarqueeSelector
from tools.loader import ModelLoader
from core.draw_manager import DrawManager
from render.snapsquare import SnapSquareRenderer
from core.edit.edit_controller import EditController

from logging_config import CadLogger
logger = CadLogger.get(__name__)


# Shader klasörü — modül seviyesinde bir kez
_here = Path(__file__).resolve().parent
SHADER_DIR = _here.parent / "render" / "shaders"


class PureKivyEngine:
    """Kivy'den bağımsız CAD motoru."""

    def __init__(self, w, h):
        self.w, self.h = max(1, w), max(1, h)
        self.pending_anim = False
        self.loading = False

        # Shader'lar
        self.shaders = {}
        self.pick_s = self.standard_s = self.node_s = None
        self.simple_s = self.overlay_s = self.preview_s = self.grid_s = None

        # Hover/pick durumu
        self.hover_id = 0
        self.hover_element_type = None
        self.hover_enabled = True
        self.last_hover_x = -1
        self.last_hover_y = -1
        self.last_hover_time = 0
        self.hover_throttle = 0.05
        self.pending_pick_check = False

        # Alt bileşenler (init_gl'de kurulur)
        self.cam = None
        self.input = None
        self.scene = None
        self.renderer = None
        self.pick_pass = None
        self.sel_mgr = None
        self.marquee = None
        self.loader = None
        self.draw_mgr = None
        self.snap = None
        self.edit = None
        self.sel_policy = None
        self.grid = None

        # Callback'ler (KivyCADWidget bağlar)
        self.on_hover_changed_callback = None

    # ------------------------------------------------------------------
    # INIT
    # ------------------------------------------------------------------
    def init_gl(self):
        """GL context hazır olunca bir kez çağrılır."""
        logger.info("GL_VERSION: %s", glGetString(GL_VERSION))
        self._init_shaders()
        self._init_camera()
        self._init_components()

    def _init_shaders(self):
        shader_list = ["pick", "standard", "node", "simple",
                       "2d_overlay", "preview", "grid"]
        for name in shader_list:
            v = SHADER_DIR / f"{name}.vert"
            f = SHADER_DIR / f"{name}.frag"
            try:
                self.shaders[name] = ShaderProgram(name, str(v), str(f))
            except Exception:
                logger.exception("Shader yükleme hatası (%s)", name)
                self.shaders[name] = None

        self.pick_s = self.shaders.get("pick")
        self.standard_s = self.shaders.get("standard")
        self.node_s = self.shaders.get("node")
        self.simple_s = self.shaders.get("simple")
        self.overlay_s = self.shaders.get("2d_overlay")
        self.preview_s = self.shaders.get("preview")
        self.grid_s = self.shaders.get("grid")

    def _init_camera(self):
        self.cam = Camera()
        self.cam.set_aspect(self.w, self.h)
        self.cam.pitch = 30.0
        self.cam.yaw = -45.0
        self.cam.distance = 50.0
        self.cam._update_position()

    def _init_components(self):
        self.scene = Scene()
        self.input = InputManager()
        self.sel_policy = SelectionPolicy(self.input)
        self.grid = GridSystem(self.grid_s)
        self.snap = SnapSquareRenderer()

        self.renderer = SceneRenderer(
            pick_s=self.pick_s,
            standard_s=self.standard_s,
            node_s=self.node_s,
            simple_s=self.simple_s,
            overlay_s=self.overlay_s,
            w=self.w, h=self.h,
        )
        self.renderer.set_cam(self.cam)
        self.renderer.set_grid(self.grid)
        self.renderer.set_snap(self.snap)
        self.renderer.set_engine(self)

        self.pick_pass = self.renderer.pick_pass
        self.sel_mgr = SelectionManager(self.renderer)
        self.marquee = MarqueeSelector(self, self.sel_mgr, self.sel_policy)
        self.renderer.set_marquee(self.marquee)
        self.loader = ModelLoader(self)
        self.draw_mgr = DrawManager(self)
        self.edit = EditController(self)

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------
    def resize(self, w, h):
        self.w, self.h = max(1, w), max(1, h)
        if self.cam:
            self.cam.set_aspect(self.w, self.h)
        if self.renderer:
            self.renderer.resize(self.w, self.h)
        if self.pick_pass:
            self.pick_pass.set_viewport(self.w, self.h)

    def load_model(self, builder):
        self.scene = builder.scene
        self.renderer.update_geo(self.scene)
        self.fit_view()

    def set_scene(self, scene):
        self.scene = scene
        self.renderer.update_geo(self.scene)
        self.fit_view()

    def clear_scene(self):
        self.scene = Scene()
        self.renderer.set_scene(self.scene)
        for r in (self.renderer.frame_r, self.renderer.node_r,
                  self.renderer.area_r, self.renderer.link_r,
                  self.renderer.polygon_r):
            r.elements = []

    def fit_view(self):
        if not self.renderer:
            return
        self.renderer._update_bounds_from_nodes()
        c, s = self.renderer.get_bounds()
        self.cam.update_bounds(c, s)
        self.cam.focus_on_model()

    def redraw_scene(self, full_rebuild: bool = True):
        if not self.renderer:
            return
        if full_rebuild:
            self.renderer.update_geo(self.scene)
        if hasattr(self.renderer, 'rebuild_pick_ids'):
            self.renderer.rebuild_pick_ids()
        self.pending_anim = True

    # ------------------------------------------------------------------
    # HOVER / PICK (Kivy'den çağrılır)
    # ------------------------------------------------------------------
    def start_hover_pick(self, x, y):
        if not self.renderer or not self.renderer.pick_pass:
            return
        now = time.time()
        if (now - self.last_hover_time) < self.hover_throttle:
            return
        if x == self.last_hover_x and y == self.last_hover_y:
            return
        if self.renderer.pick_async(x, y):
            self.last_hover_x = x
            self.last_hover_y = y
            self.last_hover_time = now
            self.pending_pick_check = True

    def check_pick_result(self):
        if not self.pending_pick_check:
            return False
        try:
            pick_id, _, _ = self.renderer.check_pick()
            if pick_id is not None:
                self.pending_pick_check = False
                self._update_hover(pick_id)
                return True
            elif not self.renderer.pick_pass.pending_pick:
                self.pending_pick_check = False
        except Exception as e:
            logger.error(f"Pick kontrolü hatası: {e}")
            self.pending_pick_check = False
        return False

    def handle_pick_from_hover(self, ctrl=False):
        if self.hover_id > 0 and self.renderer and self.renderer.pick_pass:
            element = self.renderer.get_element_from_id(self.hover_id)
            if element:
                self.sel_mgr.select(element, additive=ctrl)

    def update_world_pos(self, x, y):
        if not self.cam or not self.input:
            return
        if self.hover_id > 0 and self.hover_element_type == 'node':
            return

        v = self.cam.get_view_matrix()
        p = self.cam.get_projection_matrix()
        nx = 2 * x / self.w - 1
        ny = 1 - 2 * y / self.h
        inv = glm.inverse(p * v)

        near = inv * glm.vec4(nx, ny, -1, 1)
        far = inv * glm.vec4(nx, ny, 1, 1)
        near = glm.vec3(near) / near.w
        far = glm.vec3(far) / far.w
        direction = glm.normalize(far - near)

        if abs(direction.z) > 1e-6:
            t = -near.z / direction.z
            if t > 0:
                self.input.mouse_world_pos = near + direction * t
                self.input.mouse_world_valid = True
                return
        self.input.mouse_world_valid = False

    def clear_hover(self):
        self.hover_id = 0
        self.hover_element_type = None
        self.input.mouse_world_valid = False

    def enable_hover(self, enabled=True):
        self.hover_enabled = enabled
        if not enabled and self.hover_id != 0:
            self.hover_id = 0
            self.hover_element_type = None

    # ------------------------------------------------------------------
    # PLAN FILTER (Kivy'den çağrılır)
    # ------------------------------------------------------------------
    def apply_plane_filter(self, plane=None, offset=0.0, direction="positive"):
        """Kameraya plan filter uygula ve sahneyi yeniden build et."""
        if plane is None:
            self.cam.clear_plane_filter()
        else:
            self.cam.set_plane_filter(plane, offset, direction)
        self.renderer.apply_plane_filter(self.cam)
        if self.scene:
            self.renderer.update_geo(self.scene)

    # ------------------------------------------------------------------
    # INTERNAL
    # ------------------------------------------------------------------
    def _update_hover(self, pick_id):
        if pick_id == self.hover_id:
            return
        self.hover_id = pick_id

        if pick_id > 0:
            element = self.renderer.get_element_from_id(pick_id)
            if element is None:
                self.clear_hover()
                return
            element_type = self._element_type(element)
            self.hover_element_type = element_type

            if element_type == 'node' and hasattr(element, 'x'):
                self.input.mouse_world_pos = glm.vec3(element.x, element.y, element.z)
                self.input.mouse_world_valid = True

            # Callback
            if self.on_hover_changed_callback:
                self.on_hover_changed_callback(element)
        else:
            self.clear_hover()
            if self.on_hover_changed_callback:
                self.on_hover_changed_callback(None)

    @staticmethod
    def _element_type(element):
        if element is None:
            return None
        if hasattr(element, 'element_type'):
            return element.element_type
        class_name = element.__class__.__name__.lower()
        for key in ('node', 'frame', 'area', 'link', 'polygon'):
            if key in class_name:
                return key
        return None