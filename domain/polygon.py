# domain/polygon.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pyglm import glm

from core.id_manager import IDManager
from data import enums as E
from domain import definition as D
from domain.vertex import Vertex


def _coords(v) -> tuple[float, float, float]:
    return (v.x, v.y, v.z)


@dataclass
class Polygon:
    nodes: list = field(default_factory=list)
    label: str = ""
    poly_type: E.PolygonType = E.PolygonType.GENERIC
    color: list = field(default_factory=lambda: [0.8, 0.3, 0.8, 0.6])
    is_selected: bool = False
    is_visible: bool = True
    element_type: str = "Polygon"
    unique_id: int = field(default_factory=IDManager.generate_id)
    pick_id: int = 0
    show_axes_override: bool | None = None
    windplane: dict = field(default_factory=dict)
    is_temporary: bool = False
    uniform_to_frame_loads: list = field(default_factory=list)
    associated_frame_ids: list[int] = field(default_factory=list)
    assigned_loads: list = field(default_factory=list)
    load_pattern: str = ""
    transfer_target: str = "frames"
    transfer_dist_type: str = "one_way"
    is_load_area: bool = False
    zone_children_by_direction: dict = field(default_factory=dict)
    show_zones_direction: str | None = None
    needs_update: bool = True

    def __post_init__(self):
        self.pick_id = self.unique_id

    def toggle_selection(self):
        self.is_selected = not self.is_selected

    def mark_dirty(self):
        self.needs_update = True

    def collect_loads(self) -> list:
        return list(self.assigned_loads)

    def is_valid(self) -> bool:
        return len(self.nodes) >= 3

    def centroid(self) -> tuple[float, float, float]:
        if not self.nodes:
            return (0.0, 0.0, 0.0)
        n = len(self.nodes)
        xs = sum(_coords(v)[0] for v in self.nodes) / n
        ys = sum(_coords(v)[1] for v in self.nodes) / n
        zs = sum(_coords(v)[2] for v in self.nodes) / n
        return (xs, ys, zs)

    @staticmethod
    def calculate_normal(nodes, use_newell: bool = True) -> glm.vec3:
        n = glm.vec3(0, 0, 0)
        if use_newell:
            N = len(nodes)
            for i in range(N):
                a = _coords(nodes[i])
                b = _coords(nodes[(i + 1) % N])
                n.x += (a[1] - b[1]) * (a[2] + b[2])
                n.y += (a[2] - b[2]) * (a[0] + b[0])
                n.z += (a[0] - b[0]) * (a[1] + b[1])
        else:
            if len(nodes) < 3:
                return glm.vec3(0, 0, 1)
            a, b, c = _coords(nodes[0]), _coords(nodes[1]), _coords(nodes[2])
            v1 = glm.vec3(b[0] - a[0], b[1] - a[1], b[2] - a[2])
            v2 = glm.vec3(c[0] - a[0], c[1] - a[1], c[2] - a[2])
            n = glm.cross(v1, v2)
        L = glm.length(n)
        return n / L if L > 1e-9 else glm.vec3(0, 0, 1)

    @staticmethod
    def calculate_plane_axes(nodes) -> tuple[glm.vec3, glm.vec3, glm.vec3]:
        N = Polygon.calculate_normal(nodes)
        a = _coords(nodes[0])
        b = _coords(nodes[1])
        u = glm.vec3(b[0] - a[0], b[1] - a[1], b[2] - a[2])
        u = u - N * glm.dot(u, N)
        if glm.length(u) < 1e-6:
            u = glm.vec3(1, 0, 0) - N * N.x
        u = glm.normalize(u)
        v = glm.normalize(glm.cross(N, u))
        return u, v, N

    def get_plane_frame(self):
        if len(self.nodes) < 3:
            return glm.vec3(0), glm.vec3(1, 0, 0), glm.vec3(0, 1, 0), glm.vec3(0, 0, 1)
        u, v, n = self.calculate_plane_axes(self.nodes)
        cx, cy, cz = self.centroid()
        return glm.vec3(cx, cy, cz), u, v, n

    def classify_load_direction(self, load_dir_enum, cos_threshold: float = 0.85):
        u, v_ax, n = self.calculate_plane_axes(self.nodes)
        mapping = {
            E.LoadDirection.GLOBAL_X: glm.vec3(1, 0, 0),
            E.LoadDirection.GLOBAL_Y: glm.vec3(0, 1, 0),
            E.LoadDirection.GLOBAL_Z: glm.vec3(0, 0, 1),
            E.LoadDirection.GRAVITY: glm.vec3(0, 0, -1),
            E.LoadDirection.LOCAL_1: u,
            E.LoadDirection.LOCAL_2: v_ax,
            E.LoadDirection.LOCAL_3: n,
            E.LoadDirection.PROJECTED_X: glm.vec3(1, 0, 0),
            E.LoadDirection.PROJECTED_Y: glm.vec3(0, 1, 0),
            E.LoadDirection.PROJECTED_Z: glm.vec3(0, 0, 1),
        }
        if load_dir_enum not in mapping:
            return "UNKNOWN", glm.vec3(0, 0, -1)
        vec = mapping[load_dir_enum]
        vec = glm.normalize(vec) if glm.length(vec) > 1e-9 else vec
        dots = {"NORMAL": abs(glm.dot(vec, n)),
                "U": abs(glm.dot(vec, u)),
                "V": abs(glm.dot(vec, v_ax))}
        best = max(dots, key=dots.get)
        if dots[best] >= cos_threshold:
            return best, vec
        world = {"GX": abs(vec.x), "GY": abs(vec.y),
                 "GZ": abs(vec.z), "GRAV": abs(-vec.z)}
        best_w = max(world, key=world.get)
        if world[best_w] >= cos_threshold:
            return best_w, vec
        return "UNKNOWN", vec

    def add_uniform_to_frame_load(self, pattern_name, value, direction=None, dist_type=None):
        from domain.definition import AreaUniformToFrameLoad, DistType
        load = AreaUniformToFrameLoad(
            pattern_name=pattern_name.strip(),
            direction=direction if direction is not None else E.LoadDirection.GRAVITY,
            value=value,
            dist_type=dist_type if dist_type is not None else DistType.ONE_WAY,
            coordinate_system="GLOBAL",
        )
        self.uniform_to_frame_loads.append(load)
        self.mark_dirty()

    def to_vertices(self) -> list[Vertex]:
        return [v if isinstance(v, Vertex) else Vertex(*_coords(v), label=getattr(v, "label", ""))
                for v in self.nodes]