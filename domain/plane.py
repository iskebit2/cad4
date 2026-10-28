# domain/plane.py
from __future__ import annotations

import uuid
from dataclasses import dataclass

import numpy as np


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

_KIND_COLLECTION = {
    "node": "nodes",
    "frame": "frames",
    "poly": "polygons",
    "area": "areas",
    "link": "links",
}


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
        origin = np.asarray(origin, dtype=float)
        normal = np.asarray(normal, dtype=float)
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
            u = u / u_len

        u = np.asarray(u, dtype=float)
        self.u = u / np.linalg.norm(u)

        # --- v ---  (YENİ: verilirse kullan, yoksa türet)
        if v is not None:
            v = np.asarray(v, dtype=float)
            # u'ya dik hale getir, sonra normalize
            v = v - self.u * float(np.dot(v, self.u))
            v_len = np.linalg.norm(v)
            if v_len < 1e-12:
                # Dejenere → türet
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
        self.pending: dict[tuple[str, str], PendingChange] = {}

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
    def from_polygon(cls, poly, **kw) -> Plane:
        nodes = poly.nodes
        if len(nodes) < 3:
            raise ValueError("Poly en az 3 node olmalı")
        n = np.zeros(3)
        m = len(nodes)
        for i in range(m):
            a = nodes[i]
            b = nodes[(i + 1) % m]
            n[0] += (a.y - b.y) * (a.z + b.z)
            n[1] += (a.z - b.z) * (a.x + b.x)
            n[2] += (a.x - b.x) * (a.y + b.y)
        if np.linalg.norm(n) < 1e-12:
            raise ValueError("Poly dejenere")
        origin = np.array([nodes[0].x, nodes[0].y, nodes[0].z])
        v0 = np.array([nodes[1].x - nodes[0].x,
                       nodes[1].y - nodes[0].y,
                       nodes[1].z - nodes[0].z])
        u_len = np.linalg.norm(v0)
        u = v0 / u_len if u_len > 1e-12 else None
        return cls(origin, n, u=u, **kw)

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
        return float(np.dot(self.normal, np.asarray(pt, dtype=float) - self.origin))

    def distance_abs(self, pt) -> float:
        return abs(self.distance(pt))

    def project(self, pt) -> np.ndarray:
        pt = np.asarray(pt, dtype=float)
        return pt - self.normal * self.distance(pt)

    def to_2d(self, pt) -> tuple[float, float]:
        rel = np.asarray(pt, dtype=float) - self.origin
        return float(np.dot(rel, self.u)), float(np.dot(rel, self.v))

    def to_3d(self, uv: tuple[float, float]) -> np.ndarray:
        return self.origin + uv[0] * self.u + uv[1] * self.v

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

    def add_assoc(self, kind: str, unique_id: int):
        self.associated.setdefault(kind, set()).add(int(unique_id))
        self.excluded.get(kind, set()).discard(int(unique_id))

    def remove_assoc(self, kind: str, unique_id: int, permanent=True):
        self.associated.get(kind, set()).discard(int(unique_id))
        if permanent:
            self.excluded.setdefault(kind, set()).add(int(unique_id))

    def is_excluded(self, kind: str, unique_id: int) -> bool:
        return int(unique_id) in self.excluded.get(kind, set())

    def refresh_assoc(self, scene):
        if not self.auto_assoc:
            return
        for kind in ASSOC_KINDS:
            self.associated[kind] = set()
        self._scan_scene(scene)

    def _scan_scene(self, scene):
        for kind, cname in (("node", "nodes"), ("frame", "frames"),
                            ("poly", "polygons"), ("area", "areas"),
                            ("link", "links")):
            coll = getattr(scene, cname, {}) or {}
            for uid, el in coll.items():
                if self._element_in_plane(el, kind):
                    self.associated[kind].add(uid)

    def _element_in_plane(self, el, kind: str) -> bool:
        uid = getattr(el, "unique_id", None)
        if uid is None or self.is_excluded(kind, uid):
            return False
        pts = self._element_points(el, kind)
        if not pts:
            return False
        if self.auto_assoc_ignore_bounds:
            return all(self.band_contains_pt(p) for p in pts)
        return all(self.contains_pt(p) for p in pts)

    @staticmethod
    def _element_points(el, kind: str) -> list[np.ndarray]:
        if kind == "node":
            return [np.array([el.x, el.y, el.z], dtype=float)]
        if kind in ("frame", "link"):
            ni = getattr(el, "node_i", None)
            nj = getattr(el, "node_j", None)
            out = []
            if ni is not None and hasattr(ni, "x"):
                out.append(np.array([ni.x, ni.y, ni.z], dtype=float))
            if nj is not None and hasattr(nj, "x"):
                out.append(np.array([nj.x, nj.y, nj.z], dtype=float))
            return out
        if kind in ("poly", "area"):
            return [np.array([nd.x, nd.y, nd.z], dtype=float)
                    for nd in getattr(el, "nodes", [])]
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

    # ---------------- DEBUG ----------------

    def __repr__(self):
        return (f"Plane(id={self.plane_id[:6]}, name={self.name!r}, "
                f"depth=[-{self.depth_minus},+{self.depth_plus}], "
                f"assoc={sum(len(s) for s in self.associated.values())}, "
                f"pending={len(self.pending)})")