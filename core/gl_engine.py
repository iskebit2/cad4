# core/gl_engine.py
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, TYPE_CHECKING

import numpy as np
from OpenGL.GL import *
from pyglm import glm

from core.camera import Camera
from plane.plane_source_dialog import PlaneSourceDialog
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
from render.interactionrenderer import InteractionRenderer
from render.mathmodelrenderer import MathModelRenderer
from render.scenerenderer import SceneRenderer
from render.shaderprogram import ShaderProgram
from render.snapsquare import SnapSquareRenderer
from plane.plane_creation_tool import PlaneCreationTool, PlaneFromElementInputHandler, PlaneFromElementState
from core.input_manager import InputManager
from core.camera_controller import CameraController

from logging_config import CadLogger
logger = CadLogger.get(__name__)

if TYPE_CHECKING:
    from plane.plane import Plane


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

        self.viewport_manager = None
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
        self.last_hover_viewport = None
        self.viewport_pointer = None
        self.last_hover_time = 0.0
        self.hover_throttle = 0.05
        self.pending_pick_check = False
        self._force_id_pass_once = False

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

        self._plane_from_element = PlaneFromElementState()
        self._plane_from_element.engine = self

    @property
    def plane_from_element_dialog(self):
        return getattr(self, "_plane_source_dialog", None)

    @property
    def math_model_renderer(self):
        return getattr(self.renderer, "math_model_renderer", None) if self.renderer else None

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

        self.presentation_renderer = self.renderer.presentation_renderer
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
        self.input.register(PlaneFromElementInputHandler(self._plane_from_element))

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

        if not self.presentation_renderer:
            return

        t = time.perf_counter()
        geometry = GeometryProcessor.process(scene, None, math_model)
        logger.debug("[update_geo] GeometryProcessor: %.1f ms", (time.perf_counter() - t) * 1000)

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

    # ------------------------------------------------------------------
    def render(self, cam, target_fbo: int = 0, draw_interaction: bool = True,
           target_size: tuple[int, int] | None = None,
           viewport_name: str | None = None, viewport_plane=None, visible_ids=None):
        if not (cam and self.renderer and self.mrt):
            return

        self.mrt.bind()
        self.mrt.clear()

        if target_size is not None:
            tw, th = target_size
            scale = min(1.0, self.mrt.w / tw, self.mrt.h / th)
            render_w = max(1, int(tw * scale))
            render_h = max(1, int(th * scale))
        else:
            tw = th = None
            render_w, render_h = self.mrt.w, self.mrt.h
        glViewport(0, 0, render_w, render_h)
        force_id = target_size is not None or self._force_id_pass_once
        self._force_id_pass_once = False

        glDrawBuffer(GL_COLOR_ATTACHMENT0)
        self.renderer.render(
            cam, target_fbo, force_id_pass=force_id,
            viewport_name=viewport_name, plane=viewport_plane,
            visible_ids=visible_ids,
        )

        self.mrt.blit_to(
            target_fbo,
            target_w=tw,
            target_h=th,
            copy_id=target_size is not None,
            source_w=render_w,
            source_h=render_h,
        )

        if draw_interaction and self.show.get("interaction", True) and self.interaction_renderer:
            glViewport(0, 0, tw or self.w, th or self.h)
            glDrawBuffer(GL_COLOR_ATTACHMENT0)
            viewport_pointer = self.viewport_pointer
            pointer = (
                viewport_pointer[1:]
                if viewport_name is not None
                and viewport_pointer is not None
                and viewport_pointer[0] == viewport_name
                else None
            )
            interaction_w, interaction_h = target_size or (self.w, self.h)
            self.interaction_renderer.render(
                self, interaction_w, interaction_h,
                camera=cam, viewport_name=viewport_name,
                mouse_pos=pointer,
            )

        if target_size is not None:
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
            glViewport(0, 0, self.w, self.h)

    def render_viewport(self, vp):
        if vp is None or vp.camera is None:
            return
        vp.camera.set_aspect(vp.width, vp.height)
        # ★ Viewport 2D modundaysa plane_2d projection kullan
        is_2d = getattr(vp, "is_2d", False)
        prev_projection = self.renderer.projection
        if is_2d:
            self.renderer.projection = "plane_2d"
            if self.renderer.math_model_renderer:
                self.renderer.math_model_renderer.projection = "plane_2d"
        try:
            self.render(
                vp.camera, target_fbo=vp.fbo.fbo,
                target_size=(vp.width, vp.height),
                viewport_name=vp.name,
                viewport_plane=getattr(vp, "plane", None),
                visible_ids=getattr(vp, "visible_ids", None),
            )
        finally:
            # ★ Global state'i geri yükle
            self.renderer.projection = prev_projection
            if self.renderer.math_model_renderer:
                self.renderer.math_model_renderer.projection = prev_projection        
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
        if self.renderer:
            self.renderer.update_geo(
                self.math_model, self.scene,
                polygons=[], lines=[], frames=[], nodes=[], areas=[], links=[],
            )

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

    def start_viewport_hover_pick(self, viewport, x, y):
        self.set_viewport_pointer(viewport, x, y)
        pick_pass = self.renderer.pick_pass if self.renderer else None
        if pick_pass is None:
            return
        now = time.time()
        position = (viewport.name, int(x), int(y))
        if (now - self.last_hover_time) < self.hover_throttle:
            return
        if position == (self.last_hover_viewport, self.last_hover_x, self.last_hover_y):
            return
        if pick_pass.pick_async(
            int(x), int(y),
            source_fbo=viewport.fbo.fbo,
            viewport_size=(viewport.width, viewport.height),
        ):
            self.last_hover_viewport, self.last_hover_x, self.last_hover_y = position
            self.last_hover_time = now
            self.pending_pick_check = True

    def set_viewport_pointer(self, viewport, x, y):
        self.viewport_pointer = (viewport.name, int(x), int(y))

    def check_pick_result(self):
        if not self.pending_pick_check:
            return False
        try:
            pick_id, px, py = self.renderer.check_pick()
        except Exception:
            logger.exception("Pick kontrolü")
            self.pending_pick_check = False
            return False
        if pick_id is not None:
            self.pending_pick_check = False
            # ★ İlk hover'da 0 dönerse bir kez daha dene
            if pick_id == 0 and not getattr(self, "_hover_retry", False):
                self._hover_retry = True
                self.last_hover_x = -1
                self.last_hover_y = -1
                return False
            self._hover_retry = False
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
        # logger.debug(f"[HOVER] pick_id={pick_id}")
        if pick_id == self.hover_id:
            return
        self.hover_id = pick_id
        if pick_id <= 0:
            self.clear_hover()
            if self.on_hover_changed_callback:
                self.on_hover_changed_callback(None)
            pfe = getattr(self, "_plane_from_element", None)
            if pfe is not None and pfe.active:
                pfe.set_hover(None)
            return
        element = self._find_element(pick_id)
        pfe = getattr(self, "_plane_from_element", None)
        if pfe is not None and pfe.active:
            pfe.set_hover(element)
            
        if element is None:
            self.clear_hover()
            return
        if self.on_hover_changed_callback:
            self.on_hover_changed_callback(element)

    def _find_element(self, pick_id):
        el = self.renderer.get_element_from_id(pick_id)
        if el is not None:
            return el
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

    def start_plane_from_element(self):
        self._plane_from_element.start()

    def cancel_plane_from_element(self):
        self._plane_from_element.cancel()

    def toggle_plane_from_element_axis(self):
        self._plane_from_element.frame_axis_12 = not self._plane_from_element.frame_axis_12
        
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