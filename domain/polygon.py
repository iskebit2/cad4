# domain/polygon.py
from __future__ import annotations

from dataclasses import dataclass, field

from pyglm import glm
import numpy as np

from core.id_manager import IDManager
from data import enums as E
from domain.element import Element
from domain.vertex import Vertex
from tools.polygon_frame_assoc import (
    angle_to_axis_deg, passes_direction_filter, segment_hits_band_and_box,
)


def _coords(v) -> tuple[float, float, float]:
    return (v.x, v.y, v.z)


@dataclass
class Polygon(Element):
    nodes: list = field(default_factory=list)
    poly_type: E.PolygonType = E.PolygonType.GENERIC
    dist_type: E.DistType = E.DistType.TWO_WAY
    is_temporary: bool = False
    zone_children_by_direction: dict = field(default_factory=dict)
    show_zones_direction: str | None = None

    # Assoc
    assoc_auto: bool = True
    assoc_depth: float = 500.0
    assoc_ignore_bounds: bool = False
    assoc_direction_filter: bool = True
    assoc_angle_tol_deg: float = 10.0
    associated: set[int] = field(default_factory=set)
    excluded: set[int] = field(default_factory=set)
    association_revision: int = 0

    element_type: str = "Polygon"

    def __post_init__(self):
        super().__post_init__()
        # color normalize: None → default rgba
        if self.color is None or len(self.color) < 4:
            self.color = [0.8, 0.3, 0.8, 0.6]

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
            return (glm.vec3(0), glm.vec3(1, 0, 0),
                    glm.vec3(0, 1, 0), glm.vec3(0, 0, 1))
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

    def to_vertices(self) -> list[Vertex]:
        return [
            v if isinstance(v, Vertex)
            else Vertex(*_coords(v), label=getattr(v, "label", ""))
            for v in self.nodes
        ]

    # ============ ASSOC ============

    def is_load_transfer(self) -> bool:
        return self.poly_type in E.LOAD_TRANSFER_POLYGON_TYPES

    def assoc_plane(self, *, depth: float | None = None):
        """Polygon düzleminde, polygon uv bbox'ı ve assoc_depth bandı ile Plane."""
        from plane.plane import Plane
        pl = Plane.from_polygon(self)
        d = self.assoc_depth if depth is None else float(depth)
        pl.depth_minus = pl.depth_plus = d
        us = [pl.to_2d(_coords(n))[0] for n in self.nodes]
        vs = [pl.to_2d(_coords(n))[1] for n in self.nodes]
        pl.set_bounds(min(us), max(us), min(vs), max(vs), recenter=False)
        return pl

    def _assoc_tolerance(self, pl, world_pts) -> float:
        scale = max(1.0, abs(pl.u_min), abs(pl.u_max),
                    abs(pl.v_min), abs(pl.v_max),
                    pl.depth_minus, pl.depth_plus)
        world = max(1.0, max(float(np.max(np.abs(p))) for p in world_pts))
        return max(scale * 1e-9, world * 32.0 * np.finfo(float).eps)

    def refresh_assoc(
        self,
        math_model,
        *,
        force: bool = False,
        write: bool = True,
        excluded_override: set[int] | None = None,
    ) -> set[int]:
        """
        Uygun frame'leri tarar.

        - `force=True`: `assoc_auto` bayrağını yok sayar.
        - `write=True`: sonucu `self.associated`'a yazar, `association_revision` artar.
        - `write=False`: sonucu sadece döndürür (panel draft modu).
        - `excluded_override`: `self.excluded` yerine bu küme kullanılır
          (draft modda panele ait geçici `excluded`).
        """
        if not force and not self.assoc_auto:
            return self.associated

        excluded = self.excluded if excluded_override is None else excluded_override
        pl = self.assoc_plane()
        lower = np.array((pl.u_min, pl.v_min, -pl.depth_minus))
        upper = np.array((pl.u_max, pl.v_max,  pl.depth_plus))
        tol = self._assoc_tolerance(
            pl, [np.asarray(_coords(n), float) for n in self.nodes]
        )
        apply_direction = (
            self.assoc_direction_filter
            and self.dist_type != E.DistType.TWO_WAY
        )

        associated: set[int] = set()
        for uid, fr in (math_model.frames.items() if math_model else ()):
            p1 = np.asarray(_coords(fr.node_i), float)
            p2 = np.asarray(_coords(fr.node_j), float)
            a = pl.world_to_local(p1)
            b = pl.world_to_local(p2)
            if not segment_hits_band_and_box(
                a, b, lower, upper,
                ignore_bounds=self.assoc_ignore_bounds, tol=tol,
            ):
                continue
            if apply_direction and not passes_direction_filter(
                p2 - p1, pl.u, pl.v, self.dist_type, self.assoc_angle_tol_deg,
            ):
                continue
            if uid in excluded:
                continue
            associated.add(int(uid))

        if write:
            self.associated = associated
            self.association_revision += 1
        return associated

    def toggle_assoc(self, uid: int, on: bool) -> bool:
        """Panelden manuel seçim. (Draft mekanizması paneldedir.)"""
        uid = int(uid)
        changed = False
        if on:
            if uid in self.excluded:
                self.excluded.discard(uid); changed = True
            if uid not in self.associated:
                self.associated.add(uid); changed = True
        else:
            if uid in self.associated:
                self.associated.discard(uid); changed = True
            if uid not in self.excluded:
                self.excluded.add(uid); changed = True
        if changed:
            self.association_revision += 1
        return changed

    def clear_excluded(self) -> bool:
        if not self.excluded:
            return False
        self.excluded.clear()
        self.association_revision += 1
        return True

    def set_dist_type(self, dist_type: E.DistType | str | int) -> None:
        """UI/panel setter. string/int/Enum hepsini kabul eder."""
        self.dist_type = E.DistType.from_input(dist_type)
        self.association_revision += 1

    def set_angle_tolerance(self, deg: float) -> None:
        self.assoc_angle_tol_deg = float(deg)
        self.association_revision += 1

    def set_assoc_depth(self, depth: float) -> None:
        self.assoc_depth = float(depth)
        self.association_revision += 1

    def assoc_frame_angle_deg(self, frame) -> float:
        """UI için: frame'in seçili local eksene göre açısı (derece).
        `dist_type == TWO_WAY` ise 0 döner (filtre yok)."""
        if self.dist_type == E.DistType.TWO_WAY:
            return 0.0
        u, v, _ = self.calculate_plane_axes(self.nodes)
        axis = v if self.dist_type == E.DistType.ONE_WAY_U2 else u
        a = glm.vec3(*(_coords(frame.node_i)))
        b = glm.vec3(*(_coords(frame.node_j)))
        d = np.array(tuple(b - a), float)
        return angle_to_axis_deg(d, np.array(tuple(axis), float))