# plane/plane.py

from __future__ import annotations

import uuid
from dataclasses import dataclass

import mapbox_earcut as earcut
import numpy as np

from core.units import Dimension, UnitSystem, convert_value


class ChangeOp:
    ADD = "add"
    MODIFY = "modify"
    DELETE = "delete"
    ALL = (ADD, MODIFY, DELETE)
    APPLY_ORDER = (DELETE, MODIFY, ADD)


@dataclass
class PendingChange:
    op: str
    kind: str
    id: str
    data: dict | None = None


ASSOC_KINDS = ("frame", "node", "poly", "area", "link")
ON_PLANE = "ON_PLANE"
INTERSECTING = "INTERSECTING"
WITHIN_DEPTH = "WITHIN_DEPTH"
OUTSIDE = "OUTSIDE"
ASSOC_STATUSES = (ON_PLANE, INTERSECTING, WITHIN_DEPTH, OUTSIDE)

_KIND_COLLECTION = {
    "node": "nodes", "frame": "frames", "poly": "polygons",
    "area": "areas", "link": "links",
}


def _as_vec3(value, name: str) -> np.ndarray:
    v = np.asarray(value, dtype=float)
    if v.shape != (3,) or not np.isfinite(v).all():
        raise ValueError(f"{name} 3 sonlu koordinat içermeli")
    return v


class Plane:
    __unit_schema__ = {
        "origin": Dimension.LENGTH,
        "u_min": Dimension.LENGTH, "u_max": Dimension.LENGTH,
        "v_min": Dimension.LENGTH, "v_max": Dimension.LENGTH,
        "depth_minus": Dimension.LENGTH, "depth_plus": Dimension.LENGTH,
    }

    def __init__(self, origin, normal, u=None, v=None, *,
                 plane_id=None, name="",
                 u_min=None, u_max=None, v_min=None, v_max=None,
                 depth_minus=0.0, depth_plus=0.0):
        origin = _as_vec3(origin, "origin")
        normal = _as_vec3(normal, "normal")
        n_len = np.linalg.norm(normal)
        if n_len < 1e-12:
            raise ValueError("Plane normal sıfır olamaz")
        self.normal = normal / n_len

        if u is None:
            presets = {
                0: np.array([0.0, 1.0, 0.0]),
                1: np.array([1.0, 0.0, 0.0]),
                2: np.array([1.0, 0.0, 0.0]),
            }
            u = presets[int(np.argmax(np.abs(self.normal)))]
        else:
            u = _as_vec3(u, "u ekseni")

        u = u - self.normal * float(np.dot(u, self.normal))
        u_len = np.linalg.norm(u)
        if u_len < 1e-12:
            raise ValueError("Plane u ekseni normale paralel olamaz")
        self.u = u / u_len

        if v is not None:
            v = _as_vec3(v, "v ekseni")
            v = v - self.normal * float(np.dot(v, self.normal))
            v = v - self.u * float(np.dot(v, self.u))
            v_len = np.linalg.norm(v)
            self.v = np.cross(self.normal, self.u) if v_len < 1e-12 else v / v_len
        else:
            self.v = np.cross(self.normal, self.u)
            self.v = self.v / np.linalg.norm(self.v)

        if all(x is not None for x in (u_min, u_max, v_min, v_max)):
            uc = 0.5 * (u_min + u_max)
            vc = 0.5 * (v_min + v_max)
            self.origin = origin + uc * self.u + vc * self.v
            self.u_min, self.u_max = u_min - uc, u_max - uc
            self.v_min, self.v_max = v_min - vc, v_max - vc
        else:
            self.origin = origin
            self.u_min, self.u_max = u_min, u_max
            self.v_min, self.v_max = v_min, v_max

        self.plane_id = plane_id or uuid.uuid4().hex
        self.name = name or f"Plane_{self.plane_id[:6]}"
        self.depth_minus = float(depth_minus)
        self.depth_plus = float(depth_plus)
        self.auto_assoc = True
        self.auto_assoc_ignore_bounds = False
        self.associated = {k: set() for k in ASSOC_KINDS}
        self.excluded = {k: set() for k in ASSOC_KINDS}
        self.association_status = {k: {} for k in ASSOC_KINDS}
        self._association_revision = 0
        self.pending = {}

    @property
    def x_axis(self): return self.u

    @property
    def y_axis(self): return self.v

    @property
    def boundary(self):
        return self.u_min, self.u_max, self.v_min, self.v_max

    @property
    def depth(self):
        return self.depth_minus, self.depth_plus

    # ---------------- CONSTRUCTORS ----------------

    @classmethod
    def from_point_normal(cls, p0, normal, **kw):
        return cls(np.asarray(p0, float), np.asarray(normal, float), **kw)

    @classmethod
    def from_3_points(cls, p0, p1, p2, **kw):
        p0, p1, p2 = (np.asarray(p, float) for p in (p0, p1, p2))
        u, v = p1 - p0, p2 - p0
        if np.linalg.norm(u) < 1e-12: raise ValueError("p1 == p0")
        if np.linalg.norm(v) < 1e-12: raise ValueError("p2 == p0")
        n = np.cross(u, v)
        if np.linalg.norm(n) < 1e-12: raise ValueError("noktalar collinear")
        return cls(p0, n, u=u, v=v, **kw)

    @classmethod
    def from_2_points_z_up(cls, p1, p2, up=(0.0, 0.0, 1.0), **kw):
        p1, p2, up = (np.asarray(p, float) for p in (p1, p2, up))
        u = p2 - p1
        if np.linalg.norm(u) < 1e-12: raise ValueError("p1 == p2")
        n = np.cross(u, up)
        if np.linalg.norm(n) < 1e-12: raise ValueError("u ile up paralel")
        return cls(p1, n, u=u, v=up, **kw)

    @classmethod
    def from_2_points(cls, p1, p2, orientation: str, **kw):
        p1, p2 = _as_vec3(p1, "p1"), _as_vec3(p2, "p2")
        delta = p2 - p1
        L = float(np.linalg.norm(delta))
        if L < 1e-12: raise ValueError("noktalar aynı")
        normals = {"XY": (0, 0, 1), "XZ": (0, 1, 0), "YZ": (1, 0, 0)}
        orientation = orientation.upper()
        if orientation not in normals: raise ValueError("orientation XY/XZ/YZ")
        normal = np.array(normals[orientation], float)
        if abs(float(np.dot(delta, normal))) > max(1e-9, L * 1e-9):
            raise ValueError(f"{orientation} düzlemine uymuyor")
        u = delta / L
        v = np.cross(normal, u)
        return cls(p1, normal, u=u, v=v, **kw)

    @classmethod
    def from_polygon(cls, poly, **kw):
        nodes = poly.nodes
        if len(nodes) < 3: raise ValueError("En az 3 node")
        pts = np.array([(n.x, n.y, n.z) for n in nodes], float)
        n = np.zeros(3)
        m = len(nodes)
        for i in range(m):
            a, b = pts[i], pts[(i + 1) % m]
            n += np.array(((a[1] - b[1]) * (a[2] + b[2]),
                           (a[2] - b[2]) * (a[0] + b[0]),
                           (a[0] - b[0]) * (a[1] + b[1])))
        n_len = float(np.linalg.norm(n))
        if n_len < 1e-12: raise ValueError("Poly dejenere")
        origin = pts[0]
        unit_n = n / n_len
        scale = max(float(np.linalg.norm(p - origin)) for p in pts)
        if any(abs(float(np.dot(p - origin, unit_n))) > max(1e-8, scale * 1e-9) for p in pts[1:]):
            raise ValueError("Poly düzlemsel değil")
        u = None
        for p in pts[1:]:
            c = p - origin
            c -= unit_n * float(np.dot(c, unit_n))
            if np.linalg.norm(c) > 1e-12:
                u = c / np.linalg.norm(c)
                break
        if u is None: raise ValueError("Poly dejenere")
        return cls(origin, n, u=u, **kw)

    @classmethod
    def from_axis_offset(cls, axis: str, offset: float,
                         u_min=None, u_max=None, v_min=None, v_max=None,
                         depth_minus=0.0, depth_plus=0.0, **kw):
        axis = axis.lower()
        normals = {"x": [1, 0, 0], "y": [0, 1, 0], "z": [0, 0, 1]}
        axes = {"x": ([0, 1, 0], [0, 0, 1]), "y": ([1, 0, 0], [0, 0, 1]), "z": ([1, 0, 0], [0, 1, 0])}
        if axis not in normals: raise ValueError("axis x/y/z")
        normal = np.array(normals[axis], float)
        u, v = (np.array(a, float) for a in axes[axis])
        return cls(normal * float(offset), normal, u=u, v=v,
                   u_min=u_min, u_max=u_max, v_min=v_min, v_max=v_max,
                   depth_minus=depth_minus, depth_plus=depth_plus, **kw)

    @classmethod
    def from_element(cls, element, *, frame_local_12: bool = False, **kw):
        from domain.element import Area, Frame
        from domain.polygon import Polygon
        if isinstance(element, Frame):
            if element.get_length() < 1e-12: raise ValueError("Frame uzunluğu sıfır")
            axes = element.get_local_axes()
            x_axis = _as_vec3(tuple(axes[0]), "frame local 1")
            in_plane = _as_vec3(tuple(axes[1] if frame_local_12 else axes[2]), "frame in-plane")
            normal = np.cross(x_axis, in_plane)
            return cls(_as_vec3(element.node_i.coords, "frame origin"),
                       normal, u=x_axis, v=in_plane, **kw)
        if isinstance(element, (Area, Polygon)):
            return cls.from_polygon(element, **kw)
        raise TypeError("Desteklenmiyor")

    @staticmethod
    def default_grid_plane_depth(unit_system=None) -> float:
        return float(convert_value(Dimension.LENGTH, 500.0, UnitSystem.N_MM, unit_system or UnitSystem.N_MM))

    # ---------------- GEOMETRİ ----------------

    def distance(self, pt) -> float:
        return float(np.dot(self.normal, _as_vec3(pt, "point") - self.origin))

    def distance_abs(self, pt) -> float:
        return abs(self.distance(pt))

    def project(self, pt) -> np.ndarray:
        pt = _as_vec3(pt, "point")
        return pt - self.normal * self.distance(pt)

    def to_2d(self, pt) -> tuple[float, float]:
        rel = _as_vec3(pt, "point") - self.origin
        return float(np.dot(rel, self.u)), float(np.dot(rel, self.v))

    def to_3d(self, uv) -> np.ndarray:
        c = np.asarray(uv, float)
        if c.shape != (2,): raise ValueError("uv (2,) olmalı")
        return self.origin + c[0] * self.u + c[1] * self.v

    def world_to_local(self, point) -> np.ndarray:
        r = _as_vec3(point, "point") - self.origin
        return np.array((np.dot(r, self.u), np.dot(r, self.v), np.dot(r, self.normal)))

    def local_to_world(self, coordinates) -> np.ndarray:
        l = _as_vec3(coordinates, "local")
        return self.origin + l[0] * self.u + l[1] * self.v + l[2] * self.normal

    def intersect_ray(self, origin, direction):
        o, d = _as_vec3(origin, "ray origin"), _as_vec3(direction, "ray direction")
        d_len = float(np.linalg.norm(d))
        if d_len < 1e-12: raise ValueError("yön sıfır")
        denom = float(np.dot(self.normal, d))
        if abs(denom) <= 1e-12 * d_len: return None
        t = float(np.dot(self.origin - o, self.normal) / denom)
        if t < -1e-12 / d_len: return None
        return o + max(t, 0.0) * d

    def bounds_contains_uv(self, u, v):
        return ((self.u_min is None or u >= self.u_min) and
                (self.u_max is None or u <= self.u_max) and
                (self.v_min is None or v >= self.v_min) and
                (self.v_max is None or v <= self.v_max))

    def band_contains_pt(self, pt):
        d = self.distance(pt)
        return -self.depth_minus <= d <= self.depth_plus

    def contains_pt(self, pt):
        return self.band_contains_pt(pt) and self.bounds_contains_uv(*self.to_2d(pt))

    def corners_3d(self):
        if None in (self.u_min, self.u_max, self.v_min, self.v_max): return []
        return [
            self.to_3d((self.u_min, self.v_min)), self.to_3d((self.u_max, self.v_min)),
            self.to_3d((self.u_max, self.v_max)), self.to_3d((self.u_min, self.v_max)),
        ]

    # ---------------- ASSOC ----------------

    def all_assoc_ids(self, kind):
        return self.associated.get(kind, set())

    @property
    def association_revision(self): return self._association_revision

    def add_assoc(self, kind, uid):
        uid = int(uid)
        if uid not in self.associated.setdefault(kind, set()) or uid in self.excluded.setdefault(kind, set()):
            self.associated[kind].add(uid)
            self.excluded[kind].discard(uid)
            self._association_revision += 1

    def remove_assoc(self, kind, uid, permanent=True):
        uid = int(uid)
        changed = uid in self.associated.setdefault(kind, set())
        self.associated[kind].discard(uid)
        if permanent:
            changed = changed or uid not in self.excluded.setdefault(kind, set())
            self.excluded[kind].add(uid)
        if changed:
            self._association_revision += 1

    def is_excluded(self, kind, uid):
        return int(uid) in self.excluded.get(kind, set())

    def association_of(self, kind, uid):
        return self.association_status.get(kind, {}).get(int(uid), OUTSIDE)

    def association_counts(self, kind=None):
        kinds = (kind,) if kind else ASSOC_KINDS
        counts = {s: 0 for s in ASSOC_STATUSES}
        for k in kinds:
            for s in self.association_status.get(k, {}).values():
                counts[s] += 1
        return counts

    def refresh_assoc(self, math_model, scene=None):
        if not self.auto_assoc:
            return
        for k in ASSOC_KINDS:
            self.associated[k] = set()
            self.association_status[k] = {}
        for kind, cname in _KIND_COLLECTION.items():
            if kind == "poly":
                source = getattr(scene, "polygons", {}) if scene else {}
            else:
                source = getattr(math_model, cname, {}) if math_model else {}
            for uid, el in source.items():
                status = self.classify_element(el, kind)
                self.association_status[kind][int(uid)] = status
                if status != OUTSIDE and not self.is_excluded(kind, uid):
                    self.associated[kind].add(int(uid))
        self._association_revision += 1

    def classify_element(self, el, kind):
        if kind not in ASSOC_KINDS: raise ValueError(f"bilinmeyen kind: {kind}")
        pts = self._element_points(el, kind)
        if not pts: return OUTSIDE
        pts = [_as_vec3(p, "element point") for p in pts]
        local = np.asarray([self.world_to_local(p) for p in pts], float)
        lower, upper = self._association_bounds()
        tol = self._association_tolerance(pts, local)
        if np.any(lower > upper): return OUTSIDE

        if kind == "node":
            p = local[0]
            if not self._point_in_box(p, lower, upper, tol): return OUTSIDE
            return ON_PLANE if abs(p[2]) <= tol else WITHIN_DEPTH

        if kind in ("frame", "link"):
            if len(local) != 2: return OUTSIDE
            a, b = local
            if not self._segment_intersects_box(a, b, lower, upper, tol): return OUTSIDE
            if max(abs(a[2]), abs(b[2])) <= tol: return ON_PLANE
            if self._segment_intersects_plane_bounds(a, b, lower[:2], upper[:2], tol): return INTERSECTING
            return WITHIN_DEPTH

        if len(local) < 3: return OUTSIDE
        tris = self._triangulate_surface(local)
        if not tris: return OUTSIDE
        if not any(self._polygon_intersects_box(t, lower, upper, tol) for t in tris): return OUTSIDE
        if np.max(np.abs(local[:, 2])) <= tol: return ON_PLANE
        if any(self._triangle_intersects_plane_bounds(t, lower[:2], upper[:2], tol) for t in tris): return INTERSECTING
        return WITHIN_DEPTH

    @staticmethod
    def _triangulate_surface(points):
        center = np.mean(points, axis=0)
        centered = points - center
        normal = np.zeros(3)
        for i, p in enumerate(centered):
            normal += np.cross(p, centered[(i + 1) % len(centered)])
        n_len = float(np.linalg.norm(normal))
        if n_len < 1e-12: return []
        normal /= n_len
        seed = np.eye(3)[int(np.argmin(np.abs(normal)))]
        u = seed - normal * float(np.dot(seed, normal))
        u /= np.linalg.norm(u)
        v = np.cross(normal, u)
        proj = np.column_stack((centered @ u, centered @ v))
        idx = earcut.triangulate_float64(np.ascontiguousarray(proj), np.array([len(proj)], np.uint32))
        return [points[np.asarray(idx[i:i + 3], int)] for i in range(0, len(idx), 3)]

    def _association_bounds(self):
        if self.auto_assoc_ignore_bounds:
            u_min, u_max = v_min, v_max = -np.inf, np.inf
        else:
            u_min = -np.inf if self.u_min is None else float(self.u_min)
            u_max = np.inf if self.u_max is None else float(self.u_max)
            v_min = -np.inf if self.v_min is None else float(self.v_min)
            v_max = np.inf if self.v_max is None else float(self.v_max)
        if self.depth_minus < 0 or self.depth_plus < 0:
            raise ValueError("depth negatif olamaz")
        return (np.array((u_min, v_min, -self.depth_minus)),
                np.array((u_max, v_max, self.depth_plus)))

    def _association_tolerance(self, world_pts, local_pts):
        scale = max(1.0, float(np.max(np.abs(local_pts))),
                    abs(self.depth_minus), abs(self.depth_plus))
        for b in (self.u_min, self.u_max, self.v_min, self.v_max):
            if b is not None: scale = max(scale, abs(float(b)))
        world = max(1.0, float(np.max(np.abs(self.origin))),
                    max(float(np.max(np.abs(p))) for p in world_pts))
        return max(scale * 1e-9, world * 32.0 * np.finfo(float).eps)

    @staticmethod
    def _point_in_box(p, lower, upper, tol):
        return bool(np.all(p >= lower - tol) and np.all(p <= upper + tol))

    @classmethod
    def _segment_intersects_box(cls, a, b, lower, upper, tol):
        s, e = 0.0, 1.0
        d = b - a
        for ax in range(3):
            if abs(d[ax]) <= tol:
                if a[ax] < lower[ax] - tol or a[ax] > upper[ax] + tol: return False
                continue
            t0 = (lower[ax] - a[ax]) / d[ax]
            t1 = (upper[ax] - a[ax]) / d[ax]
            s, e = max(s, min(t0, t1)), min(e, max(t0, t1))
            if s > e + tol: return False
        return True

    @classmethod
    def _segment_intersects_plane_bounds(cls, a, b, lower, upper, tol):
        cuts = [p[:2] for p in (a, b) if abs(p[2]) <= tol]
        if (a[2] < -tol and b[2] > tol) or (a[2] > tol and b[2] < -tol):
            r = a[2] / (a[2] - b[2])
            cuts.append(a[:2] + r * (b[:2] - a[:2]))
        for p in cuts:
            if cls._point_in_box(np.array((*p, 0.0)), np.array((*lower, 0.0)),
                                 np.array((*upper, 0.0)), tol): return True
        return any(cls._segment_intersects_box(
            np.array((*p, 0.0)), np.array((*q, 0.0)),
            np.array((*lower, 0.0)), np.array((*upper, 0.0)), tol)
            for i, p in enumerate(cuts) for q in cuts[i + 1:])

    @classmethod
    def _polygon_intersects_box(cls, poly, lower, upper, tol):
        pts = [p.copy() for p in poly]
        for ax in range(3):
            if np.isfinite(lower[ax]):
                pts = cls._clip(pts, ax, lower[ax], True, tol)
            if not pts: return False
            if np.isfinite(upper[ax]):
                pts = cls._clip(pts, ax, upper[ax], False, tol)
            if not pts: return False
        return True

    @staticmethod
    def _clip(poly, ax, bound, keep_above, tol):
        def inside(p): return p[ax] >= bound - tol if keep_above else p[ax] <= bound + tol
        out = []
        prev = poly[-1]
        prev_in = inside(prev)
        for cur in poly:
            cur_in = inside(cur)
            if cur_in != prev_in:
                denom = cur[ax] - prev[ax]
                if abs(denom) > 1e-15:
                    r = (bound - prev[ax]) / denom
                    out.append(prev + r * (cur - prev))
            if cur_in: out.append(cur)
            prev, prev_in = cur, cur_in
        return out

    @classmethod
    def _triangle_intersects_plane_bounds(cls, tri, lower, upper, tol):
        cuts = []
        for i in range(3):
            a, b = tri[i], tri[(i + 1) % 3]
            if abs(a[2]) <= tol: cuts.append(a[:2])
            if (a[2] < -tol and b[2] > tol) or (a[2] > tol and b[2] < -tol):
                r = a[2] / (a[2] - b[2])
                cuts.append(a[:2] + r * (b[:2] - a[:2]))
        uniq = []
        for p in cuts:
            if not any(np.linalg.norm(p - q) <= tol for q in uniq): uniq.append(p)
        if any(np.all(p >= lower - tol) and np.all(p <= upper + tol) for p in uniq): return True
        return any(cls._segment_intersects_plane_bounds(
            np.array((*a, 0.0)), np.array((*b, 0.0)), lower, upper, tol)
            for i, a in enumerate(uniq) for b in uniq[i + 1:])

    @staticmethod
    def _element_points(el, kind):
        if kind == "node":
            return [_as_vec3((el.x, el.y, el.z), "node")]
        if kind in ("frame", "link"):
            ni, nj = getattr(el, "node_i", None), getattr(el, "node_j", None)
            return [] if ni is None or nj is None else [
                _as_vec3(ni.coords, "frame node"), _as_vec3(nj.coords, "frame node")]
        if kind in ("poly", "area"):
            nodes = getattr(el, "nodes", [])
            return [] if len(nodes) < 3 else [_as_vec3(n.coords, "poly node") for n in nodes]
        return []

    # ---------------- PENDING ----------------

    def is_pending(self, kind, eid):
        return (kind, str(eid)) in self.pending

    def pending_of(self, kind, eid):
        return self.pending.get((kind, str(eid)))

    def add_pending(self, op, kind, eid, data=None):
        if op not in ChangeOp.ALL: raise ValueError(f"op geçersiz: {op}")
        key = (kind, str(eid))
        existing = self.pending.get(key)

        if existing is None:
            self.pending[key] = PendingChange(op, kind, str(eid), data)
        elif existing.op == ChangeOp.ADD:
            if op == ChangeOp.MODIFY:
                prev = existing.data or {}
                after = (data or {}).get("after", data) or {}
                existing.data = {**prev, **after}
            elif op == ChangeOp.DELETE:
                del self.pending[key]
            else:
                existing.data = data
        elif existing.op == ChangeOp.MODIFY:
            if op == ChangeOp.DELETE:
                existing.op = ChangeOp.DELETE
                existing.data = None
            elif op == ChangeOp.MODIFY:
                before = (existing.data or {}).get("before")
                existing.data = {"before": before, "after": (data or {}).get("after", data)}
        elif existing.op == ChangeOp.DELETE and op == ChangeOp.ADD:
            existing.op = ChangeOp.MODIFY
            existing.data = {"before": None, "after": data}

    def clear_pending(self):
        self.pending.clear()

    def apply_pending(self, math_model, project=None) -> dict:
        report = {"deleted": 0, "modified": 0, "added": 0, "draft_map": {}, "errors": []}
        scene = project.scene if project else None
        by_op = {op: [] for op in ChangeOp.APPLY_ORDER}
        for ch in self.pending.values():
            by_op[ch.op].append(ch)

        for ch in by_op[ChangeOp.DELETE]:
            uid = int(ch.id)
            if ch.kind == "poly":
                if scene is not None and scene.remove_polygon(uid):
                    report["deleted"] += 1
            else:
                el = getattr(math_model, _KIND_COLLECTION[ch.kind], {}).get(uid)
                if el is not None and math_model.remove_element(el):
                    report["deleted"] += 1
            self.associated.get(ch.kind, set()).discard(uid)
            self.excluded.get(ch.kind, set()).discard(uid)

        for ch in by_op[ChangeOp.MODIFY]:
            uid = int(ch.id)
            if ch.kind == "poly":
                el = scene.polygons.get(uid) if scene else None
            else:
                el = getattr(math_model, _KIND_COLLECTION[ch.kind], {}).get(uid)
            if el is None:
                continue
            for k, v in ((ch.data or {}).get("after") or {}).items():
                setattr(el, k, v)
            el.mark_dirty()
            report["modified"] += 1

        for ch in by_op[ChangeOp.ADD]:
            new_el = self._build_from_data(
                ch.kind, ch.data or {}, math_model, report["draft_map"], project,
            )
            if new_el is None:
                report["errors"].append(f"add {ch.kind}#{ch.id}")
                continue
            if ch.kind == "poly":
                if scene is None or not scene.add_polygon(new_el):
                    report["errors"].append(f"add poly#{ch.id}")
                    continue
            else:
                if not math_model.add_element(new_el):
                    report["errors"].append(f"add {ch.kind}#{ch.id}")
                    continue
            report["added"] += 1
            report["draft_map"][ch.id] = new_el.unique_id
            self.associated.setdefault(ch.kind, set()).add(new_el.unique_id)

        self.pending.clear()
        self.refresh_assoc(math_model, scene)
        return report

    def _build_from_data(self, kind, data, math_model, draft_map, project=None):
        builders = {"node": self._build_node, "frame": self._build_frame,
                    "poly": self._build_poly, "area": self._build_area,
                    "link": self._build_link}
        fn = builders.get(kind)
        return fn(data, math_model, draft_map, project) if fn else None

    @staticmethod
    def _resolve_node(ref, scene, draft_map):
        if hasattr(ref, "unique_id"): return ref
        if isinstance(ref, int): return scene.nodes.get(ref)
        s = str(ref)
        if s.startswith("draft:"): return scene.nodes.get(draft_map.get(s))
        if s.startswith("real:"): return scene.nodes.get(int(s[5:]))
        return scene.nodes.get(int(s))

    def _build_node(self, data, math_model, draft_map, project=None):
        from domain.definition import Restraint
        from domain.element import Node
        r = data.get("restraint")
        if isinstance(r, dict): r = Restraint(**r)
        return Node(float(data["x"]), float(data["y"]), float(data["z"]),
                    label=data.get("label", ""), restraint=r)

    def _build_frame(self, data, math_model, draft_map, project=None):
        from domain.element import Frame
        ni = self._resolve_node(data.get("node_i_ref"), math_model, draft_map)
        nj = self._resolve_node(data.get("node_j_ref"), math_model, draft_map)
        if ni is None or nj is None: raise ValueError("node çözülemedi")
        sec = data.get("section")
        if sec is None:
            sec = (
                project.get_section_by_name(data.get("section_name"))
                if project is not None else None
            )
        if sec is None: raise ValueError("section yok")
        return Frame(ni, nj, sec, rotation_deg=float(data.get("rotation_deg", 0.0)),
                     label=data.get("label", ""))

    def _build_poly(self, data, math_model, draft_map, project=None):
        from data.enums import PolygonType
        from domain.polygon import Polygon
        nodes = [self._resolve_node(r, math_model, draft_map) for r in (data.get("node_refs") or [])]
        nodes = [n for n in nodes if n is not None]
        if len(nodes) < 3: raise ValueError("min 3 node")
        pt = data.get("poly_type", PolygonType.GENERIC)
        if isinstance(pt, str): pt = getattr(PolygonType, pt, PolygonType.GENERIC)
        return Polygon(nodes, label=data.get("label", ""), poly_type=pt)

    def _build_area(self, data, math_model, draft_map, project=None):
        from domain.element import Area
        nodes = [self._resolve_node(r, math_model, draft_map) for r in (data.get("node_refs") or [])]
        nodes = [n for n in nodes if n is not None]
        if len(nodes) < 3: raise ValueError("min 3 node")
        return Area(nodes, thickness=float(data.get("thickness", 0.0)),
                    label=data.get("label", ""))

    def _build_link(self, data, math_model, draft_map, project=None):
        from domain.element import Link
        ni = self._resolve_node(data.get("node_i_ref"), math_model, draft_map)
        nj = self._resolve_node(data.get("node_j_ref"), math_model, draft_map)
        if ni is None or nj is None: raise ValueError("node çözülemedi")
        return Link(ni, nj, propname=data.get("propname", "LINK1"),
                    label=data.get("label", ""))

    def uv_basis(self):
        return self.u, self.v, self.normal

    def set_bounds(self, u_min, u_max, v_min, v_max, recenter=True):
        if u_min > u_max: u_min, u_max = u_max, u_min
        if v_min > v_max: v_min, v_max = v_max, v_min
        if recenter:
            uc, vc = 0.5 * (u_min + u_max), 0.5 * (v_min + v_max)
            if abs(uc) > 1e-12 or abs(vc) > 1e-12:
                self.origin = self.origin + uc * self.u + vc * self.v
                u_min -= uc; u_max -= uc
                v_min -= vc; v_max -= vc
        self.u_min, self.u_max = float(u_min), float(u_max)
        self.v_min, self.v_max = float(v_min), float(v_max)

    def fit_to_math_model(self, math_model, margin_ratio=0.05, min_margin=100.0):
        us, vs = [], []
        for nd in (math_model.nodes.values() if math_model else ()):
            u, v = self.to_2d((nd.x, nd.y, nd.z))
            us.append(u)
            vs.append(v)
        if not us:
            half = 5000.0
            self.u_min, self.u_max = -half, half
            self.v_min, self.v_max = -half, half
            return
        mu = max(margin_ratio * (max(us) - min(us)), min_margin)
        mv = max(margin_ratio * (max(vs) - min(vs)), min_margin)
        self.u_min, self.u_max = min(us) - mu, max(us) + mu
        self.v_min, self.v_max = min(vs) - mv, max(vs) + mv
        
    def __repr__(self):
        return (f"Plane(id={self.plane_id[:6]}, name={self.name!r}, "
                f"depth=[-{self.depth_minus},+{self.depth_plus}], "
                f"assoc={sum(len(s) for s in self.associated.values())}, "
                f"pending={len(self.pending)})")