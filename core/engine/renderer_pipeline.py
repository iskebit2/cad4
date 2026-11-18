# core/engine/renderer_pipeline.py
from __future__ import annotations

from typing import TYPE_CHECKING

from OpenGL.GL import (
    GL_COLOR_ATTACHMENT0, GL_FRAMEBUFFER,
    glBindFramebuffer, glDrawBuffer, glViewport,
)

from core.mrt import MRTFramebuffer
from render.interactionrenderer import InteractionRenderer
from render.mathmodelrenderer import MathModelRenderer
from render.scenerenderer import SceneRenderer
from geometry.geometry_processor import GeometryProcessor
from logging_config import CadLogger

if TYPE_CHECKING:
    from core.engine.camera_rig import CameraRig
    from domain.project import Project
    from viewport.viewport import Viewport

logger = CadLogger.get(__name__)


class RendererPipeline:
    """MRT + SceneRenderer + pick_pass. Interaction Engine.render_viewport'ta."""

    def __init__(self, width: int, height: int,
                 shaders: dict, snap_renderer) -> None:
        self.width = max(1, int(width))
        self.height = max(1, int(height))
        self.shaders = shaders
        self.mrt = MRTFramebuffer(self.width, self.height)

        self.scene = None
        self.math_model = None

        self.renderer = None
        self.presentation = None
        self.interaction = None
        self.snap = snap_renderer
        self.pick_pass = None

        self._build()

    def _build(self) -> None:
        s = self.shaders
        mmr = MathModelRenderer(
            pick_s=s["pick"], standard_s=s["standard"],
            node_s=s["node"], simple_s=s["simple"],
            overlay_s=s["2d_overlay"], axes_s=s["axes"],
            w=self.width, h=self.height,
        )
        self.renderer = SceneRenderer(
            standard_shader=s["standard"],
            axes_shader=s["axes"],
            overlay_shader=s["2d_overlay"],
            simple_shader=s["simple"],
            grid_shader=s["grid"],
            math_model_renderer=mmr,
        )
        self.pick_pass = self.renderer.pick_pass
        self.pick_pass.set_main_fbo(self.mrt.fbo)
        self.renderer.set_snap(self.snap)
        self.presentation = self.renderer.presentation_renderer
        self.interaction = InteractionRenderer(overlay_shader=s["2d_overlay"])

    # ------------------------------------------------------------------
    def resize(self, width: int, height: int) -> None:
        self.width = max(1, int(width))
        self.height = max(1, int(height))
        self.mrt.resize(self.width, self.height)
        self.renderer.resize(self.width, self.height)
        self.pick_pass.set_viewport(self.width, self.height)
        self.pick_pass.set_main_fbo(self.mrt.fbo)

    def update_geo(self, project: "Project | None") -> None:
        if project is None:
            return
        self.scene = project.scene
        self.math_model = project.math_model
        if self.presentation is None:
            return
        geo = GeometryProcessor.process(project.scene, None, project.math_model)
        self.renderer.update_geo(
            project.math_model, project.scene,
            polygons=geo.polygons, lines=geo.lines, grid_axes=geo.grid_axes,
            frames=geo.frames, nodes=geo.nodes, areas=geo.areas, links=geo.links,
        )
        cam_scale = (
            self.renderer._compute_cam_scale()
            if hasattr(self.renderer, "_compute_cam_scale") else 1.0
        )
        self.presentation.update_loads(
            project.math_model,
            camera_scale=cam_scale,
            scene_size=getattr(self.renderer, "size", 1.0),
            unit_system=project.unit_system,
            wind_results=project.loads.wind_results,
        )

    def render(self, vp: "Viewport", camera_rig: "CameraRig") -> None:
        """Sadece scene render + blit. Interaction Engine'de çağrılır."""
        if not self.renderer or not self.mrt:
            return

        self.mrt.bind()
        self.mrt.clear()
        glViewport(0, 0, vp.width, vp.height)
        glDrawBuffer(GL_COLOR_ATTACHMENT0)

        self.renderer.render(
            vp.camera, vp.fbo.fbo, force_id_pass=True,
            viewport_name=vp.name, plane=vp.plane, visible_ids=vp.visible_ids,
        )

        self.mrt.blit_to(
            vp.fbo.fbo,
            target_w=vp.width, target_h=vp.height,
            copy_id=True,
            source_w=vp.width, source_h=vp.height,
        )

        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        # glViewport(0, 0, self.width, self.height)

    # ------------------------------------------------------------------
    def get_element_by_id(self, pick_id: int):
        if self.renderer is None:
            return None
        return self.renderer.get_element_from_id(pick_id)

    def in_section(self, element, camera, plane) -> bool:
        mmr = self.math_model_renderer
        if mmr is None:
            return True
        return mmr._element_in_section(element, camera, plane)

    def iter_render_elements(self):
        mmr = self.math_model_renderer
        if mmr is None:
            return
        for elems in mmr._render_elements.values():
            yield from elems

    @property
    def math_model_renderer(self):
        return getattr(self.renderer, "math_model_renderer", None) if self.renderer else None

    @property
    def grid(self):
        return self.presentation.grid if self.presentation else None

    def fit_view_bounds(self):
        from domain.bounds import Bounds3D
        import numpy as np
        items = [b for b in (
            self.scene.bounds if self.scene else None,
            self.math_model.bounds if self.math_model else None,
        ) if b is not None]
        if not items:
            return None
        minimum = np.min([item.min for item in items], axis=0)
        maximum = np.max([item.max for item in items], axis=0)
        return Bounds3D(min=minimum, max=maximum)

    def cleanup(self) -> None:
        if self.renderer:
            self.renderer.cleanup()
        if self.interaction and hasattr(self.interaction, "cleanup"):
            self.interaction.cleanup()
        if self.mrt:
            self.mrt.cleanup()