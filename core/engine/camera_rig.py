# core/engine/camera_rig.py
from __future__ import annotations

from typing import TYPE_CHECKING

from core.camera import Camera

if TYPE_CHECKING:
    from domain.bounds import Bounds3D
    from plane.plane import Plane


class CameraRig:
    """Kamera + view operasyonları. Engine/app bilmez."""

    def __init__(self, width: int, height: int) -> None:
        self.width = max(1, int(width))
        self.height = max(1, int(height))
        self.cam = Camera()
        self.cam.set_aspect(self.width, self.height)
        self.cam.pitch = 30.0
        self.cam.yaw = -45.0
        self.cam.distance = 50.0
        self.cam._update_position()

    def resize(self, width: int, height: int) -> None:
        self.width = max(1, int(width))
        self.height = max(1, int(height))
        self.cam.set_aspect(self.width, self.height)

    def fit_view(self, bounds: "Bounds3D | None") -> None:
        if bounds is not None:
            self.cam.update_bounds(bounds.center, bounds.size)
        else:
            self.cam.update_bounds((0.0, 0.0, 0.0), 10000.0)
        self.cam.focus_on_model()

    def zoom_extents(self, bounds: "Bounds3D | None") -> None:
        self.fit_view(bounds)

    def enter_plane_2d(self, plane: "Plane") -> None:
        if plane is None:
            return
        self.cam.save_view()
        uc = 0.5 * ((plane.u_min or 0.0) + (plane.u_max or 0.0))
        vc = 0.5 * ((plane.v_min or 0.0) + (plane.v_max or 0.0))
        center = plane.to_3d((uc, vc))
        half_u = 0.5 * abs((plane.u_max or 0.0) - (plane.u_min or 0.0))
        half_v = 0.5 * abs((plane.v_max or 0.0) - (plane.v_min or 0.0))
        fit_radius = max(half_u, half_v) * 1.4
        if fit_radius < 1e-6:
            fit_radius = 1000.0
        self.cam.look_at_plane(
            origin=center, u=plane.u, v=plane.v, n=plane.normal,
            fit_radius=fit_radius,
        )
        self.cam.set_section_filter(
            normal=plane.normal, origin=plane.origin,
            min_s=-plane.depth_minus, max_s=plane.depth_plus,
        )

    def exit_plane_2d(self) -> None:
        self.cam.restore_view()
        self.cam.clear_section_filter()