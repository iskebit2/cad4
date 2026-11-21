from __future__ import annotations

from typing import TYPE_CHECKING

from logging_config import CadLogger

if TYPE_CHECKING:
    from app.cad_app import CadApp

logger = CadLogger.get(__name__)


class ViewService:
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

    def toggle_2d(self) -> None:
        eng = self.app.engine
        if eng is None:
            return
        vm = self.app.viewport_manager
        viewport = vm.active if vm is not None else None
        if viewport is None:
            return

        bounds = eng._combined_bounds()
        fallback_center = bounds.center if bounds is not None else None
        fallback_radius = float(bounds.size) if bounds is not None else 2000.0

        if viewport.is_2d:
            viewport.is_2d = False
            viewport.camera.is_2d = False
            if not viewport.camera.restore_view():
                viewport.focus_on_volume(
                    fallback_center=fallback_center,
                    fallback_radius=fallback_radius,
                )
            return

        viewport.camera.save_view()
        viewport.is_2d = True
        viewport.focus_on_volume(
            fallback_center=fallback_center,
            fallback_radius=fallback_radius,
        )
