# core/gl_engine.py
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, TYPE_CHECKING

import numpy as np
from OpenGL.GL import *
from pyglm import glm

from core.camera import Camera
from tools.draw_manager import DrawManager
from core.edit.edit_controller import EditController
from core.input_manager import InputManager
from core.marquee_selector import MarqueeSelector
from core.mrt import MRTFramebuffer
from core.selection_manager import SelectionManager
from core.selection_policy import SelectionPolicy
from domain.scene import Scene
from domain.math_model import MathModel
from geometry.geometry_processor import GeometryProcessor
from logging_config import CadLogger
from render.interactionrenderer import InteractionRenderer
from render.mathmodelrenderer import MathModelRenderer
from render.scenerenderer import SceneRenderer
from render.shaderprogram import ShaderProgram
from render.snapsquare import SnapSquareRenderer
from plane.plane_creation_tool import PlaneCreationTool
from core.input_manager import InputManager
from core.camera_controller import CameraController


if TYPE_CHECKING:
    from plane.plane import Plane

logger = CadLogger.get(__name__)

SHADER_DIR = Path(__file__).resolve().parent.parent / "render" / "shaders"


class Engine:

    def __init__(self, w: int, h: int):
        self.w = max(1, w)
        self.h = max(1, h)

        self.shaders: dict = {}
        self.pick_s = None
        self.standard_s = None
        self.node_s = None
        self.simple_s = None
        self.overlay_s = None
        self.preview_s = None
        self.grid_s = None
        self.axes_s = None

        self.plane_draw_mgr = None
        self.draw_mgr = None

        self.cam = None
        self.input = None
        self.scene = None
        self.math_model = None
        self.project = None
        self.renderer = None
        self.presentation_renderer = None
        self.interaction_renderer = None
        self.pick_pass = None
        self.mrt = None
        self.sel_mgr = None
        self.marquee = None
        self.draw_mgr = None
        self.snap = None
        self.edit = None
        self.sel_policy = None
        self.grid = None
        self.active_wind_vector = None
        
        self.hover_id = 0
        self.hover_enabled = True
        self.last_hover_x = -1
        self.last_hover_y = -1
        self.last_hover_time = 0.0
        self.hover_throttle = 0.05
        self.pending_pick_check = False

        self.show = {
            "scene": True,
            "grid": True,
            "polygon": True,
            "lines": True,
            "zones": True,
            "loads": True,
            "labels": True,
            "global_axis": True,
            "local_axes": False,
            "interaction": True,
        }

        self.working_plane_provider: Callable[[], Plane | None] | None = None
        self.on_hover_changed_callback = None
        
    # ------------------------------------------------------------------
    def init_gl(self):
        logger.debug("GL_VERSION: %s", glGetString(GL_VERSION))
        self._init_shaders()
        self._init_camera()
        self.mrt = MRTFramebuffer(self.w, self.h)
        self._init_components()

    def _init_shaders(self):
        for name in ("pick", "standard", "node", "simple",
                     "2d_overlay", "preview", "grid", "axes"):
            try:
                self.shaders[name] = ShaderProgram(
                    name,
                    str(SHADER_DIR / f"{name}.vert"),
                    str(SHADER_DIR / f"{name}.frag"),
                )
            except Exception:
                logger.exception("Shader yükleme hatası: %s", name)
                self.shaders[name] = None
        self.pick_s = self.shaders["pick"]
        self.standard_s = self.shaders["standard"]
        self.node_s = self.shaders["node"]
        self.simple_s = self.shaders["simple"]
        self.overlay_s = self.shaders["2d_overlay"]
        self.preview_s = self.shaders["preview"]
        self.grid_s = self.shaders["grid"]
        self.axes_s = self.shaders["axes"]

    def _init_camera(self):
        self.cam = Camera()
        self.cam.set_aspect(self.w, self.h)
        self.cam.pitch = 30.0
        self.cam.yaw = -45.0
        self.cam.distance = 50.0
        self.cam._update_position()

    def _init_components(self):
        self.scene = Scene()
        self.math_model = MathModel()
        self.input = InputManager()
        self._app = None
        self.sel_policy = SelectionPolicy(self.input)
        self.snap = SnapSquareRenderer()
        

        math_model_renderer = MathModelRenderer(
            pick_s=self.pick_s, standard_s=self.standard_s,
            node_s=self.node_s, simple_s=self.simple_s,
            overlay_s=self.overlay_s, axes_s=self.axes_s,
            w=self.w, h=self.h,
        )
        self.renderer = SceneRenderer(
            standard_shader=self.standard_s,
            axes_shader=self.axes_s,
            overlay_shader=self.overlay_s,
            simple_shader=self.simple_s,
            grid_shader=self.grid_s,
            math_model_renderer=math_model_renderer,
        )
        self.renderer.set_engine(self)
        self.pick_pass = self.renderer.pick_pass
        self.pick_pass.set_main_fbo(self.mrt.fbo)

        self.renderer.set_cam(self.cam)
        self.renderer.set_snap(self.snap)

        self.presentation_renderer = self.renderer
        self.grid = self.presentation_renderer.grid

        self.interaction_renderer = InteractionRenderer(overlay_shader=self.overlay_s)

        self.sel_mgr = SelectionManager(self.renderer)
        self.marquee = MarqueeSelector(self, self.sel_mgr, self.sel_policy)
        self.edit = EditController(self)

        self.draw_mgr = DrawManager(self)
        self.plane_draw_mgr = PlaneCreationTool(self)

    def set_app(self, app) -> None:
        self._app = app
        controller = CameraController(self, app)
        self.input.set_fallback(controller)
        self.input.register(self.plane_draw_mgr)
        self.input.register(self.draw_mgr)
        self.input.set_global_escape(self._on_global_escape)

        from imgui_bundle import imgui
        self.input.set_capture_callbacks(
            mouse_fn=lambda: bool(imgui.get_io().want_capture_mouse),
            keyboard_fn=lambda: bool(imgui.get_io().want_capture_keyboard),
        )

    def set_project(self, project) -> None:
        self.project = project
        if project is None:
            return
        self.scene = project.scene
        self.math_model = project.math_model

    def _combined_bounds(self):
        from domain.bounds import Bounds3D

        items = [
            b for b in (
                self.scene.bounds if self.scene else None,
                self.math_model.bounds if self.math_model else None,
            ) if b is not None
        ]
        if not items:
            return None
        minimum = np.min([item.min for item in items], axis=0)
        maximum = np.max([item.max for item in items], axis=0)
        return Bounds3D(min=minimum, max=maximum)
    # ------------------------------------------------------------------
    def resize(self, w: int, h: int):
        self.w = max(1, w)
        self.h = max(1, h)
        if self.cam:
            self.cam.set_aspect(self.w, self.h)
        if self.renderer:
            self.renderer.resize(self.w, self.h)
        if self.mrt:
            self.mrt.resize(self.w, self.h)
        if self.pick_pass:
            self.pick_pass.set_viewport(self.w, self.h)
            self.pick_pass.set_main_fbo(self.mrt.fbo)
        
    # ------------------------------------------------------------------
    def update_geo(self, project=None):
        t_start = time.perf_counter()
        plane_name= "full"
        if project is not None:
            self.project = project
        else:
            project = self.project
        scene = project.scene if project else self.scene
        math_model = project.math_model if project else self.math_model
        if scene is None or math_model is None:
            return
        self.scene = scene
        self.math_model = math_model

        plane = project.active_plane if project else None

        # # Assoc
        # if self.math_model and project is not None:
        #     t = time.perf_counter()
        #     self.math_model.refresh_plane_associations(
        #         project.all_planes(), scene=self.scene,
        #     )
        #     logger.debug("[update_geo] assoc: %.1f ms", (time.perf_counter() - t) * 1000)

        if not self.presentation_renderer:
            return

        t = time.perf_counter()
        geometry = GeometryProcessor.process(scene, plane, math_model)
        logger.debug("[update_geo] GeometryProcessor: %.1f ms", (time.perf_counter() - t) * 1000)

        if plane is not None:
            plane_name = plane.name

        t = time.perf_counter()
        self.renderer.update_geo(
            math_model,
            scene,
            polygons=geometry.polygons,
            lines=geometry.lines,
            grid_axes=geometry.grid_axes,
            frames=geometry.frames,
            nodes=geometry.nodes,
            areas=geometry.areas,
            links=geometry.links,
        )

        logger.debug("[update_geo] renderer.update_geo: %.1f ms", (time.perf_counter() - t) * 1000)

        t = time.perf_counter()
        cam_scale = (
            self.renderer._compute_cam_scale()
            if hasattr(self.renderer, "_compute_cam_scale") else 1.0
        )
        scene_size = getattr(self.renderer, "size", 1.0)
        self.presentation_renderer.update_loads(
            math_model, camera_scale=cam_scale, scene_size=scene_size,
        )

        logger.debug("Update geo: %s", plane_name)

        logger.debug("[update_geo] loads: %.1f ms", (time.perf_counter() - t) * 1000)

        logger.debug("[update_geo] TOTAL: %.1f ms", (time.perf_counter() - t_start) * 1000)

    def _register_picks(self, polygons, lines):
        if not self.pick_pass:
            return
        pr = self.presentation_renderer
        for p in polygons:
            p.pick_id = p.unique_id
            self.pick_pass.register(p.pick_id, p, pr.polygon)
        for ln in lines:
            ln.pick_id = ln.unique_id
            self.pick_pass.register(ln.pick_id, ln, pr.lines)

    # ------------------------------------------------------------------
    def render(self, cam, target_fbo: int = 0):
        if not (cam and self.renderer and self.mrt):
            return

        self.mrt.bind()
        self.mrt.clear()

        # 1. Grid + görsel öğeler (polygon, line, zones, loads, labels)
        glDrawBuffer(GL_COLOR_ATTACHMENT0)
        if self.show.get("presentation_any", True) and self.presentation_renderer and self.scene:
            self._render_scene_visuals(cam)

        # 2. Math model (frame, area, link, node) — EN ÖNDE
        if self.show.get("scene", True):
            self.renderer.render(cam, target_fbo)

        # 3. Sunum pick
        if self.pick_s and self.presentation_renderer:
            self._render_scene_pick(cam)

        self.mrt.blit_to(target_fbo)

        if self.show.get("interaction", True) and self.interaction_renderer:
            self.interaction_renderer.render(self, self.w, self.h)

    def _render_scene_visuals(self, cam):
        self.renderer.render_scene_visuals(
            cam, self.renderer.model_mat, self.scene, self.math_model,
            self.w, self.h, self.show, self.active_wind_vector,
        )

    def _render_scene_pick(self, cam):
        self.mrt.bind()
        glDrawBuffer(GL_COLOR_ATTACHMENT1)
        self.presentation_renderer.render_presentation_pick(
            cam, self.renderer.model_mat, self.pick_s,
        )
        glDrawBuffer(GL_COLOR_ATTACHMENT0)

    # ------------------------------------------------------------------
    def set_scene(self, project):
        if self.interaction_renderer:
            self.interaction_renderer.preview_plane = None
        self.project = project
        self.scene = project.scene
        self.math_model = project.math_model
        self.update_geo(project)
        self.fit_view()

    def clear_scene(self):
        self.project = None
        self.scene = Scene()
        self.math_model = MathModel()
        self.update_geo()
        for r in (self.renderer.frame_r, self.renderer.node_r,
                  self.renderer.area_r, self.renderer.link_r):
            r.elements = []
        if self.presentation_renderer:
            self.presentation_renderer.polygon.elements = []

    def fit_view(self):
        bounds = self._combined_bounds()
        if bounds is not None:
            self.cam.update_bounds(bounds.center, bounds.size)
        else:
            self.cam.update_bounds((0.0, 0.0, 0.0), 10000.0)
        self.cam.focus_on_model()

    def focus_plane(self, plane) -> None:
        if plane is None or self.cam is None:
            return
        uc = 0.5 * ((plane.u_min or 0.0) + (plane.u_max or 0.0))
        vc = 0.5 * ((plane.v_min or 0.0) + (plane.v_max or 0.0))
        center = plane.to_3d((uc, vc))
        half_u = 0.5 * abs((plane.u_max or 0.0) - (plane.u_min or 0.0))
        half_v = 0.5 * abs((plane.v_max or 0.0) - (plane.v_min or 0.0))
        fit_radius = max(half_u, half_v) * 1.4
        if fit_radius < 1e-6:
            bounds = self._combined_bounds()
            size = bounds.size if bounds else 1000.0
            fit_radius = max(float(size), 1000.0)
        self.cam.look_at_plane(
            origin=center,
            u=plane.u,
            v=plane.v,
            n=plane.normal,
            fit_radius=fit_radius,
        )
        
    def zoom_extents(self):
        if self.scene:
            self.scene.refresh_bounds()
        if self.math_model:
            self.math_model.refresh_bounds()
        self.fit_view()

    # ------------------------------------------------------------------
    def set_working_plane_provider(self, provider):
        self.working_plane_provider = provider

    @property
    def active_working_plane(self):
        return self.working_plane_provider() if self.working_plane_provider else None

    # ------------------------------------------------------------------
    def start_hover_pick(self, x, y):
        if not (self.renderer and self.renderer.pick_pass):
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
        except Exception:
            logger.exception("Pick kontrolü")
            self.pending_pick_check = False
            return False
        if pick_id is not None:
            self.pending_pick_check = False
            self._update_hover(pick_id)
            return True
        if not self.renderer.pick_pass.pending_pick:
            self.pending_pick_check = False
        return False

    def handle_pick_from_hover(self, ctrl: bool = False):
        if not self.sel_mgr:
            return
        if self.hover_id > 0:
            element = self.sel_mgr.find_element_by_id(self.hover_id)
            if element:
                self.sel_mgr.select(element, additive=ctrl)
                return
        if not ctrl:
            self.sel_mgr.clear()

    def _update_hover(self, pick_id):
        if pick_id == self.hover_id:
            return
        self.hover_id = pick_id
        if pick_id <= 0:
            self.clear_hover()
            if self.on_hover_changed_callback:
                self.on_hover_changed_callback(None)
            return
        element = self._find_element(pick_id)
        if element is None:
            self.clear_hover()
            return
        if self.on_hover_changed_callback:
            self.on_hover_changed_callback(element)

    def _find_element(self, pick_id):
        el = self.renderer.get_element_from_id(pick_id)
        if el is not None:
            return el
        if self.scene:
            if pick_id in self.scene.polygons:
                return self.scene.polygons[pick_id]
            if pick_id in self.scene.lines:
                return self.scene.lines[pick_id]
        return None

    def clear_hover(self):
        self.hover_id = 0
        if self.input:
            self.input.mouse_world_valid = False

    # ------------------------------------------------------------------
    def screen_ray(self, x: float, y: float):
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
        return (np.asarray(near, dtype=float),
                np.asarray(glm.normalize(direction), dtype=float))

    def screen_to_world(self, x: float, y: float):
        ray = self.screen_ray(x, y)
        if ray is None:
            return None
        origin, direction = ray

        plane = self.active_working_plane
        if plane is not None:
            n = np.asarray(plane.normal, dtype=float)
            o = np.asarray(plane.origin, dtype=float)
            denom = float(np.dot(n, direction))
            if abs(denom) < 1e-12:
                return None
            t = float(np.dot(n, o - np.asarray(origin))) / denom
            if t < 0:
                return None
            return glm.vec3(*(origin + t * direction))

        if abs(direction[2]) <= 1e-12:
            return None
        t = -origin[2] / direction[2]
        if t < 0:
            return None
        return glm.vec3(*(origin + t * direction))

    def update_world_pos(self, x: float, y: float):
        if not (self.cam and self.input):
            return
        world = self.screen_to_world(x, y)
        if world is not None:
            self.input.mouse_world_pos = world
            self.input.mouse_world_valid = True
            return
        self.input.mouse_world_valid = False

    # ------------------------------------------------------------------
    def render_pick_pass(self, cam, target_fbo):
        if not (cam and self.renderer):
            return
        if hasattr(self.renderer, "render_pick"):
            self.renderer.render_pick(cam, target_fbo)
        if self.presentation_renderer and self.pick_s:
            model = getattr(self.renderer, "model_mat", glm.mat4(1.0))
            self.presentation_renderer.render_presentation_pick(
                cam, model, self.pick_s,
            )

    def default_xy_plane(self):
        if self.project is None:
            return None
        for p in self.project.grid_planes():
            if p.name == "XY_Z0":
                return p
        for p in self.project.grid_planes():
            if p.name.startswith("XY_Z"):
                return p
        return None

    def enter_plane_2d(self, plane):
        if plane is None or self.cam is None:
            return
        self.cam.save_view()
        uc = 0.5 * ((plane.u_min or 0.0) + (plane.u_max or 0.0))
        vc = 0.5 * ((plane.v_min or 0.0) + (plane.v_max or 0.0))
        center = plane.to_3d((uc, vc))
        half_u = 0.5 * abs((plane.u_max or 0.0) - (plane.u_min or 0.0))
        half_v = 0.5 * abs((plane.v_max or 0.0) - (plane.v_min or 0.0))
        fit_radius = max(half_u, half_v) * 1.4
        if fit_radius < 1e-6:
            b = self._combined_bounds()
            fit_radius = b.size if b else 1000.0
        self.cam.look_at_plane(
            origin=center,
            u=plane.u, v=plane.v, n=plane.normal,
            fit_radius=fit_radius,
        )
        self.cam.set_section_filter(
            normal=plane.normal, origin=plane.origin,
            min_s=-plane.depth_minus, max_s=+plane.depth_plus,
        )
        self.renderer.projection = "plane_2d"
        if self.renderer.math_model_renderer:
            self.renderer.math_model_renderer.projection = "plane_2d"

    def exit_plane_2d(self):
        self.cam.restore_view()
        self.cam.clear_section_filter()
        self.renderer.projection = "3d"
        if self.renderer.math_model_renderer:
            self.renderer.math_model_renderer.projection = "3d"
            
    def _on_global_escape(self) -> None:
        changed = False

        if self.plane_draw_mgr and self.plane_draw_mgr.is_active:
            self.plane_draw_mgr.cancel()
            changed = True
        if self.draw_mgr and self.draw_mgr.is_active:
            self.draw_mgr.cancel()
            changed = True
        if self.marquee and self.marquee.is_active:
            self.marquee.cancel_selection()
            changed = True
        if self.interaction_renderer and self.interaction_renderer.preview_plane is not None:
            self.interaction_renderer.preview_plane = None

        if self.sel_mgr:
            self.sel_mgr.clear()

        self.clear_hover()

        if self._app is not None:
            pm = self._app.panels.get("plane_manager", {}).get("instance")
            if pm is not None and (pm._selected_name is not None or pm._preview_plane is not None):
                pm._selected_name = None
                pm._preview_plane = None
                pm._form_open = False
                pm._editing_plane = None
                # pm._clear_preview()
                pm._preview_off()

        # if self.project is not None and self.project.active_plane is not None:
        #     self.project.deactivate_plane()
        #     self.cam.clear_section_filter()
        #     changed = True

        # if changed and self.project is not None:
        #     self.update_geo(self.project)