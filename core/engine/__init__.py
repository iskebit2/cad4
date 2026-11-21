# core/engine/__init__.py
from __future__ import annotations

from typing import TYPE_CHECKING

from core.input_manager import InputManager
from core.engine.gl_context import GLContext
from core.engine.renderer_pipeline import RendererPipeline
from core.engine.camera_rig import CameraRig
from core.engine.hover_system import HoverSystem
from core.engine.plane_mode import PlaneMode
from core.engine.tools_registry import ToolsRegistry
from render.snapsquare import SnapSquareRenderer
from plane.plane_creation_tool import PlaneFromElementState
from logging_config import CadLogger

if TYPE_CHECKING:
    from domain.project import Project
    from viewport.viewport import Viewport
    from domain.bounds import Bounds3D

logger = CadLogger.get(__name__)


class Engine:
    """Render pipeline orkestratörü. App bilmez, UI bilmez."""

    def __init__(self, width: int, height: int, command_queue) -> None:
        self.w = max(1, int(width))
        self.h = max(1, int(height))
        self.command_queue = command_queue
        self.project: Project | None = None

        self.gl = GLContext(self.w, self.h)
        self.camera_rig = CameraRig(self.w, self.h)
        self.input = InputManager()
        self.camera_ctrl = None
        self.pipeline: RendererPipeline | None = None
        self.plane_mode: PlaneMode | None = None
        self.hover: HoverSystem | None = None
        self.tools: ToolsRegistry | None = None

        self.show = {
            "scene": True, "grid": True, "polygon": True, "lines": True,
            "interaction": True, "presentation_any": True,
            "loads": True, "zones": False,
            "labels": True, "grid_labels": True, "selected_labels": True,
            "global_axis": True, "local_axes": False,
        }

        self.hover_visual_enabled = True
        self.active_wind_vector = None
        self._plane_from_element = PlaneFromElementState()
        self._plane_from_element.engine = self
        self.viewport_manager = None

        
    # ------------------------------------------------------------------
    def init_gl(self) -> None:
        self.gl.init()
        self.pipeline = RendererPipeline(self.w, self.h, self.gl.shaders)
        self.tools = ToolsRegistry(self)
        self.tools.build()
        self.pipeline.renderer.set_engine(self)
        self.plane_mode = PlaneMode(self.camera_rig, self.pipeline, self.command_queue)

        self.hover = HoverSystem(
            self.pipeline.pick_pass,
            self.command_queue,
            resolve_element=self._find_element,
        )
        from core.camera_controller import CameraController
        self.camera_ctrl = CameraController(self)
        self.input.set_fallback(self.camera_ctrl)

    def resize(self, w: int, h: int) -> None:
        self.w = max(1, int(w))
        self.h = max(1, int(h))
        self.camera_rig.resize(self.w, self.h)
        if self.pipeline is not None:
            self.pipeline.resize(self.w, self.h)

    def update_geo(self, project: "Project | None" = None) -> None:
        if self.pipeline is not None:
            if project is not None:
                self.project = project
            self.pipeline.update_geo(project)

    def render_viewport(self, vp: "Viewport") -> None:
        if self.pipeline is None:
            return

        is_2d = getattr(vp, "is_2d", False)
        prev_proj = self.pipeline.renderer.projection
        if is_2d:
            self.pipeline.renderer.projection = "plane_2d"
            if self.pipeline.math_model_renderer:
                self.pipeline.math_model_renderer.projection = "plane_2d"

        pointer = None
        if self.hover is not None and self.hover.pointer is not None:
            if self.hover.pointer[0] == vp.name:
                pointer = self.hover.pointer[1:]
        if pointer is None and self.input is not None:
            pointer = (
                int(self.input.state.mouse_pos.x),
                int(self.input.state.mouse_pos.y),
            )

        self.pipeline.render(
            vp,
            self.camera_rig,
            engine=self,
            pointer=pointer,
            draw_interaction=bool(self.show.get("interaction", True)),
        )

        self.pipeline.renderer.projection = prev_proj
        if self.pipeline.math_model_renderer:
            self.pipeline.math_model_renderer.projection = prev_proj

    def tick(self) -> None:
        if self.hover is not None and self.hover._pending:
            self.hover.check_pick_result()
        if self.tools is not None:
            self.tools.tick()

    # ------------------------------------------------------------------
    # Viewport 2D geçişi
    def enter_plane_2d(self, plane) -> None:
        if self.plane_mode is not None:
            self.plane_mode.enter_2d(plane)

    def exit_plane_2d(self) -> None:
        if self.plane_mode is not None:
            self.plane_mode.exit_2d()

    # ------------------------------------------------------------------
    # Fit / zoom
    def fit_view(self) -> None:
        bounds = self.pipeline.fit_view_bounds() if self.pipeline else None
        self.camera_rig.fit_view(bounds)

    def zoom_extents(self) -> None:
        if self.pipeline and self.pipeline.scene:
            self.pipeline.scene.refresh_bounds()
        if self.pipeline and self.pipeline.math_model:
            self.pipeline.math_model.refresh_bounds()
        self.fit_view()

    def default_xy_plane(self):
        if self.pipeline and self.pipeline.scene:
            from plane.plane_policy import PlaneFilterPolicy  # noqa
        if self.pipeline is None or self.pipeline.math_model is None:
            return None
        # project üzerinden
        from domain.project import Project
        project = getattr(self.pipeline, "_project", None)
        if project is None:
            return None
        return PlaneMode._default_xy_plane(project)

    # ------------------------------------------------------------------
    # Hover
    def set_viewport_pointer(self, viewport, x: int, y: int) -> None:
        if self.hover is not None:
            self.hover.set_pointer(viewport.name, x, y)

    def clear_hover(self) -> None:
        if self.hover is not None:
            self.hover.clear()

    def handle_pick_from_hover(self, ctrl: bool = False) -> None:
        if self.sel_mgr is None:
            return
        element = self.hover_element
        if element is not None:
            self.sel_mgr.select(element, additive=ctrl)
            return
        if not ctrl:
            self.sel_mgr.clear()

    def start_hover_pick(self, x: int, y: int) -> None:
        if self.hover is not None:
            self.hover.start_pick(x, y)

    def start_viewport_hover_pick(self, viewport, x: int, y: int) -> None:
        if self.hover is not None:
            self.hover.set_pointer(viewport.name, x, y)
            self.hover.start_pick(x, y, viewport=viewport)

    def check_pick_result(self) -> bool:
        if self.hover is None:
            return False
        return self.hover.check_pick_result()

    def _find_element(self, pick_id: int):
        return self.pipeline.get_element_by_id(pick_id) if self.pipeline else None

    # ------------------------------------------------------------------
    # Screen → world
    def screen_ray(self, x: float, y: float):
        from core.engine.ray_cast import screen_ray
        return screen_ray(self.cam, x, y, self.w, self.h)

    def _active_viewport(self):
        vm = getattr(self, "viewport_manager", None)
        return vm.active if vm is not None else None

    def screen_to_world(self, x: float, y: float, vp=None):
        from core.engine.ray_cast import screen_to_world
        target_vp = vp or self._active_viewport()
        cam = target_vp.camera if target_vp is not None else self.cam
        w = target_vp.width if target_vp is not None else self.w
        h = target_vp.height if target_vp is not None else self.h
        plane = getattr(target_vp, "plane", None) if target_vp is not None else self.active_working_plane
        return screen_to_world(cam, x, y, w, h, plane)

    def update_world_pos(self, x: float, y: float, vp=None) -> None:
        if self.input is None:
            return
        target_vp = vp or self._active_viewport()
        world = self.screen_to_world(x, y, vp=target_vp)
        if world is not None:
            self.input.mouse_world_pos = world
            self.input.mouse_world_valid = True
            plane = getattr(target_vp, "plane", None) if target_vp is not None else None
            if plane is not None:
                loc = plane.world_to_local((world.x, world.y, world.z))
                self.input.mouse_ucs_pos = (float(loc[0]), float(loc[1]), float(loc[2]))
                self.input.mouse_ucs_name = plane.name
            else:
                self.input.mouse_ucs_pos = (float(world.x), float(world.y), float(world.z))
                self.input.mouse_ucs_name = "Global"
            return
        self.input.mouse_world_valid = False
        self.input.mouse_ucs_pos = None

    # ------------------------------------------------------------------
    # Plane from element
    def start_plane_from_element(self) -> None:
        self._plane_from_element.start()

    def cancel_plane_from_element(self) -> None:
        self._plane_from_element.cancel()

    def toggle_plane_from_element_axis(self) -> None:
        self._plane_from_element.frame_axis_12 = not self._plane_from_element.frame_axis_12

    # ------------------------------------------------------------------
    # Cleanup
    def cleanup(self) -> None:
        if self.pipeline is not None:
            self.pipeline.cleanup()
        self.pipeline = None
        self.tools = None
        self.hover = None
        self.plane_mode = None

    # ------------------------------------------------------------------
    # Property delegasyonları — InteractionRenderer ve eski kod için
    @property
    def cam(self):
        return self.camera_rig.cam

    @property
    def renderer(self):
        return self.pipeline.renderer if self.pipeline else None

    @property
    def pick_pass(self):
        return self.pipeline.pick_pass if self.pipeline else None

    @property
    def mrt(self):
        return self.pipeline.mrt if self.pipeline else None

    @property
    def presentation_renderer(self):
        return self.pipeline.presentation if self.pipeline else None

    @property
    def interaction_renderer(self):
        return self.pipeline.interaction if self.pipeline else None

    @property
    def math_model_renderer(self):
        return self.pipeline.math_model_renderer if self.pipeline else None

    @property
    def grid(self):
        return self.pipeline.grid if self.pipeline else None

    @property
    def scene(self):
        return self.pipeline.scene if self.pipeline else None

    @property
    def math_model(self):
        return self.pipeline.math_model if self.pipeline else None

    @property
    def hover_id(self):
        return self.hover.element_id if self.hover else 0

    @property
    def hover_element(self):
        return self.hover.element if self.hover else None

    @property
    def preview_s(self):
        return self.gl.get("preview") if self.gl else None

    @property
    def pick_s(self):
        return self.gl.get("pick") if self.gl else None

    @property
    def sel_mgr(self):
        return self.tools.sel_mgr if self.tools else None

    @property
    def sel_policy(self):
        return self.tools.sel_policy if self.tools else None

    @property
    def draw_mgr(self):
        return self.tools.draw_mgr if self.tools else None

    @property
    def plane_draw_mgr(self):
        return self.tools.plane_draw_mgr if self.tools else None

    @property
    def marquee(self):
        return self.tools.marquee if self.tools else None

    @property
    def edit(self):
        return self.tools.edit if self.tools else None

    @property
    def snap(self):
        return self.tools.snap if self.tools else None

    @property
    def pending_pick_check(self):
        return self.hover._pending if self.hover else False

    @property
    def active_working_plane(self):
        return None  # pipeline._project üzerinden override edilebilir

    @property
    def viewport_pointer(self):
        return self.hover.pointer if self.hover else None
    def _combined_bounds(self):
        return self.pipeline.fit_view_bounds() if self.pipeline else None

    def set_scene(self, project) -> None:
        if self.pipeline is None:
            return
        if self.pipeline.interaction is not None:
            self.pipeline.interaction.preview_plane = None
        self.update_geo(project)
        self.fit_view()