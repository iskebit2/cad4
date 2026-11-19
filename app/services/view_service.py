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

        vm = self.app.viewport_manager
        viewport = vm.active if vm is not None else None
        project = self.app.project_service.project
        if viewport is None:
            return

        plane = vm.ensure_viewport_plane(viewport, project)
        camera = viewport.camera

        if viewport.is_2d:
            viewport.is_2d = False
            camera.is_2d = False
            camera.clear_section_filter()
            if not camera.restore_view():
                vm.focus_viewport_on_plane(viewport, plane)
            viewport.invalidate_visible_ids()
            return

        camera.save_view()
        viewport.is_2d = True
        vm.focus_viewport_on_plane(viewport, plane)
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