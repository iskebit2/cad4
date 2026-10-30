# domain/plane.py
from __future__ import annotations

import uuid
from dataclasses import dataclass

import mapbox_earcut as earcut
import numpy as np

from core.units import Dimension, UnitSystem, convert_value


# ----------------------------------------------------------------------
#  Pending change tipleri
# ----------------------------------------------------------------------
class ChangeOp:
    ADD    = "add"
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
    "node": "nodes",
    "frame": "frames",
    "poly": "polygons",
    "area": "areas",
    "link": "links",
}


def _as_vec3(value, name: str) -> np.ndarray:
    vector = np.asarray(value, dtype=float)
    if vector.shape != (3,) or not np.isfinite(vector).all():
        raise ValueError(f"{name} 3 sonlu koordinat içermeli")
    return vector


# ----------------------------------------------------------------------
#  Plane — sadece davranış; serileştirme serializer'ın işi
# ----------------------------------------------------------------------
class Plane:
    """
    Sınırlı, derinlikli çalışma düzlemi.

    Geometri:
        origin  : düzlem merkezi (u/v orta noktası, sınır varsa)
        normal  : birim normal (depth_plus yönü)
        u, v    : düzlem içi ortonormal eksenler

    Sınır / derinlik:
        u_min/u_max/v_min/v_max : dikdörtgen sınır (None = sonsuz)
        depth_minus/depth_plus  : normal yönünde [-depth_minus, +depth_plus] bant

    Assoc:
        associated[kind] = set(unique_id int)  — bu plane'e bağlı scene elemanları
        excluded[kind]   = set(unique_id int)  — auto-assoc'un almadıkları
        association_status[kind][id]            — gerçek geometriden sınıflandırma

    Pending:
        pending[(kind, id_str)] = PendingChange
        op ∈ {ADD, MODIFY, DELETE}
    """

    # NOT: __slots__ kullanmıyoruz — serializer'ın __dict__ üzerinden
    # otomatik encode/decode yapabilmesi için.

    def __init__(self,
                origin: np.ndarray,
                normal: np.ndarray,
                u: np.ndarray | None = None,
                v: np.ndarray | None = None,          # ← YENİ
                *,
                plane_id: str | None = None,
                name: str = "",
                u_min: float | None = None,
                u_max: float | None = None,
                v_min: float | None = None,
                v_max: float | None = None,
                depth_minus: float = 0.0,
                depth_plus: float = 0.0):
        origin = _as_vec3(origin, "origin")
        normal = _as_vec3(normal, "normal")
        n_len = np.linalg.norm(normal)
        if n_len < 1e-12:
            raise ValueError("Plane normal sıfır olamaz")
        self.normal = normal / n_len

        # --- u ---
        if u is None:
            abs_n = np.abs(self.normal)
            min_axis = int(np.argmin(abs_n))
            seed = np.zeros(3)
            seed[min_axis] = 1.0
            u = np.cross(self.normal, seed)
            u_len = np.linalg.norm(u)
            if u_len < 1e-12:
                u = np.cross(self.normal, np.array([0.0, 1.0, 0.0]))
                u_len = np.linalg.norm(u)
        else:
            u = _as_vec3(u, "u ekseni")

        u = u - self.normal * float(np.dot(u, self.normal))
        u_len = np.linalg.norm(u)
        if u_len < 1e-12:
            raise ValueError("Plane u ekseni normale paralel olamaz")
        self.u = u / u_len

        # --- v ---  (YENİ: verilirse kullan, yoksa türet)
        if v is not None:
            v = _as_vec3(v, "v ekseni")
            v = v - self.normal * float(np.dot(v, self.normal))
            v = v - self.u * float(np.dot(v, self.u))
            v_len = np.linalg.norm(v)
            if v_len < 1e-12:
                self.v = np.cross(self.normal, self.u)
                self.v = self.v / np.linalg.norm(self.v)
            else:
                self.v = v / v_len
        else:
            self.v = np.cross(self.normal, self.u)
            self.v = self.v / np.linalg.norm(self.v)

        # origin: sınır varsa merkez
        if all(x is not None for x in (u_min, u_max, v_min, v_max)):
            uc = 0.5 * (u_min + u_max)
            vc = 0.5 * (v_min + v_max)
            self.origin = origin + uc * self.u + vc * self.v
        else:
            self.origin = origin

        self.plane_id = plane_id or uuid.uuid4().hex
        self.name = name or f"Plane_{self.plane_id[:6]}"

        self.u_min = u_min
        self.u_max = u_max
        self.v_min = v_min
        self.v_max = v_max

        self.depth_minus = float(depth_minus)
        self.depth_plus = float(depth_plus)

        self.auto_assoc = True
        self.auto_assoc_ignore_bounds = False

        self.associated: dict[str, set[int]] = {k: set() for k in ASSOC_KINDS}
        self.excluded: dict[str, set[int]] = {k: set() for k in ASSOC_KINDS}
        self.association_status: dict[str, dict[int, str]] = {
            k: {} for k in ASSOC_KINDS
        }
        self._association_revision = 0
        self.pending: dict[tuple[str, str], PendingChange] = {}
    
    @property
    def x_axis(self) -> np.ndarray:
        return self.u

    @property
    def y_axis(self) -> np.ndarray:
        return self.v

    @property
    def boundary(self) -> tuple[float | None, float | None,
                                float | None, float | None]:
        return self.u_min, self.u_max, self.v_min, self.v_max

    @property
    def depth(self) -> tuple[float, float]:
        return self.depth_minus, self.depth_plus

    # ---------------- CONSTRUCTORS ----------------

    @classmethod
    def from_point_normal(cls, p0, normal, **kw) -> Plane:
        return cls(np.asarray(p0, dtype=float), np.asarray(normal, dtype=float), **kw)

    @classmethod
    def from_3_points(cls, p0, p1, p2, **kw) -> Plane:
        """
        p0 = origin
        p1 - p0 = u yönü
        p2 - p0 = v yönü
        n = u × v
        """
        p0 = np.asarray(p0, dtype=float)
        p1 = np.asarray(p1, dtype=float)
        p2 = np.asarray(p2, dtype=float)

        u = p1 - p0
        v = p2 - p0
        if np.linalg.norm(u) < 1e-12:
            raise ValueError("p1 == p0")
        if np.linalg.norm(v) < 1e-12:
            raise ValueError("p2 == p0")

        n = np.cross(u, v)
        if np.linalg.norm(n) < 1e-12:
            raise ValueError("p0, p1, p2 collinear")

        return cls(p0, n, u=u, v=v, **kw)

    @classmethod
    def from_2_points_z_up(cls, p1, p2, up=(0.0, 0.0, 1.0), **kw) -> Plane:
        """
        p1 = origin
        p2 - p1 = u yönü
        global Z (up) = v yönü
        n = u × v
        """
        p1 = np.asarray(p1, dtype=float)
        p2 = np.asarray(p2, dtype=float)
        up = np.asarray(up, dtype=float)

        u = p2 - p1
        if np.linalg.norm(u) < 1e-12:
            raise ValueError("p1 == p2")

        v = up
        n = np.cross(u, v)
        if np.linalg.norm(n) < 1e-12:
            raise ValueError("p1-p2 yönü up'a paralel")

        return cls(p1, n, u=u, v=v, **kw)

    @classmethod
    def from_2_points(cls, p1, p2, orientation: str, **kw) -> Plane:
        """Create an axis-aligned plane containing both points."""
        p1 = _as_vec3(p1, "p1")
        p2 = _as_vec3(p2, "p2")
        delta = p2 - p1
        length = float(np.linalg.norm(delta))
        if length < 1e-12:
            raise ValueError("p1 and p2 must be distinct")

        orientation = orientation.upper()
        normals = {
            "XY": np.array((0.0, 0.0, 1.0)),
            "XZ": np.array((0.0, 1.0, 0.0)),
            "YZ": np.array((1.0, 0.0, 0.0)),
        }
        normal = normals.get(orientation)
        if normal is None:
            raise ValueError("orientation must be XY, XZ, or YZ")

        tolerance = max(1e-9, length * 1e-9)
        if abs(float(np.dot(delta, normal))) > tolerance:
            raise ValueError(
                f"Selected points are not compatible with the {orientation} plane"
            )

        u = delta / length
        v = np.cross(normal, u)
        return cls(p1, normal, u=u, v=v, **kw)

    @classmethod
    def from_polygon(cls, poly, **kw) -> Plane:
        nodes = poly.nodes
        if len(nodes) < 3:
            raise ValueError("Poly en az 3 node olmalı")
        points = np.array([
            _as_vec3((node.x, node.y, node.z), "polygon point")
            for node in nodes
        ])
        n = np.zeros(3, dtype=float)
        m = len(nodes)
        for i in range(m):
            a = points[i]
            b = points[(i + 1) % m]
            n += np.array((
                (a[1] - b[1]) * (a[2] + b[2]),
                (a[2] - b[2]) * (a[0] + b[0]),
                (a[0] - b[0]) * (a[1] + b[1]),
            ))
        normal_length = float(np.linalg.norm(n))
        if normal_length < 1e-12:
            raise ValueError("Poly dejenere")
        origin = points[0]
        unit_normal = n / normal_length
        scale = max(float(np.linalg.norm(point - origin)) for point in points)
        tolerance = max(1e-8, scale * 1e-9)
        if any(
            abs(float(np.dot(point - origin, unit_normal))) > tolerance
            for point in points[1:]
        ):
            raise ValueError("Poly düzlemsel değil")

        u = None
        for point in points[1:]:
            candidate = point - origin
            candidate -= unit_normal * float(np.dot(candidate, unit_normal))
            candidate_length = float(np.linalg.norm(candidate))
            if candidate_length > 1e-12:
                u = candidate / candidate_length
                break
        if u is None:
            raise ValueError("Poly dejenere")
        return cls(origin, n, u=u, **kw)

    @classmethod
    def from_element(cls, element, *, frame_local_12: bool = False, **kw) -> Plane:
        from domain.element import Area, Frame, Polygon

        if isinstance(element, Frame):
            if element.get_length() < 1e-12:
                raise ValueError("Frame length must be non-zero")
            axes = element.get_local_axes()
            x_axis = _as_vec3(tuple(axes[0]), "frame local 1 axis")
            in_plane_axis = _as_vec3(
                tuple(axes[1] if frame_local_12 else axes[2]),
                "frame local plane axis",
            )
            normal = np.cross(x_axis, in_plane_axis)
            return cls(
                _as_vec3(element.node_i.coords, "frame origin"),
                normal,
                u=x_axis,
                v=in_plane_axis,
                **kw,
            )
        if isinstance(element, (Area, Polygon)):
            return cls.from_polygon(element, **kw)
        raise TypeError("Plane source must be a Frame, Area, or Polygon")

    @staticmethod
    def grid_levels(grid, orientation: str) -> list[float]:
        """Return the project-grid coordinates that define planes of an orientation."""
        orientation = str(orientation).upper()
        level_axis = {"XY": "z", "XZ": "y", "YZ": "x"}.get(orientation)
        if level_axis is None:
            raise ValueError("Grid orientation must be XY, XZ, or YZ")
        values = np.asarray(getattr(grid, f"{level_axis}_coords", ()), dtype=float)
        if values.size == 0 or not np.isfinite(values).all():
            return []
        return sorted({float(value) for value in values})

    @staticmethod
    def default_grid_plane_depth(unit_system: UnitSystem | None) -> float:
        """Return 500 mm expressed in the project's current length unit."""
        return float(convert_value(
            Dimension.LENGTH,
            500.0,
            UnitSystem.N_MM,
            unit_system or UnitSystem.N_MM,
        ))

    @classmethod
    def from_grid(
        cls,
        grid,
        grid_plane: str,
        *,
        grid_coordinate: float | None = None,
        **kw,
    ) -> Plane:
        """Create a plane from project grid coordinates or a user grid definition."""
        requested = str(getattr(grid_plane, "name", grid_plane))
        grid_name = requested.upper()
        if grid is None:
            raise ValueError("Grid system is not available")

        if grid_name in ("XY", "XZ", "YZ"):
            coordinates = {
                axis: np.sort(np.unique(np.asarray(
                    getattr(grid, f"{axis.lower()}_coords", ()), dtype=float,
                )))
                for axis in "XYZ"
            }
            if any(
                values.size < 2 or not np.isfinite(values).all()
                for values in coordinates.values()
            ):
                raise ValueError("Grid plane needs at least two finite coordinates per axis")

            origin = np.array((
                float(grid.origin_x),
                float(grid.origin_y),
                float(grid.origin_z),
            ))
            x_coords = coordinates["X"]
            y_coords = coordinates["Y"]
            z_coords = coordinates["Z"]
            if grid_name == "XY":
                level = z_coords[0] if grid_coordinate is None else float(grid_coordinate)
                origin[2] += level
                u, v, normal = (1, 0, 0), (0, 1, 0), (0, 0, 1)
                bounds = (x_coords[0], x_coords[-1], y_coords[0], y_coords[-1])
            elif grid_name == "XZ":
                level = y_coords[0] if grid_coordinate is None else float(grid_coordinate)
                origin[1] += level
                u, v, normal = (1, 0, 0), (0, 0, 1), (0, -1, 0)
                bounds = (x_coords[0], x_coords[-1], z_coords[0], z_coords[-1])
            else:
                level = x_coords[0] if grid_coordinate is None else float(grid_coordinate)
                origin[0] += level
                u, v, normal = (0, 1, 0), (0, 0, 1), (1, 0, 0)
                bounds = (y_coords[0], y_coords[-1], z_coords[0], z_coords[-1])
            if not np.isfinite(level):
                raise ValueError("Grid plane coordinate must be finite")
        else:
            user_plane_name = (
                requested[len("user::"):]
                if requested.startswith("user::")
                else requested
            )
            get_user_plane = getattr(grid, "get_user_plane", None)
            grid_definition = (
                get_user_plane(user_plane_name) if callable(get_user_plane) else None
            )
            if grid_definition is None:
                grid_definition = next(
                    (
                        definition
                        for definition in getattr(grid, "user_planes", ())
                        if definition.name == user_plane_name
                    ),
                    None,
                )
            if grid_definition is None:
                raise ValueError(f"Grid plane not found: {requested}")

            origin, u, v, normal = grid_definition.get_uv_frame()
            origin = _as_vec3(tuple(origin), "grid plane origin")
            u = _as_vec3(tuple(u), "grid plane u axis")
            v = _as_vec3(tuple(v), "grid plane v axis")
            normal = _as_vec3(tuple(normal), "grid plane normal")
            half_u = float(grid_definition.spacing_u) * int(grid_definition.count_u)
            half_v = float(grid_definition.spacing_v) * int(grid_definition.count_v)
            if not np.isfinite((half_u, half_v)).all() or half_u <= 0 or half_v <= 0:
                raise ValueError("Grid plane spacing and count must be positive")
            bounds = (-half_u, half_u, -half_v, half_v)
            grid_name = user_plane_name

        plane = cls(
            origin,
            normal,
            u=u,
            v=v,
            name=kw.pop("name", f"Plane_Grid_{grid_name}"),
            **kw,
        )
        plane.u_min, plane.u_max, plane.v_min, plane.v_max = bounds
        return plane

    @classmethod
    def from_axis_offset(cls, axis: str, offset: float,
                         u_min=None, u_max=None, v_min=None, v_max=None,
                         depth_minus=0.0, depth_plus=0.0, **kw) -> Plane:
        axis = axis.lower()
        if axis not in ("x", "y", "z"):
            raise ValueError("axis x/y/z olmalı")
        normal = {"x": np.array([1.0, 0, 0]),
                  "y": np.array([0, 1.0, 0]),
                  "z": np.array([0, 0, 1.0])}[axis]
        origin = normal * float(offset)
        if axis == "y":
            u = np.array([1.0, 0, 0]); v = np.array([0, 0, 1.0])
        elif axis == "x":
            u = np.array([0, 1.0, 0]); v = np.array([0, 0, 1.0])
        else:  # z
            u = np.array([1.0, 0, 0]); v = np.array([0, 1.0, 0])
        return cls(origin, normal, u=u, v=v,          # ← v= eklendi
           u_min=u_min, u_max=u_max, v_min=v_min, v_max=v_max,
           depth_minus=depth_minus, depth_plus=depth_plus, **kw)
    
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

    def to_3d(self, uv: tuple[float, float]) -> np.ndarray:
        coordinates = np.asarray(uv, dtype=float)
        if coordinates.shape != (2,) or not np.isfinite(coordinates).all():
            raise ValueError("uv koordinatı iki sonlu değer içermeli")
        return self.origin + coordinates[0] * self.u + coordinates[1] * self.v

    def world_to_local(self, point) -> np.ndarray:
        """Return the point's (u, v, signed-normal-distance) coordinates."""
        relative = _as_vec3(point, "point") - self.origin
        return np.array((
            np.dot(relative, self.u),
            np.dot(relative, self.v),
            np.dot(relative, self.normal),
        ), dtype=float)

    def local_to_world(self, coordinates) -> np.ndarray:
        """Convert (u, v, signed-normal-distance) coordinates to world space."""
        local = _as_vec3(coordinates, "local coordinates")
        return (
            self.origin
            + local[0] * self.u
            + local[1] * self.v
            + local[2] * self.normal
        )

    def contains(self, point) -> bool:
        return self.contains_pt(point)

    def intersect_ray(self, ray_origin, ray_direction) -> np.ndarray | None:
        """Return the forward ray/plane hit, or None for a parallel or backward ray."""
        origin = _as_vec3(ray_origin, "ray origin")
        direction = _as_vec3(ray_direction, "ray direction")
        direction_length = float(np.linalg.norm(direction))
        if direction_length < 1e-12:
            raise ValueError("Ray direction sıfır olamaz")

        denominator = float(np.dot(self.normal, direction))
        if abs(denominator) <= 1e-12 * direction_length:
            return None

        distance = float(np.dot(self.origin - origin, self.normal) / denominator)
        if distance < -1e-12 / direction_length:
            return None
        return origin + max(distance, 0.0) * direction

    # ---------------- SINIR / DERİNLİK ----------------

    def bounds_contains_uv(self, u: float, v: float) -> bool:
        if self.u_min is not None and u < self.u_min: return False
        if self.u_max is not None and u > self.u_max: return False
        if self.v_min is not None and v < self.v_min: return False
        if self.v_max is not None and v > self.v_max: return False
        return True

    def band_contains_pt(self, pt) -> bool:
        d = self.distance(pt)
        return -self.depth_minus <= d <= self.depth_plus

    def contains_pt(self, pt) -> bool:
        if not self.band_contains_pt(pt):
            return False
        u, v = self.to_2d(pt)
        return self.bounds_contains_uv(u, v)

    def corners_3d(self) -> list[np.ndarray]:
        if None in (self.u_min, self.u_max, self.v_min, self.v_max):
            return []
        return [
            self.to_3d((self.u_min, self.v_min)),
            self.to_3d((self.u_max, self.v_min)),
            self.to_3d((self.u_max, self.v_max)),
            self.to_3d((self.u_min, self.v_max)),
        ]

    # ---------------- ASSOC ----------------

    def all_assoc_ids(self, kind: str) -> set[int]:
        return self.associated.get(kind, set())

    @property
    def association_revision(self) -> int:
        return self._association_revision

    def add_assoc(self, kind: str, unique_id: int):
        uid = int(unique_id)
        associated = self.associated.setdefault(kind, set())
        excluded = self.excluded.setdefault(kind, set())
        if uid not in associated or uid in excluded:
            associated.add(uid)
            excluded.discard(uid)
            self._association_revision += 1

    def remove_assoc(self, kind: str, unique_id: int, permanent=True):
        uid = int(unique_id)
        associated = self.associated.setdefault(kind, set())
        excluded = self.excluded.setdefault(kind, set())
        changed = uid in associated
        associated.discard(uid)
        if permanent:
            changed = changed or uid not in excluded
            excluded.add(uid)
        if changed:
            self._association_revision += 1

    def is_excluded(self, kind: str, unique_id: int) -> bool:
        return int(unique_id) in self.excluded.get(kind, set())

    def association_of(self, kind: str, unique_id: int) -> str:
        return self.association_status.get(kind, {}).get(int(unique_id), OUTSIDE)

    def association_counts(self, kind: str | None = None) -> dict[str, int]:
        kinds = (kind,) if kind is not None else ASSOC_KINDS
        counts = {status: 0 for status in ASSOC_STATUSES}
        for item_kind in kinds:
            for status in self.association_status.get(item_kind, {}).values():
                counts[status] += 1
        return counts

    def refresh_assoc(self, scene):
        if not self.auto_assoc:
            return
        for kind in ASSOC_KINDS:
            self.associated[kind] = set()
            self.association_status[kind] = {}
        self._scan_scene(scene)
        self._association_revision += 1

    def _scan_scene(self, scene):
        for kind, cname in (("node", "nodes"), ("frame", "frames"),
                            ("poly", "polygons"), ("area", "areas"),
                            ("link", "links")):
            coll = getattr(scene, cname, {}) or {}
            for uid, el in coll.items():
                status = self.classify_element(el, kind)
                self.association_status[kind][int(uid)] = status
                if status != OUTSIDE and not self.is_excluded(kind, uid):
                    self.associated[kind].add(uid)

    def _element_in_plane(self, el, kind: str) -> bool:
        uid = getattr(el, "unique_id", None)
        if uid is None or self.is_excluded(kind, uid):
            return False
        return self.classify_element(el, kind) != OUTSIDE

    def classify_element(self, el, kind: str) -> str:
        """Classify an element using its full geometry against the bounded plane."""
        if kind not in ASSOC_KINDS:
            raise ValueError(f"Unknown association kind: {kind}")

        world_points = self._element_points(el, kind)
        if not world_points:
            return OUTSIDE
        world_points = [_as_vec3(point, "element point") for point in world_points]
        local_points = np.asarray(
            [self.world_to_local(point) for point in world_points],
            dtype=float,
        )
        lower, upper = self._association_bounds()
        tolerance = self._association_tolerance(world_points, local_points)
        if np.any(lower > upper):
            return OUTSIDE

        if kind == "node":
            point = local_points[0]
            if not self._point_in_box(point, lower, upper, tolerance):
                return OUTSIDE
            return ON_PLANE if abs(point[2]) <= tolerance else WITHIN_DEPTH

        if kind in ("frame", "link"):
            if len(local_points) != 2:
                return OUTSIDE
            first, second = local_points
            if not self._segment_intersects_box(
                first, second, lower, upper, tolerance
            ):
                return OUTSIDE
            if max(abs(first[2]), abs(second[2])) <= tolerance:
                return ON_PLANE
            if self._segment_intersects_plane_bounds(
                first, second, lower[:2], upper[:2], tolerance
            ):
                return INTERSECTING
            return WITHIN_DEPTH

        if len(local_points) < 3:
            return OUTSIDE

        triangles = self._triangulate_surface(local_points)
        if not triangles:
            return OUTSIDE
        if not any(
            self._polygon_intersects_box(triangle, lower, upper, tolerance)
            for triangle in triangles
        ):
            return OUTSIDE
        if np.max(np.abs(local_points[:, 2])) <= tolerance:
            return ON_PLANE
        if any(
            self._triangle_intersects_plane_bounds(
                triangle, lower[:2], upper[:2], tolerance
            )
            for triangle in triangles
        ):
            return INTERSECTING
        return WITHIN_DEPTH

    @staticmethod
    def _triangulate_surface(points: np.ndarray) -> list[np.ndarray]:
        center = np.mean(points, axis=0)
        centered = points - center
        normal = np.zeros(3, dtype=float)
        for index, point in enumerate(centered):
            normal += np.cross(point, centered[(index + 1) % len(centered)])
        normal_length = float(np.linalg.norm(normal))
        if normal_length < 1e-12:
            return []
        normal /= normal_length

        seed = np.eye(3)[int(np.argmin(np.abs(normal)))]
        u_axis = seed - normal * float(np.dot(seed, normal))
        u_axis /= np.linalg.norm(u_axis)
        v_axis = np.cross(normal, u_axis)
        projected = np.column_stack((centered @ u_axis, centered @ v_axis))
        indices = earcut.triangulate_float64(
            np.ascontiguousarray(projected, dtype=np.float64),
            np.asarray((len(projected),), dtype=np.uint32),
        )
        return [
            points[np.asarray(indices[index:index + 3], dtype=int)]
            for index in range(0, len(indices), 3)
        ]

    def _association_bounds(self) -> tuple[np.ndarray, np.ndarray]:
        if self.auto_assoc_ignore_bounds:
            u_min, u_max = -np.inf, np.inf
            v_min, v_max = -np.inf, np.inf
        else:
            raw_bounds = (self.u_min, self.u_max, self.v_min, self.v_max)
            for value in raw_bounds:
                if value is not None and not np.isfinite(float(value)):
                    raise ValueError("Plane association boundary must be finite")
            u_min = -np.inf if self.u_min is None else float(self.u_min)
            u_max = np.inf if self.u_max is None else float(self.u_max)
            v_min = -np.inf if self.v_min is None else float(self.v_min)
            v_max = np.inf if self.v_max is None else float(self.v_max)
        depth_minus = float(self.depth_minus)
        depth_plus = float(self.depth_plus)
        if (
            not np.isfinite((depth_minus, depth_plus)).all()
            or depth_minus < 0.0
            or depth_plus < 0.0
        ):
            raise ValueError("Plane association depths must be finite and non-negative")
        bounds = np.asarray(
            ((u_min, u_max), (v_min, v_max), (-depth_minus, depth_plus)),
            dtype=float,
        )
        return bounds[:, 0], bounds[:, 1]

    def _association_tolerance(
        self,
        world_points: list[np.ndarray],
        local_points: np.ndarray,
    ) -> float:
        scale = max(
            1.0,
            float(np.max(np.abs(local_points))),
            abs(self.depth_minus),
            abs(self.depth_plus),
        )
        for bound in (self.u_min, self.u_max, self.v_min, self.v_max):
            if bound is not None:
                scale = max(scale, abs(float(bound)))
        world_scale = max(
            1.0,
            float(np.max(np.abs(self.origin))),
            max(float(np.max(np.abs(point))) for point in world_points),
        )
        return max(
            scale * 1e-9,
            world_scale * 32.0 * np.finfo(float).eps,
        )

    @staticmethod
    def _point_in_box(
        point: np.ndarray,
        lower: np.ndarray,
        upper: np.ndarray,
        tolerance: float,
    ) -> bool:
        return bool(
            np.all(point >= lower - tolerance)
            and np.all(point <= upper + tolerance)
        )

    @classmethod
    def _segment_intersects_box(
        cls,
        first: np.ndarray,
        second: np.ndarray,
        lower: np.ndarray,
        upper: np.ndarray,
        tolerance: float,
    ) -> bool:
        start, end = 0.0, 1.0
        delta = second - first
        for axis in range(3):
            if abs(delta[axis]) <= tolerance:
                if (
                    first[axis] < lower[axis] - tolerance
                    or first[axis] > upper[axis] + tolerance
                ):
                    return False
                continue
            t0 = (lower[axis] - first[axis]) / delta[axis]
            t1 = (upper[axis] - first[axis]) / delta[axis]
            start = max(start, min(t0, t1))
            end = min(end, max(t0, t1))
            if start > end + tolerance:
                return False
        return True

    @classmethod
    def _segment_intersects_plane_bounds(
        cls,
        first: np.ndarray,
        second: np.ndarray,
        lower: np.ndarray,
        upper: np.ndarray,
        tolerance: float,
    ) -> bool:
        cut_points = []
        for point in (first, second):
            if abs(point[2]) <= tolerance:
                cut_points.append(point[:2])
        if (first[2] < -tolerance and second[2] > tolerance) or (
            first[2] > tolerance and second[2] < -tolerance
        ):
            ratio = first[2] / (first[2] - second[2])
            cut_points.append(first[:2] + ratio * (second[:2] - first[:2]))
        if any(
            cls._point_in_box(
                np.asarray((point[0], point[1], 0.0)),
                np.asarray((lower[0], lower[1], 0.0)),
                np.asarray((upper[0], upper[1], 0.0)),
                tolerance,
            )
            for point in cut_points
        ):
            return True
        return any(
            cls._segment_intersects_box(
                np.asarray((*start, 0.0)),
                np.asarray((*end, 0.0)),
                np.asarray((lower[0], lower[1], 0.0)),
                np.asarray((upper[0], upper[1], 0.0)),
                tolerance,
            )
            for index, start in enumerate(cut_points)
            for end in cut_points[index + 1:]
        )

    @classmethod
    def _polygon_intersects_box(
        cls,
        polygon: np.ndarray,
        lower: np.ndarray,
        upper: np.ndarray,
        tolerance: float,
    ) -> bool:
        clipped = [point.copy() for point in polygon]
        for axis in range(3):
            if np.isfinite(lower[axis]):
                clipped = cls._clip_polygon(
                    clipped, axis, lower[axis], keep_above=True, tolerance=tolerance
                )
            if not clipped:
                return False
            if np.isfinite(upper[axis]):
                clipped = cls._clip_polygon(
                    clipped, axis, upper[axis], keep_above=False, tolerance=tolerance
                )
            if not clipped:
                return False
        return bool(clipped)

    @staticmethod
    def _clip_polygon(
        polygon: list[np.ndarray],
        axis: int,
        bound: float,
        *,
        keep_above: bool,
        tolerance: float,
    ) -> list[np.ndarray]:
        if not polygon:
            return []

        def inside(point):
            if keep_above:
                return point[axis] >= bound - tolerance
            return point[axis] <= bound + tolerance

        result = []
        previous = polygon[-1]
        previous_inside = inside(previous)
        for current in polygon:
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

    @classmethod
    def _triangle_intersects_plane_bounds(
        cls,
        triangle: np.ndarray,
        lower: np.ndarray,
        upper: np.ndarray,
        tolerance: float,
    ) -> bool:
        cut_points = []
        for index in range(3):
            first = triangle[index]
            second = triangle[(index + 1) % 3]
            if abs(first[2]) <= tolerance:
                cut_points.append(first[:2])
            if (first[2] < -tolerance and second[2] > tolerance) or (
                first[2] > tolerance and second[2] < -tolerance
            ):
                ratio = first[2] / (first[2] - second[2])
                cut_points.append(first[:2] + ratio * (second[:2] - first[:2]))

        unique_points = []
        for point in cut_points:
            if not any(
                np.linalg.norm(point - existing) <= tolerance
                for existing in unique_points
            ):
                unique_points.append(point)
        if any(
            np.all(point >= lower - tolerance)
            and np.all(point <= upper + tolerance)
            for point in unique_points
        ):
            return True
        return any(
            cls._segment_intersects_plane_bounds(
                np.asarray((*first, 0.0)),
                np.asarray((*second, 0.0)),
                lower,
                upper,
                tolerance,
            )
            for index, first in enumerate(unique_points)
            for second in unique_points[index + 1:]
        )

    @staticmethod
    def _element_points(el, kind: str) -> list[np.ndarray]:
        if kind == "node":
            return [_as_vec3((el.x, el.y, el.z), "node coordinates")]
        if kind in ("frame", "link"):
            ni = getattr(el, "node_i", None)
            nj = getattr(el, "node_j", None)
            if ni is None or nj is None:
                return []
            return [
                _as_vec3((ni.x, ni.y, ni.z), "element node coordinates"),
                _as_vec3((nj.x, nj.y, nj.z), "element node coordinates"),
            ]
        if kind in ("poly", "area"):
            nodes = getattr(el, "nodes", [])
            if len(nodes) < 3:
                return []
            return [
                _as_vec3((node.x, node.y, node.z), "element node coordinates")
                for node in nodes
            ]
        return []

    # ---------------- PENDING ----------------

    def is_pending(self, kind: str, eid) -> bool:
        return (kind, str(eid)) in self.pending

    def pending_of(self, kind: str, eid) -> PendingChange | None:
        return self.pending.get((kind, str(eid)))

    def add_pending(self, op: str, kind: str, eid, data: dict | None = None):
        if op not in ChangeOp.ALL:
            raise ValueError(f"Geçersiz op: {op}")
        key = (kind, str(eid))
        existing = self.pending.get(key)

        if existing is None:
            self.pending[key] = PendingChange(op=op, kind=kind, id=str(eid), data=data)
            return

        if existing.op == ChangeOp.ADD:
            if op == ChangeOp.MODIFY:
                prev = existing.data or {}
                after = (data or {}).get("after", data)
                existing.data = {**prev, **(after or {})}
                return
            if op == ChangeOp.DELETE:
                del self.pending[key]
                return
            existing.data = data
            return

        if existing.op == ChangeOp.MODIFY:
            if op == ChangeOp.DELETE:
                existing.op = ChangeOp.DELETE
                existing.data = None
                return
            if op == ChangeOp.MODIFY:
                before = (existing.data or {}).get("before")
                after = (data or {}).get("after", data)
                existing.data = {"before": before, "after": after}
                return

        if existing.op == ChangeOp.DELETE:
            if op == ChangeOp.ADD:
                existing.op = ChangeOp.MODIFY
                existing.data = {"before": None, "after": data}
            return

    def clear_pending(self):
        self.pending.clear()

    def apply_pending(self, scene) -> dict:
        report = {"deleted": 0, "modified": 0, "added": 0,
                  "draft_map": {}, "errors": []}

        by_op: dict[str, list] = {op: [] for op in ChangeOp.APPLY_ORDER}
        for ch in self.pending.values():
            by_op[ch.op].append(ch)

        # 1) DELETE
        for ch in by_op[ChangeOp.DELETE]:
            try:
                uid = int(ch.id)
            except ValueError:
                continue
            coll = getattr(scene, _KIND_COLLECTION[ch.kind], {})
            el = coll.get(uid)
            if el is not None:
                if scene.remove_element(el):
                    report["deleted"] += 1
                else:
                    report["errors"].append(
                        f"delete {ch.kind}#{uid}: bağlı eleman var"
                    )
            self.associated.get(ch.kind, set()).discard(uid)
            self.excluded.get(ch.kind, set()).discard(uid)

        # 2) MODIFY
        for ch in by_op[ChangeOp.MODIFY]:
            try:
                uid = int(ch.id)
            except ValueError:
                continue
            coll = getattr(scene, _KIND_COLLECTION[ch.kind], {})
            el = coll.get(uid)
            if el is None:
                continue
            after = (ch.data or {}).get("after") or {}
            for k, v in after.items():
                try:
                    setattr(el, k, v)
                except Exception as e:
                    report["errors"].append(f"modify {ch.kind}#{uid}.{k}: {e}")
            el.mark_dirty()
            if not self._element_in_plane(el, ch.kind):
                self.associated.get(ch.kind, set()).discard(uid)
            report["modified"] += 1

        # 3) ADD
        for ch in by_op[ChangeOp.ADD]:
            try:
                new_el = self._build_from_data(ch.kind, ch.data or {},
                                               scene, report["draft_map"])
            except Exception as e:
                report["errors"].append(f"add {ch.kind}#{ch.id}: {e}")
                continue
            if new_el is None:
                continue
            if not scene.add_element(new_el):
                report["errors"].append(f"add {ch.kind}#{ch.id}: add_element reddetti")
                continue
            real_uid = new_el.unique_id
            report["added"] += 1
            report["draft_map"][ch.id] = real_uid
            self.associated.setdefault(ch.kind, set()).add(real_uid)

        self.pending.clear()
        self.refresh_assoc(scene)
        return report

    # ---------------- ADD builders ----------------

    def _build_from_data(self, kind, data, scene, draft_map):
        if kind == "node":  return self._build_node(data)
        if kind == "frame": return self._build_frame(data, scene, draft_map)
        if kind == "poly":  return self._build_poly(data, scene, draft_map)
        if kind == "area":  return self._build_area(data, scene, draft_map)
        if kind == "link":  return self._build_link(data, scene, draft_map)
        return None

    @staticmethod
    def _resolve_node(ref, scene, draft_map):
        if hasattr(ref, "unique_id"):
            return ref
        if isinstance(ref, int):
            return scene.nodes.get(ref)
        s = str(ref)
        if s.startswith("draft:"):
            real = draft_map.get(s)
            return scene.nodes.get(real) if real is not None else None
        if s.startswith("real:"):
            try:
                return scene.nodes.get(int(s[5:]))
            except ValueError:
                return None
        try:
            return scene.nodes.get(int(s))
        except ValueError:
            return None

    def _build_node(self, data: dict):
        from domain.definition import Restraint
        from domain.element import Node
        r = data.get("restraint")
        if isinstance(r, dict):
            r = Restraint(**r)
        return Node(
            x=float(data["x"]), y=float(data["y"]), z=float(data["z"]),
            label=data.get("label", ""), restraint=r,
            mass=tuple(data.get("mass", (0.0,) * 6)),
        )

    def _build_frame(self, data, scene, draft_map):
        from domain.element import Frame
        ni = self._resolve_node(data.get("node_i_ref"), scene, draft_map)
        nj = self._resolve_node(data.get("node_j_ref"), scene, draft_map)
        if ni is None or nj is None:
            raise ValueError("Frame node_i/node_j çözülemedi")
        sec = data.get("section")
        if sec is None:
            project = getattr(scene, "project", None)
            sec_name = data.get("section_name")
            if project and sec_name:
                sec = project.get_section_by_name(sec_name)
        if sec is None:
            raise ValueError("Frame section bulunamadı")
        return Frame(ni, nj, sec,
                     rotation_deg=float(data.get("rotation_deg", 0.0)),
                     label=data.get("label", ""))

    def _build_poly(self, data, scene, draft_map):
        from data.enums import PolygonType
        from domain.element import Polygon
        nodes = [self._resolve_node(r, scene, draft_map)
                 for r in (data.get("node_refs") or [])]
        nodes = [n for n in nodes if n is not None]
        if len(nodes) < 3:
            raise ValueError("Poly en az 3 node istiyor")
        pt = data.get("poly_type", PolygonType.GENERIC)
        if isinstance(pt, str):
            pt = getattr(PolygonType, pt, PolygonType.GENERIC)
        return Polygon(nodes, label=data.get("label", ""), poly_type=pt)

    def _build_area(self, data, scene, draft_map):
        from domain.element import Area
        nodes = [self._resolve_node(r, scene, draft_map)
                 for r in (data.get("node_refs") or [])]
        nodes = [n for n in nodes if n is not None]
        if len(nodes) < 3:
            raise ValueError("Area en az 3 node istiyor")
        return Area(nodes, thickness=float(data.get("thickness", 0.0)),
                    label=data.get("label", ""))

    def _build_link(self, data, scene, draft_map):
        from domain.element import Link
        ni = self._resolve_node(data.get("node_i_ref"), scene, draft_map)
        nj = self._resolve_node(data.get("node_j_ref"), scene, draft_map)
        if ni is None or nj is None:
            raise ValueError("Link node_i/node_j çözülemedi")
        return Link(ni, nj, propname=data.get("propname", "LINK1"),
                    label=data.get("label", ""))

    def uv_basis(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Düzlemin (u, v, normal) ortonormal baz vektörleri.

        `to_2d()` ile birebir tutarlıdır:  to_2d(p) == (dot(p-origin, u), dot(p-origin, v))
        """
        return self.u, self.v, self.normal

    def set_bounds(self, u_min, u_max, v_min, v_max, recenter: bool = True):
        """u/v sınırlarını ata.

        recenter=True ise origin'i u/v merkezine kaydırır (Plane.__init__
        ile aynı davranış, sonradan sınır atamada da tutarlı olsun diye).
        """
        if u_min > u_max:
            u_min, u_max = u_max, u_min
        if v_min > v_max:
            v_min, v_max = v_max, v_min

        if recenter:
            uc = 0.5 * (u_min + u_max)
            vc = 0.5 * (v_min + v_max)
            if abs(uc) > 1e-12 or abs(vc) > 1e-12:
                self.origin = self.origin + uc * self.u + vc * self.v
                u_min -= uc; u_max -= uc
                v_min -= vc; v_max -= vc

        self.u_min = float(u_min)
        self.u_max = float(u_max)
        self.v_min = float(v_min)
        self.v_max = float(v_max)
        
    # ---------------- DEBUG ----------------

    def __repr__(self):
        return (f"Plane(id={self.plane_id[:6]}, name={self.name!r}, "
                f"depth=[-{self.depth_minus},+{self.depth_plus}], "
                f"assoc={sum(len(s) for s in self.associated.values())}, "
                f"pending={len(self.pending)})")