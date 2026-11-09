from __future__ import annotations

from typing import Any

import numpy as np

from domain.grid import Grid
from domain.bounds import Bounds3D
from domain.lighting import Light, LightingSettings
from domain.line import Line
from domain.polygon import Polygon


class Scene:
    """Persistent presentation data, independent of the structural MathModel."""

    def __init__(self):
        self.grid = Grid()
        self.grid.scene = self
        
        self.polygons: dict[int, Polygon] = {}
        self.lines: dict[int, Line] = {}
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

        for polygon in self.polygons.values():
            if getattr(polygon, "is_visible", True):
                coords.extend(
                    (node.x, node.y, node.z) for node in polygon.nodes
                )
                for zones in polygon.zone_children_by_direction.values():
                    for zone in zones:
                        zone_coords = (
                            zone.get("coords", ())
                            if isinstance(zone, dict)
                            else getattr(zone, "coords", ())
                        )
                        coords.extend(
                            tuple(float(value) for value in point[:3])
                            for point in zone_coords
                            if len(point) >= 3
                        )
        for line in self.lines.values():
            if getattr(line, "visible", True):
                coords.extend((vertex.x, vertex.y, vertex.z) for vertex in line.vertices)

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

    def add_polygon(self, polygon: Polygon) -> None:
        self.polygons[polygon.unique_id] = polygon
        self.mark_dirty()

    def remove_polygon(self, polygon_id: int) -> bool:
        if self.polygons.pop(polygon_id, None) is None:
            return False
        self.mark_dirty()
        return True

    def add_line(self, line: Line) -> None:
        self.lines[line.unique_id] = line
        self.mark_dirty()

    def remove_line(self, line_id: int) -> bool:
        if self.lines.pop(line_id, None) is None:
            return False
        self.mark_dirty()
        return True

    @property
    def all_elements(self) -> dict[int, Any]:
        return {**self.polygons, **self.lines}

    def get_selected(self) -> list[Any]:
        return [
            element for element in self.all_elements.values()
            if getattr(element, "is_selected", False)
        ]

    def clear_selections(self) -> int:
        selected = self.get_selected()
        for element in selected:
            element.is_selected = False
        return len(selected)

    def get_element_by_unique_id(self, unique_id: int):
        return self.all_elements.get(unique_id)

    def __repr__(self) -> str:
        return (
            f"<Scene polygons={len(self.polygons)} lines={len(self.lines)}>"
        )

    def summary(self) -> str:
        return (
            "Scene:\n"
            f"  Grid axes: {len(self.grid.axes)}\n"
            f"  Polygons: {len(self.polygons)}\n"
            f"  Lines: {len(self.lines)}"
        )
