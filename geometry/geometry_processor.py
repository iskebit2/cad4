# geometry/geometry_processor.py

from __future__ import annotations
import time

from copy import copy
from dataclasses import dataclass

import numpy as np

from plane.plane_policy import SectionFilterMode
from logging_config import CadLogger
logger = CadLogger.get(__name__)

@dataclass(slots=True)
class ProcessedGeometry:
    grid_axes: list
    lines: list
    polygons: list
    frames: list
    nodes: list
    areas: list
    links: list


class GeometryProcessor:
    """Prepare renderer-compatible geometry without depending on rendering code."""

    @classmethod
    def process(cls, scene, plane=None, math_model=None) -> ProcessedGeometry:
        t_start = time.perf_counter()
        total_steps = 7 if math_model is not None else 3
        current_step = 0

        current_step += 1
        
        t = time.perf_counter()
        grid_axes = cls.process_grid_axes(scene.grid, plane)
        logger.debug("[GP] grid_axes: %.1f ms", (time.perf_counter() - t) * 1000)

        current_step += 1
        
        t = time.perf_counter()
        lines = cls.process_lines(
            list(math_model.lines.values()) if math_model is not None else [],
            plane,
        )
        logger.debug("[GP] lines: %.1f ms", (time.perf_counter() - t) * 1000)

        current_step += 1
        
        t = time.perf_counter()
        polygons = cls.process_polygons(
            list(math_model.polygons.values()) if math_model is not None else [],
            plane,
        )
        logger.debug("[GP] polygons: %.1f ms", (time.perf_counter() - t) * 1000)

        frames, nodes, areas, links = [], [], [], []
        if math_model is not None:
            current_step += 1
        
            t = time.perf_counter()
            frames = cls.process_lines(list(math_model.frames.values()), plane)
            logger.debug("[GP] frames: %.1f ms", (time.perf_counter() - t) * 1000)

            current_step += 1
        
            t = time.perf_counter()
            nodes = cls.process_nodes(list(math_model.nodes.values()), plane)
            logger.debug("[GP] nodes: %.1f ms", (time.perf_counter() - t) * 1000)

            current_step += 1
        
            t = time.perf_counter()
            areas = cls.process_polygons(list(math_model.areas.values()), plane)
            logger.debug("[GP] areas: %.1f ms", (time.perf_counter() - t) * 1000)

            current_step += 1
        
            t = time.perf_counter()
            links = cls.process_lines(list(math_model.links.values()), plane)
            logger.debug("[GP] links: %.1f ms", (time.perf_counter() - t) * 1000)

        
        return ProcessedGeometry(
            grid_axes=grid_axes, lines=lines, polygons=polygons,
            frames=frames, nodes=nodes, areas=areas, links=links,
        )

    @classmethod
    def process_nodes(cls, nodes: list, plane) -> list:
        if plane is None or not nodes:
            return list(nodes)
        
        filtered = []
        for node in nodes:
            coords = getattr(node, "coords", None)
            if coords is None:
                coords = (node.x, node.y, node.z)
            if plane.element_passes_filter([np.asarray(coords, dtype=float)]):
                filtered.append(node)
        return filtered

    @staticmethod
    def _mode(plane):
        return getattr(plane, "filter_mode", SectionFilterMode.INTERSECT)

    @staticmethod
    def _coordinates(point) -> np.ndarray:
        coords = getattr(point, "coords", None)
        if coords is None:
            coords = (point.x, point.y, point.z)
        result = np.asarray(coords, dtype=float)
        if result.shape != (3,):
            raise ValueError("Geometri noktası üç koordinat içermeli")
        return result

    @staticmethod
    def _copy_point(point, coordinates):
        if not all(hasattr(point, name) for name in ("x", "y", "z")):
            return _CoordinatePoint(*map(float, coordinates))
        result = copy(point)
        if hasattr(result, "set_coords"):
            result.set_coords(*coordinates)
        else:
            result.x, result.y, result.z = map(float, coordinates)
        return result

    @classmethod
    def _copy_segment(cls, element, endpoint_names, start, end):
        result = copy(element)
        for name, coordinates in zip(endpoint_names, (start, end)):
            setattr(result, name, cls._copy_point(getattr(element, name), coordinates))
        result._geometry_source = getattr(element, "_geometry_source", element)
        return result

    @classmethod
    def process_grid_axes(cls, project_or_grid, plane=None) -> list:
        """Filter or clip grid axes for the active plane."""
        if hasattr(project_or_grid, "grid"):
            project = project_or_grid
            grid = project.grid
            if plane is None:
                plane = getattr(project, "active_plane", None)
        else:
            grid = project_or_grid

        axes = list(grid.axes)
        if plane is None:
            return axes

        processed = []
        is_clip = cls._mode(plane) == SectionFilterMode.CLIP
        for axis in axes:
            start, end = axis.start_point(), axis.end_point()
            if is_clip:
                clipped = plane.clip_line_segment(start, end)
                if clipped is None:
                    continue
                p0, p1 = clipped
                direction = p1 - p0
                length = float(np.linalg.norm(direction))
                if length <= 1e-12:
                    continue
                result = copy(axis)
                result.origin = tuple(float(v) for v in (p0 + p1) * 0.5)
                result.direction = tuple(float(v) for v in direction / length)
                result.length = length * 0.5
                processed.append(result)
            elif plane.element_passes_filter([start, end]):
                processed.append(axis)
        return processed

    @classmethod
    def process_lines(cls, lines: list, plane) -> list:
        """Filter or clip lines and frame-like segments efficiently."""
        if plane is None or not lines:
            return list(lines)

        processed = []
        is_clip = cls._mode(plane) == SectionFilterMode.CLIP
        
        first = lines[0]
        if hasattr(first, "v1") and hasattr(first, "v2"):
            endpoint_names = ("v1", "v2")
        elif hasattr(first, "node_i") and hasattr(first, "node_j"):
            endpoint_names = ("node_i", "node_j")
        else:
            endpoint_names = None

        for line in lines:
            if endpoint_names is None:
                if hasattr(line, "v1"):
                    ep_names = ("v1", "v2")
                elif hasattr(line, "node_i"):
                    ep_names = ("node_i", "node_j")
                else:
                    raise TypeError(f"Desteklenmeyen çizgi türü: {type(line).__name__}")
            else:
                ep_names = endpoint_names

            start = cls._coordinates(getattr(line, ep_names[0]))
            end = cls._coordinates(getattr(line, ep_names[1]))
            
            if is_clip:
                clipped = plane.clip_line_segment(start, end)
                if clipped is not None:
                    processed.append(
                        cls._copy_segment(line, ep_names, *clipped)
                    )
            elif plane.element_passes_filter([start, end]):
                processed.append(line)
        return processed

    @classmethod
    def process_polygons(cls, polygons: list, plane) -> list:
        """Filter surfaces or crop their boundaries against the plane bounds."""
        if plane is None or not polygons:
            return list(polygons)

        processed = []
        is_clip = cls._mode(plane) == SectionFilterMode.CLIP
        for polygon in polygons:
            nodes = list(getattr(polygon, "nodes", ()))
            if len(nodes) < 3:
                continue
            world_points = np.asarray([cls._coordinates(node) for node in nodes])

            if not is_clip:
                if plane.element_passes_filter(world_points.tolist()):
                    processed.append(polygon)
                continue

            local_points = np.asarray(
                [plane.world_to_local(point) for point in world_points], dtype=float,
            )
            clipped = cls._clip_polygon_to_bounds(plane, world_points, local_points)
            if len(clipped) < 3 or cls._polygon_area(clipped) <= 1e-18:
                continue

            if len(clipped) == len(world_points) and np.allclose(
                clipped, world_points, rtol=0.0, atol=1e-12,
            ):
                processed.append(polygon)
            else:
                result = copy(polygon)
                result.nodes = [
                    cls._copy_polygon_point(nodes, world_points, point)
                    for point in clipped
                ]
                result._geometry_source = getattr(
                    polygon, "_geometry_source", polygon,
                )
                processed.append(result)
        return processed

    @staticmethod
    def _clip_polygon_to_bounds(plane, world_points, local_points) -> np.ndarray:
        lower, upper = plane._association_bounds()
        tolerance = plane._association_tolerance(world_points, local_points)
        points = [point.copy() for point in local_points]

        for axis in range(3):
            if np.isfinite(lower[axis]):
                points = GeometryProcessor._clip_polygon_halfspace(
                    points, axis, lower[axis], keep_above=True, tolerance=tolerance,
                )
            if not points:
                return np.empty((0, 3), dtype=float)
            if np.isfinite(upper[axis]):
                points = GeometryProcessor._clip_polygon_halfspace(
                    points, axis, upper[axis], keep_above=False, tolerance=tolerance,
                )
            if not points:
                return np.empty((0, 3), dtype=float)

        cleaned = []
        for point in points:
            if not cleaned or np.linalg.norm(point - cleaned[-1]) > tolerance:
                cleaned.append(point)
        if len(cleaned) > 1 and np.linalg.norm(cleaned[0] - cleaned[-1]) <= tolerance:
            cleaned.pop()
        return np.asarray([plane.local_to_world(point) for point in cleaned], dtype=float)

    @classmethod
    def _copy_polygon_point(cls, nodes, world_points, point):
        distances = np.linalg.norm(world_points - point, axis=1)
        nearest = int(np.argmin(distances))
        if distances[nearest] <= 1e-10:
            return cls._copy_point(nodes[nearest], point)
        return _CoordinatePoint(*map(float, point))

    @staticmethod
    def _clip_polygon_halfspace(points, axis, bound, *, keep_above, tolerance):
        def inside(point):
            if keep_above:
                return point[axis] >= bound - tolerance
            return point[axis] <= bound + tolerance

        result = []
        previous = points[-1]
        previous_inside = inside(previous)
        for current in points:
            current_inside = inside(current)
            if current_inside != previous_inside:
                denominator = current[axis] - previous[axis]
                if abs(denominator) > 1e-15:
                    ratio = (bound - previous[axis]) / denominator
                    result.append(previous + ratio * (current - previous))
            if current_inside:
                result.append(current)
            previous, previous_inside = current, current_inside
        return result

    @staticmethod
    def _polygon_area(points) -> float:
        area_vector = np.zeros(3, dtype=float)
        origin = points[0]
        for index, point in enumerate(points):
            area_vector += np.cross(
                point - origin, points[(index + 1) % len(points)] - origin,
            )
        return float(np.linalg.norm(area_vector) * 0.5)


@dataclass(slots=True)
class _CoordinatePoint:
    x: float
    y: float
    z: float

    @property
    def coords(self):
        return self.x, self.y, self.z