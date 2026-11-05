# domain/grid.py
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterator

import numpy as np

from core.units import Dimension


@dataclass
class Axis:
    name: str = ""
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    direction: tuple[float, float, float] = (1.0, 0.0, 0.0)
    length: float = 10000.0
    label: str = ""
    color: tuple[float, float, float] = (0.55, 0.55, 0.60)
    visible: bool = True
    kind: str = "custom"
    parallel_spacing: float = 0.0
    parallel_count: int = 0
    skip_bubble: bool = False

    __unit_schema__ = {
        "origin": Dimension.LENGTH,
        "length": Dimension.LENGTH,
        "parallel_spacing": Dimension.LENGTH,
    }

    def normalized_direction(self) -> np.ndarray:
        d = np.asarray(self.direction, dtype=float)
        n = np.linalg.norm(d)
        return d / n if n > 1e-9 else np.array([1.0, 0.0, 0.0])

    def start_point(self) -> np.ndarray:
        return np.asarray(self.origin) - self.normalized_direction() * self.length

    def end_point(self) -> np.ndarray:
        return np.asarray(self.origin) + self.normalized_direction() * self.length


@dataclass
class ObliqueAxis:
    name: str = ""
    p1: tuple[float, float] = (0.0, 0.0)
    p2: tuple[float, float] = (0.0, 0.0)
    color: tuple[float, float, float] = (0.85, 0.65, 0.12)
    visible: bool = True

    __unit_schema__ = {"p1": Dimension.LENGTH, "p2": Dimension.LENGTH}


@dataclass
class Grid:
    x_coords: list[float] = field(default_factory=list)
    y_coords: list[float] = field(default_factory=list)
    z_coords: list[float] = field(default_factory=list)
    x_labels: list[str] = field(default_factory=list)
    y_labels: list[str] = field(default_factory=list)
    z_labels: list[str] = field(default_factory=list)

    oblique_axes: list[ObliqueAxis] = field(default_factory=list)
    boundary_coords: list[tuple[float, float]] = field(default_factory=list)

    bubble_offset: float = 1000.0
    show_labels: bool = True
    label_position: str = "end"
    label_overflow: float = 200.0
    default_color: tuple[float, float, float] = (0.55, 0.55, 0.60)

    color_x: tuple[float, float, float] = (0.70, 0.25, 0.25)
    color_y: tuple[float, float, float] = (0.25, 0.70, 0.25)
    color_z: tuple[float, float, float] = (0.25, 0.45, 0.70)
    color_boundary: tuple[float, float, float] = (0.50, 0.50, 0.55)

    __unit_schema__ = {
        "x_coords": Dimension.LENGTH,
        "y_coords": Dimension.LENGTH,
        "z_coords": Dimension.LENGTH,
        "bubble_offset": Dimension.LENGTH,
        "label_overflow": Dimension.LENGTH,
    }

    def __post_init__(self):
        if not self.x_coords and not self.y_coords:
            self.create_default()

    def create_default(self):
        self.x_coords = [0.0, 4000.0, 8000.0]
        self.y_coords = [0.0, 5000.0, 10000.0]
        self.z_coords = [0.0, 4000.0]
        self.x_labels = ["X1", "X2", "X3"]
        self.y_labels = ["Y1", "Y2", "Y3"]
        self.z_labels = ["Z1", "Z2"]

    # ------------------------------------------------------------------
    @property
    def axes(self) -> list[Axis]:
        if not self.x_coords or not self.y_coords:
            return []

        xs = sorted(set(self.x_coords))
        ys = sorted(set(self.y_coords))
        zs = sorted(set(self.z_coords)) or [0.0]
        first_z = zs[0]
        cx, cy = (xs[0] + xs[-1]) / 2, (ys[0] + ys[-1]) / 2
        cz = (zs[0] + zs[-1]) / 2
        half_z = (zs[-1] - zs[0]) / 2

        axes: list[Axis] = []
        axes += self._ortho_axes(xs, ys, zs, first_z, self.color_x, "ortho_x", "X", self.x_labels, self._y_range)
        axes += self._ortho_axes(ys, xs, zs, first_z, self.color_y, "ortho_y", "Y", self.y_labels, self._x_range, swap=True)
        axes += self._z_axes(xs, ys, zs, cz, half_z)
        axes += self._oblique_axes(zs, first_z)
        axes += self._boundary_axes(zs, cz, half_z)
        return axes

    def _ortho_axes(self, prim, sec, zs, first_z, color, kind, prefix, labels, range_fn, swap=False):
        out = []
        for i, p in enumerate(prim):
            rng = range_fn(p)
            if rng is None or abs(rng[1] - rng[0]) < 1e-6:
                continue
            label = labels[i] if i < len(labels) and labels[i] else f"{prefix}{i + 1}"
            for z in zs:
                origin = (p, (rng[0] + rng[1]) / 2, z) if not swap else ((rng[0] + rng[1]) / 2, p, z)
                direction = (0.0, 1.0, 0.0) if not swap else (1.0, 0.0, 0.0)
                out.append(Axis(
                    name=f"{prefix}_{i}_z{z:g}",
                    origin=origin,
                    direction=direction,
                    length=(rng[1] - rng[0]) / 2,
                    label=label if z == first_z else "",
                    kind=kind,
                    color=color,
                ))
        return out

    def _z_axes(self, xs, ys, zs, cz, half_z):
        out = []
        for x in xs:
            for y in ys:
                if self._in_boundary(x, y):
                    out.append(Axis(
                        name=f"Z_{x:g}_{y:g}",
                        origin=(x, y, cz),
                        direction=(0.0, 0.0, 1.0),
                        length=half_z,
                        kind="ortho_z",
                        color=self.color_z,
                        skip_bubble=True,
                    ))
        return out

    def _oblique_axes(self, zs, first_z):
        out = []
        for i, obl in enumerate(self.oblique_axes):
            if not obl.visible:
                continue
            clipped = self._clip_to_boundary(obl.p1, obl.p2)
            if clipped is None:
                continue
            (x1, y1), (x2, y2) = clipped
            dx, dy = x2 - x1, y2 - y1
            L = math.hypot(dx, dy)
            if L < 1e-9:
                continue
            for z in zs:
                out.append(Axis(
                    name=f"O_{i}_z{z:g}",
                    origin=((x1 + x2) / 2, (y1 + y2) / 2, z),
                    direction=(dx / L, dy / L, 0.0),
                    length=L / 2,
                    label=obl.name if z == first_z else "",
                    kind="oblique",
                    color=obl.color,
                ))
        return out

    def _boundary_axes(self, zs, cz, half_z):
        n = len(self.boundary_coords)
        if n < 3:
            return []
        out = []
        for i in range(n):
            p1 = self.boundary_coords[i]
            p2 = self.boundary_coords[(i + 1) % n]
            dx, dy = p2[0] - p1[0], p2[1] - p1[1]
            L = math.hypot(dx, dy)
            if L < 1e-9:
                continue
            for z in zs:
                out.append(Axis(
                    name=f"B_{i}_z{z:g}",
                    origin=((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2, z),
                    direction=(dx / L, dy / L, 0.0),
                    length=L / 2,
                    kind="boundary",
                    color=self.color_boundary,
                ))
        if len(zs) > 1:
            for i, (x, y) in enumerate(self.boundary_coords):
                out.append(Axis(
                    name=f"BZ_{i}",
                    origin=(x, y, cz),
                    direction=(0.0, 0.0, 1.0),
                    length=half_z,
                    kind="boundary",
                    color=self.color_boundary,
                    skip_bubble=True,
                ))
        return out

    # ------------------------------------------------------------------
    def _y_range(self, x):
        return self._scan(x, axis=1)

    def _x_range(self, y):
        return self._scan(y, axis=0)

    def _scan(self, v, axis):
        if len(self.boundary_coords) < 3:
            coords = sorted(set(self.y_coords if axis == 1 else self.x_coords))
            return (coords[0], coords[-1]) if coords else None
        vals = []
        n = len(self.boundary_coords)
        for i in range(n):
            a = self.boundary_coords[i]
            b = self.boundary_coords[(i + 1) % n]
            lo, hi = (a[axis], b[axis])
            if lo <= v <= hi or hi <= v <= lo:
                other = 1 - axis
                if abs(b[axis] - a[axis]) < 1e-9:
                    vals += [a[other], b[other]]
                else:
                    t = (v - a[axis]) / (b[axis] - a[axis])
                    if -1e-9 <= t <= 1 + 1e-9:
                        vals.append(a[other] + t * (b[other] - a[other]))
        return (min(vals), max(vals)) if vals else None

    def _in_boundary(self, x, y):
        if len(self.boundary_coords) < 3:
            return True
        n = len(self.boundary_coords)
        for i in range(n):
            x1, y1 = self.boundary_coords[i]
            x2, y2 = self.boundary_coords[(i + 1) % n]
            if self._on_segment(x, y, x1, y1, x2, y2):
                return True
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = self.boundary_coords[i]
            xj, yj = self.boundary_coords[j]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
                inside = not inside
            j = i
        return inside

    @staticmethod
    def _on_segment(px, py, x1, y1, x2, y2, eps=1e-9):
        cross = (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)
        if abs(cross) > eps:
            return False
        return min(x1, x2) - eps <= px <= max(x1, x2) + eps \
        and min(y1, y2) - eps <= py <= max(y1, y2) + eps

    def _clip_to_boundary(self, p1, p2):
        if len(self.boundary_coords) < 3:
            return (tuple(p1), tuple(p2))
        x1, y1 = p1
        x2, y2 = p2
        dx, dy = x2 - x1, y2 - y1
        if math.hypot(dx, dy) < 1e-9:
            return None
        ts = [0.0, 1.0]
        n = len(self.boundary_coords)
        for i in range(n):
            bx1, by1 = self.boundary_coords[i]
            bx2, by2 = self.boundary_coords[(i + 1) % n]
            bdx, bdy = bx2 - bx1, by2 - by1
            denom = dx * bdy - dy * bdx
            if abs(denom) < 1e-12:
                continue
            t = ((bx1 - x1) * bdy - (by1 - y1) * bdx) / denom
            u = ((bx1 - x1) * dy - (by1 - y1) * dx) / denom
            if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
                ts.append(max(0.0, min(1.0, t)))
        ts.sort()
        best = (None, None)
        for k in range(len(ts) - 1):
            ts_, te = ts[k], ts[k + 1]
            if te - ts_ < 1e-9:
                continue
            tm = (ts_ + te) / 2
            if self._in_boundary(x1 + tm * dx, y1 + tm * dy):
                if best[0] is None or ts_ < best[0]:
                    best = (ts_, best[1])
                if best[1] is None or te > best[1]:
                    best = (best[0], te)
        if best[0] is None or best[1] is None or best[1] - best[0] < 1e-6:
            return None
        return (
            (x1 + best[0] * dx, y1 + best[0] * dy),
            (x1 + best[1] * dx, y1 + best[1] * dy),
        )

    # ------------------------------------------------------------------
    @property
    def all_oblique_lines(self):
        lines = [(o.p1, o.p2) for o in self.oblique_axes if o.visible]
        n = len(self.boundary_coords)
        for i in range(n):
            lines.append((self.boundary_coords[i], self.boundary_coords[(i + 1) % n]))
        return lines

    def snap_points(self, z_level=None):
        if not self.x_coords or not self.y_coords:
            return []
        xs = sorted(set(self.x_coords))
        ys = sorted(set(self.y_coords))
        zs = [z_level] if z_level is not None else (sorted(set(self.z_coords)) or [0.0])

        pts = []
        for x in xs:
            for y in ys:
                if self._in_boundary(x, y):
                    pts += [(x, y, z) for z in zs]

        for p1, p2 in self.all_oblique_lines:
            for x in xs:
                y = self._line_at(p1, p2, x, axis=0)
                if y is not None and self._in_boundary(x, y):
                    pts += [(x, y, z) for z in zs]
            for y in ys:
                x = self._line_at(p1, p2, y, axis=1)
                if x is not None and self._in_boundary(x, y):
                    pts += [(x, y, z) for z in zs]

        lines = self.all_oblique_lines
        for i, (a1, a2) in enumerate(lines):
            for b1, b2 in lines[i + 1:]:
                ipt = self._segment_intersect(a1, a2, b1, b2)
                if ipt and self._in_boundary(*ipt):
                    pts += [(ipt[0], ipt[1], z) for z in zs]

        for x, y in self.boundary_coords:
            pts += [(x, y, z) for z in zs]

        for o in self.oblique_axes:
            if o.visible:
                for p in (o.p1, o.p2):
                    if self._in_boundary(*p):
                        pts += [(p[0], p[1], z) for z in zs]

        seen, out = set(), []
        for pt in pts:
            k = (round(pt[0], 6), round(pt[1], 6), round(pt[2], 6))
            if k not in seen:
                seen.add(k)
                out.append(pt)
        return out

    def snap_points_on_plane(self, plane_axis, level):
        all_pts = self.snap_points()
        axis = plane_axis.lower()
        if axis == "z":
            return [p for p in all_pts if abs(p[2] - level) < 1e-3]
        if axis == "y":
            return [p for p in all_pts if abs(p[1] - level) < 1e-3]
        if axis == "x":
            return [p for p in all_pts if abs(p[0] - level) < 1e-3]
        return all_pts

    @staticmethod
    def _line_at(p1, p2, v, axis):
        a, b = p1[axis], p2[axis]
        if abs(b - a) < 1e-9:
            return None
        t = (v - a) / (b - a)
        other = 1 - axis
        return p1[other] + t * (p2[other] - p1[other]) if 0.0 <= t <= 1.0 else None

    @staticmethod
    def _segment_intersect(p1a, p2a, p1b, p2b):
        x1, y1 = p1a; x2, y2 = p2a
        x3, y3 = p1b; x4, y4 = p2b
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-9:
            return None
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
        u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom
        if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
            return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
        return None

    def visible_axes(self) -> Iterator[Axis]:
        return (a for a in self.axes if a.visible)

    def get_bounds(self):
        if not self.x_coords or not self.y_coords:
            return None
        xs = sorted(set(self.x_coords))
        ys = sorted(set(self.y_coords))
        zs = sorted(set(self.z_coords)) or [0.0]
        mn = np.array([xs[0], ys[0], zs[0]])
        mx = np.array([xs[-1], ys[-1], zs[-1]])
        center = (mn + mx) / 2
        size = max(float(np.linalg.norm(mx - mn)), 1000.0)
        return (tuple(float(v) for v in center), size)