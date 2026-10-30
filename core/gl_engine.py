# core/gl_engine.py
"""
Pure OpenGL + Domain Engine — Kivy bağımsız.

KivyCADWidget bu sınıfı kullanır ama bu sınıf Kivy'yi bilmez.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Sequence, TYPE_CHECKING

from pyglm import glm
import numpy as np

glm.silence(2)
from OpenGL.GL import GL_VERSION, glGetString

from core.camera import Camera
from core.draw_manager import DrawManager
from core.edit.edit_controller import EditController
from core.input_manager import (
    InputManager,
)
from core.marquee_selector import MarqueeSelector
from core.selection_manager import SelectionManager
from core.selection_policy import SelectionPolicy
from domain.scene import Scene

# from tools.smart_plane_analysis import SmartPlaneAnalyzer
from logging_config import CadLogger
from render.scenerenderer import SceneRenderer
from render.shaderprogram import ShaderProgram
from render.snapsquare import SnapSquareRenderer
from tools.gridsystem import GridSystem

if TYPE_CHECKING:
    from domain.plane import Plane

logger = CadLogger.get(__name__)

# Shader klasörü — modül seviyesinde bir kez
_here = Path(__file__).resolve().parent
SHADER_DIR = _here.parent / "render" / "shaders"


class Engine:
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
        self.working_plane_provider: Callable[[], Plane | None] | None = None

        self.active_smart_plane_mode = False

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
                       "2d_overlay", "preview", "grid", "axes"]
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
        self.axes_s = self.shaders.get("axes")

        # self.renderer.set_axes_shader(self.axes_s)

    
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


        
        # self.smart_analyzer = SmartPlaneAnalyzer(
        #         scene_controller=None,               # şimdilik None
        #         scene_provider=lambda: self.scene, # ama erişim anında engine.scene
        #     )
        
        self.renderer = SceneRenderer(
            pick_s=self.pick_s,
            standard_s=self.standard_s,
            node_s=self.node_s,
            simple_s=self.simple_s,
            overlay_s=self.overlay_s,
            axes_s=self.axes_s,
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
        c1, s1 = self.renderer.get_bounds()
        c2, s2 = self.grid.get_bounds()
        c, s = (c1, s1) if s1 >= s2 else (c2, s2)
        
        self.cam.update_bounds(c, s)
        self.cam.focus_on_model()

    def set_working_plane_provider(
        self, provider: Callable[[], Plane | None] | None
    ) -> None:
        self.working_plane_provider = provider

    @property
    def active_working_plane(self) -> Plane | None:
        if self.working_plane_provider is None:
            return None
        return self.working_plane_provider()

    def focus_plane(self, plane: Plane, padding: float = 1.15) -> bool:
        if self.cam is None:
            return False
        if not np.isfinite(padding) or padding <= 0.0:
            raise ValueError("Plane fit padding pozitif ve sonlu olmalı")

        center, size = (
            self.renderer.get_bounds()
            if self.renderer is not None
            else (self.cam.model_center, self.cam.model_size)
        )
        center = np.asarray(center, dtype=float)
        half_extents = np.full(3, max(float(size), 1.0) * 0.5)
        local_center = plane.world_to_local(center)
        u_extent = float(np.dot(np.abs(plane.u), half_extents))
        v_extent = float(np.dot(np.abs(plane.v), half_extents))
        u_min, u_max, v_min, v_max = plane.boundary
        u_min = local_center[0] - u_extent if u_min is None else float(u_min)
        u_max = local_center[0] + u_extent if u_max is None else float(u_max)
        v_min = local_center[1] - v_extent if v_min is None else float(v_min)
        v_max = local_center[1] + v_extent if v_max is None else float(v_max)

        focus = plane.to_3d(((u_min + u_max) * 0.5, (v_min + v_max) * 0.5))
        width = max(u_max - u_min, 1.0)
        height = max(v_max - v_min, 1.0)
        aspect = max(float(self.cam.aspect_ratio), 1e-6)
        half_height = max(height * 0.5, width / (2.0 * aspect))
        fit_distance = max(2.0 * half_height * padding, 1.0)

        self.cam.look_at_plane(
            focus, plane.u, plane.v, plane.normal, fit_radius=fit_distance
        )
        return True

    
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
            #pass(f"[PICK] check_pick → {pick_id}")
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
        #pass(f"[HOOK] hover_id={self.hover_id} ctrl={ctrl}")
        if self.hover_id > 0 and self.renderer and self.renderer.pick_pass:
            element = self.renderer.get_element_from_id(self.hover_id)
            #pass(f"[HOOK] element={type(element).__name__ if element else None}")
            if element:
                self.sel_mgr.select(element, additive=ctrl)
        # else:
            #pass(f"[HOOK] hover_id=0 → işlem yok")

    def screen_ray(self, x, y):
        if not self.cam:
            return None

        v = self.cam.get_view_matrix()
        p = self.cam.get_projection_matrix()
        nx = 2 * x / self.w - 1
        ny = 1 - 2 * y / self.h
        inv = glm.inverse(p * v)

        near = inv * glm.vec4(nx, ny, -1, 1)
        far = inv * glm.vec4(nx, ny, 1, 1)
        if abs(near.w) < 1e-12 or abs(far.w) < 1e-12:
            return None
        near = glm.vec3(near) / near.w
        far = glm.vec3(far) / far.w
        direction = far - near
        if glm.length(direction) < 1e-12:
            return None
        direction = glm.normalize(direction)
        return np.asarray(near, dtype=float), np.asarray(direction, dtype=float)

    def screen_to_working_plane(
        self,
        x: float,
        y: float,
        plane: Plane | None = None,
        *,
        grid_coordinates: tuple[Sequence[float], Sequence[float]] | None = None,
        orthogonal_origin: tuple[float, float] | None = None,
    ) -> tuple[glm.vec3, glm.vec2] | None:
        plane = self.active_working_plane if plane is None else plane
        if plane is None:
            return None
        if self.input is not None:
            if grid_coordinates is None:
                grid_coordinates = self.input.working_plane_grid_coordinates
            if orthogonal_origin is None:
                orthogonal_origin = self.input.working_plane_orthogonal_origin
        ray = self.screen_ray(x, y)
        if ray is None:
            return None
        origin, direction = ray
        point = plane.intersect_ray(origin, direction)
        if point is None:
            return None
        coords = plane.world_to_local(point)
        uv = self.constrain_working_plane_coordinates(
            (float(coords[0]), float(coords[1])),
            grid_coordinates=grid_coordinates,
            orthogonal_origin=orthogonal_origin,
        )
        if not plane.bounds_contains_uv(*uv):
            return None
        point = plane.to_3d(uv)
        return (
            glm.vec3(*point),
            glm.vec2(*uv),
        )

    @staticmethod
    def constrain_working_plane_coordinates(
        coords: tuple[float, float],
        *,
        grid_coordinates: tuple[Sequence[float], Sequence[float]] | None = None,
        orthogonal_origin: tuple[float, float] | None = None,
    ) -> tuple[float, float]:
        """Snap local coordinates to grid lines, then constrain to an orthogonal axis."""
        u, v = map(float, coords)
        if not np.isfinite((u, v)).all():
            raise ValueError("Plane koordinatları sonlu olmalı")
        if grid_coordinates is not None:
            if len(grid_coordinates) != 2:
                raise ValueError("Grid koordinatları u ve v çizgileri içermeli")
            snapped = []
            for value, lines in zip((u, v), grid_coordinates):
                values = np.asarray(lines, dtype=float)
                if (
                    values.ndim != 1
                    or values.size == 0
                    or not np.isfinite(values).all()
                ):
                    raise ValueError("Grid koordinatları boş veya geçersiz")
                snapped.append(float(values[np.argmin(np.abs(values - value))]))
            u, v = snapped
        if orthogonal_origin is not None:
            anchor = np.asarray(orthogonal_origin, dtype=float)
            if anchor.shape != (2,) or not np.isfinite(anchor).all():
                raise ValueError("Ortho başlangıcı iki sonlu koordinat içermeli")
            delta_u, delta_v = u - anchor[0], v - anchor[1]
            if abs(delta_u) >= abs(delta_v):
                v = float(anchor[1])
            else:
                u = float(anchor[0])
        return u, v

    def screen_to_world(self, x: float, y: float) -> glm.vec3 | None:
        plane = self.active_working_plane
        if plane is not None:
            hit = self.screen_to_working_plane(x, y, plane)
            return hit[0] if hit is not None else None

        ray = self.screen_ray(x, y)
        if ray is None:
            return None
        origin, direction = ray
        if abs(direction[2]) <= 1e-12:
            return None
        distance = -origin[2] / direction[2]
        if distance < 0.0:
            return None
        return glm.vec3(*(origin + distance * direction))

    def update_world_pos(self, x: float, y: float) -> None:
        if not self.cam or not self.input:
            return

        self.input.mouse_plane_valid = False
        plane = self.active_working_plane
        has_hovered_node = (
            self.hover_id > 0 and self.hover_element_type == "node"
        )
        if has_hovered_node and plane is None:
            return

        hit = (
            self.screen_to_working_plane(x, y, plane)
            if plane is not None
            else None
        )
        if hit is not None:
            plane_world, plane_coords = hit
            self.input.mouse_plane_pos = plane_world
            self.input.mouse_plane_coords = plane_coords
            self.input.mouse_plane_valid = True
            if not has_hovered_node:
                self.input.mouse_world_pos = plane_world
                self.input.mouse_world_valid = True
            return

        if has_hovered_node:
            return
        world = self.screen_to_world(x, y)
        if world is not None:
            self.input.mouse_world_pos = world
            self.input.mouse_world_valid = True
            return
        self.input.mouse_world_valid = False

    def clear_hover(self):
        self.hover_id = 0
        self.hover_element_type = None
        self.input.mouse_world_valid = False
        self.input.mouse_plane_valid = False

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
        element_type = getattr(element, 'element_type', None)
        if element_type:
            return str(element_type).lower()
        class_name = element.__class__.__name__.lower()
        for key in ('node', 'frame', 'area', 'link', 'polygon'):
            if key in class_name:
                return key
        return None