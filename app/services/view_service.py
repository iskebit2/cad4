# app/services/view_service.py
from __future__ import annotations

from typing import TYPE_CHECKING

from logging_config import CadLogger

if TYPE_CHECKING:
    from app.cad_app import CadApp

logger = CadLogger.get(__name__)


class ViewService:
    """Kamera, 2D plane, render modu, load görünürlüğü."""

    def __init__(self, app: "CadApp"):
        self.app = app

    def _active_camera(self):
        eng = self.app.engine
        if eng is None:
            return None
        viewport_manager = self.app.viewport_manager
        viewport = viewport_manager.active if viewport_manager is not None else None
        return viewport.camera if viewport is not None else eng.cam

    def fit_view(self) -> None:
        eng = self.app.engine
        camera = self._active_camera()
        if eng is None or camera is None:
            return

        bounds = eng.pipeline.fit_view_bounds() if eng.pipeline else None
        if bounds is None:
            camera.update_bounds((0.0, 0.0, 0.0), 10000.0)
        else:
            camera.update_bounds(bounds.center, bounds.size)
        camera.focus_on_model()

    def zoom_extents(self) -> None:
        eng = self.app.engine
        if eng is None:
            return
        if eng.pipeline and eng.pipeline.scene:
            eng.pipeline.scene.refresh_bounds()
        if eng.pipeline and eng.pipeline.math_model:
            eng.pipeline.math_model.refresh_bounds()
        self.fit_view()

    def set_camera_preset(self, preset: str) -> None:
        camera = self._active_camera()
        if camera is not None:
            camera.set_view_preset(preset)

    # ---- 2D / plane ----
    def toggle_2d(self) -> None:
        eng = self.app.engine
        if eng is None:
            return
        if eng.plane_draw_mgr.is_active:
            eng.plane_draw_mgr.cancel()

        viewport_manager = self.app.viewport_manager
        viewport = viewport_manager.active if viewport_manager is not None else None
        project = self.app.project_service.project
        if viewport is None:
            if eng.plane_mode is not None:
                eng.plane_mode.toggle(project)
            return

        camera = viewport.camera
        if viewport.is_2d:
            if not camera.restore_view():
                camera.set_view_preset("iso_nw")
            camera.clear_section_filter()
            viewport.is_2d = False
            viewport.plane = None
            viewport.invalidate_visible_ids()
            return

        plane = project.active_plane
        if plane is None:
            planes = project.grid_planes()
            plane = next((p for p in planes if p.name == "XY_Z0"), None)
            if plane is None:
                plane = next((p for p in planes if p.name.startswith("XY_Z")), None)
            if plane is not None:
                project.activate_plane(plane)
        if plane is None:
            return

        uc = 0.5 * ((plane.u_min or 0.0) + (plane.u_max or 0.0))
        vc = 0.5 * ((plane.v_min or 0.0) + (plane.v_max or 0.0))
        center = plane.to_3d((uc, vc))
        half_u = 0.5 * abs((plane.u_max or 0.0) - (plane.u_min or 0.0))
        half_v = 0.5 * abs((plane.v_max or 0.0) - (plane.v_min or 0.0))
        fit_radius = max(half_u, half_v) * 1.4
        if fit_radius < 1e-6:
            bounds = eng.pipeline.fit_view_bounds() if eng.pipeline else None
            fit_radius = float(bounds.size) if bounds is not None else 1000.0

        camera.save_view()
        camera.look_at_plane(
            origin=center, u=plane.u, v=plane.v, n=plane.normal,
            fit_radius=fit_radius,
        )
        camera.set_section_filter(
            normal=plane.normal, origin=plane.origin,
            min_s=-plane.depth_minus, max_s=plane.depth_plus,
        )
        viewport.plane = plane
        viewport.is_2d = True
        viewport.invalidate_visible_ids()

    def activate_plane(self, plane) -> None:
        project = self.app.project_service.project
        if plane is None:
            project.deactivate_plane()
        else:
            project.activate_plane(plane)
        eng = self.app.engine
        if eng is None:
            return
        if eng.interaction_renderer:
            eng.interaction_renderer.preview_plane = None
        if eng.renderer is not None and eng.math_model is not None:
            eng.update_geo(project)
        if eng.sel_mgr:
            eng.sel_mgr.clear()

    # ---- loads ----
    def get_loads_visible(self) -> bool:
        pres = getattr(self.app.engine, "presentation_renderer", None)
        loads = getattr(pres, "loads", None)
        return bool(loads and loads.enabled)

    def set_loads_visible(self, enabled: bool) -> None:
        pres = getattr(self.app.engine, "presentation_renderer", None)
        loads = getattr(pres, "loads", None)
        if loads is None:
            return
        loads.enabled = bool(enabled)
        eng = self.app.engine
        if enabled and eng and eng.math_model:
            pres.update_loads(eng.math_model, camera_scale=1.0, scene_size=1.0)