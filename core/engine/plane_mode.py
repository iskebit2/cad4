# core/engine/plane_mode.py
from __future__ import annotations

from typing import TYPE_CHECKING

import app.commands as cmd

if TYPE_CHECKING:
    from core.engine.camera_rig import CameraRig
    from core.engine.renderer_pipeline import RendererPipeline
    from plane.plane import Plane
    from domain.project import Project


class PlaneMode:
    """2D/3D projeksiyon modu. Engine/app bilmez, komut üretir."""

    def __init__(self, camera_rig: "CameraRig", pipeline: "RendererPipeline",
                 command_queue) -> None:
        self.camera_rig = camera_rig
        self.pipeline = pipeline
        self.command_queue = command_queue
        self.active_plane: "Plane | None" = None
        self.is_2d: bool = False

    # ------------------------------------------------------------------
    def enter_2d(self, plane: "Plane") -> None:
        if plane is None:
            return
        self.camera_rig.enter_plane_2d(plane)
        self._set_projection("plane_2d")
        self.active_plane = plane
        self.is_2d = True

    def exit_2d(self) -> None:
        self.camera_rig.exit_plane_2d()
        self._set_projection("3d")
        self.active_plane = None
        self.is_2d = False

    def toggle(self, project: "Project | None") -> bool:
        """2D/3D arasında geç. Aktif plane seç ya da oluştur."""
        if self.is_2d:
            self.exit_2d()
            return True
        plane = self._resolve_plane(project)
        if plane is None:
            return False
        self.enter_2d(plane)
        return True

    # ------------------------------------------------------------------
    def _set_projection(self, mode: str) -> None:
        self.pipeline.renderer.projection = mode
        if self.pipeline.math_model_renderer:
            self.pipeline.math_model_renderer.projection = mode

    def _resolve_plane(self, project: "Project | None") -> "Plane | None":
        if project is None:
            return None
        plane = getattr(project, "active_plane", None)
        if plane is not None:
            return plane
        plane = self._default_xy_plane(project)
        if plane is not None:
            project.activate_plane(plane)
        return plane

    @staticmethod
    def _default_xy_plane(project: "Project") -> "Plane | None":
        planes = project.grid_planes() if hasattr(project, "grid_planes") else []
        for p in planes:
            if p.name == "XY_Z0":
                return p
        for p in planes:
            if p.name.startswith("XY_Z"):
                return p
        return None