from __future__ import annotations

import numpy as np

from domain.grid import Grid
from domain.bounds import Bounds3D
from domain.lighting import Light, LightingSettings


class Scene:
    """Persistent presentation data, independent of the structural MathModel."""

    def __init__(self):
        self.grid = Grid()
        self.grid.scene = self
        self.lighting = LightingSettings()
        self._bounds: Bounds3D | None = None
        self.show_local_axes = False
        self.show_local_axes_for_selected = True
        self.show_local_axes_scale = 1.0
        self.units = "N, mm, C"
        self._is_dirty = True

    @property
    def lights(self) -> list[Light]:
        return self.lighting.lights

    def compute_bounds(self) -> Bounds3D | None:
        coords = []
        grid_coords = (
            self.grid.x_coords,
            self.grid.y_coords,
            self.grid.z_coords,
        )
        if any(grid_coords):
            coords.extend(
                (x, y, z)
                for x in (self.grid.x_coords or [0.0])
                for y in (self.grid.y_coords or [0.0])
                for z in (self.grid.z_coords or [0.0])
            )

        if not coords:
            return None
        arr = np.asarray(coords, dtype=float)
        return Bounds3D(min=arr.min(axis=0), max=arr.max(axis=0))

    @property
    def bounds(self) -> Bounds3D | None:
        self._bounds = self.compute_bounds()
        return self._bounds

    def refresh_bounds(self) -> Bounds3D | None:
        self._bounds = self.compute_bounds()
        return self._bounds

    def clear_bounds(self) -> None:
        self._bounds = None

    def mark_dirty(self) -> None:
        self._is_dirty = True
        self.clear_bounds()

    def is_dirty(self) -> bool:
        return self._is_dirty

    def clear_dirty(self) -> None:
        self._is_dirty = False

    def __repr__(self) -> str:
        return f"<Scene grid_axes={len(self.grid.axes)}>"

    def summary(self) -> str:
        return (
            "Scene:\n"
            f"  Grid axes: {len(self.grid.axes)}"
        )
