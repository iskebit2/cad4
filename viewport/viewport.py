from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import numpy as np
from OpenGL.GL import (
    GL_COLOR_ATTACHMENT1,
    GL_READ_FRAMEBUFFER,
    GL_RED_INTEGER,
    GL_UNSIGNED_INT,
    glBindFramebuffer,
    glReadBuffer,
    glReadPixels,
)

from core.camera import Camera
from render.offscreen_fbo import OffscreenFBO
from tools.filter_query import ElementFilterQuery, ModelFilterEngine


class VolumeClipMode(str, Enum):
    INTERSECT = "intersect"
    STRICT = "strict"
    CLIP = "clip"


@dataclass(frozen=True)
class ViewUCS:
    origin: np.ndarray
    u: np.ndarray
    v: np.ndarray
    normal: np.ndarray

    @classmethod
    def global_xy(cls, z: float = 0.0) -> ViewUCS:
        return cls(
            origin=np.array([0.0, 0.0, float(z)], dtype=float),
            u=np.array([1.0, 0.0, 0.0], dtype=float),
            v=np.array([0.0, 1.0, 0.0], dtype=float),
            normal=np.array([0.0, 0.0, 1.0], dtype=float),
        )

    @classmethod
    def from_axes(cls, origin, u, v) -> ViewUCS:
        o = np.asarray(origin, dtype=float)
        u_vec = np.asarray(u, dtype=float)
        u_vec = u_vec / np.linalg.norm(u_vec)
        v_raw = np.asarray(v, dtype=float)
        n_vec = np.cross(u_vec, v_raw)
        n_vec = n_vec / np.linalg.norm(n_vec)
        v_vec = np.cross(n_vec, u_vec)
        return cls(origin=o, u=u_vec, v=v_vec, normal=n_vec)

    @classmethod
    def from_3_points(cls, p0, p1, p2) -> ViewUCS:
        o = np.asarray(p0, dtype=float)
        u = np.asarray(p1, dtype=float) - o
        v = np.asarray(p2, dtype=float) - o
        return cls.from_axes(o, u, v)

    @classmethod
    def from_2_points_z_up(cls, p0, p1) -> ViewUCS:
        o = np.asarray(p0, dtype=float)
        u = np.asarray(p1, dtype=float) - o
        z_up = np.array([0.0, 0.0, 1.0], dtype=float)
        return cls.from_axes(o, u, z_up)

    def world_to_local(self, point) -> np.ndarray:
        d = np.asarray(point, dtype=float) - self.origin
        return np.array([
            float(np.dot(d, self.u)),
            float(np.dot(d, self.v)),
            float(np.dot(d, self.normal)),
        ], dtype=float)

    def local_to_world(self, uvw) -> np.ndarray:
        u_val, v_val, w_val = float(uvw[0]), float(uvw[1]), float(uvw[2])
        return self.origin + u_val * self.u + v_val * self.v + w_val * self.normal

    def matrix_4x4(self) -> np.ndarray:
        m = np.eye(4, dtype=float)
        m[:3, 0] = self.u
        m[:3, 1] = self.v
        m[:3, 2] = self.normal
        m[:3, 3] = self.origin
        return m


@dataclass
class ViewVolume:
    u_min: float | None = None
    u_max: float | None = None
    v_min: float | None = None
    v_max: float | None = None
    depth_minus: float | None = None
    depth_plus: float | None = None
    mode: VolumeClipMode = VolumeClipMode.STRICT

    @property
    def is_unbounded(self) -> bool:
        return (
            self.u_min is None
            and self.u_max is None
            and self.v_min is None
            and self.v_max is None
            and self.depth_minus is None
            and self.depth_plus is None
        )

    def set_bounds(
        self,
        u_min: float | None,
        u_max: float | None,
        v_min: float | None,
        v_max: float | None,
        depth_minus: float | None = None,
        depth_plus: float | None = None,
    ) -> None:
        if u_min is not None and u_max is not None and u_min > u_max:
            u_min, u_max = u_max, u_min
        if v_min is not None and v_max is not None and v_min > v_max:
            v_min, v_max = v_max, v_min
        self.u_min = None if u_min is None else float(u_min)
        self.u_max = None if u_max is None else float(u_max)
        self.v_min = None if v_min is None else float(v_min)
        self.v_max = None if v_max is None else float(v_max)
        self.depth_minus = None if depth_minus is None else abs(float(depth_minus))
        self.depth_plus = None if depth_plus is None else abs(float(depth_plus))

    def set_depth(self, depth_minus: float | None, depth_plus: float | None) -> None:
        self.depth_minus = None if depth_minus is None else abs(float(depth_minus))
        self.depth_plus = None if depth_plus is None else abs(float(depth_plus))

    def clear(self) -> None:
        self.u_min = None
        self.u_max = None
        self.v_min = None
        self.v_max = None
        self.depth_minus = None
        self.depth_plus = None

    def bounds_min_max(self) -> tuple[np.ndarray, np.ndarray]:
        lo = np.array([
            -np.inf if self.u_min is None else self.u_min,
            -np.inf if self.v_min is None else self.v_min,
            -np.inf if self.depth_minus is None else -self.depth_minus,
        ], dtype=float)
        hi = np.array([
            np.inf if self.u_max is None else self.u_max,
            np.inf if self.v_max is None else self.v_max,
            np.inf if self.depth_plus is None else self.depth_plus,
        ], dtype=float)
        return lo, hi

    def contains_local_point(self, uvw: np.ndarray, tol: float = 1e-6) -> bool:
        lo, hi = self.bounds_min_max()
        return bool(np.all(uvw >= lo - tol) and np.all(uvw <= hi + tol))

    def intersects_local_segment(self, p0: np.ndarray, p1: np.ndarray, tol: float = 1e-6) -> bool:
        lo, hi = self.bounds_min_max()
        t0, t1 = 0.0, 1.0
        d = p1 - p0
        for i in range(3):
            if abs(d[i]) < 1e-12:
                if p0[i] < lo[i] - tol or p0[i] > hi[i] + tol:
                    return False
            else:
                inv = 1.0 / d[i]
                t_near = (lo[i] - tol - p0[i]) * inv
                t_far = (hi[i] + tol - p0[i]) * inv
                if t_near > t_far:
                    t_near, t_far = t_far, t_near
                t0 = max(t0, t_near)
                t1 = min(t1, t_far)
                if t0 > t1:
                    return False
        return True

    def center_local(self) -> np.ndarray:
        uc = 0.0 if (self.u_min is None or self.u_max is None) else 0.5 * (self.u_min + self.u_max)
        vc = 0.0 if (self.v_min is None or self.v_max is None) else 0.5 * (self.v_min + self.v_max)
        w_lo = 0.0 if self.depth_minus is None else -self.depth_minus
        w_hi = 0.0 if self.depth_plus is None else self.depth_plus
        wc = 0.5 * (w_lo + w_hi)
        return np.array([uc, vc, wc], dtype=float)

    def radius(self) -> float | None:
        spans = []
        if self.u_min is not None and self.u_max is not None:
            spans.append(abs(self.u_max - self.u_min))
        if self.v_min is not None and self.v_max is not None:
            spans.append(abs(self.v_max - self.v_min))
        if not spans:
            return None
        return max(max(spans) * 0.5, 100.0)


class Viewport:
    def __init__(
        self,
        name: str,
        width: int = 640,
        height: int = 480,
        camera: Camera | None = None,
        ucs: ViewUCS | None = None,
        volume: ViewVolume | None = None,
        element_filter: ElementFilterQuery | None = None,
        is_2d: bool = False,
    ) -> None:
        self.name = name
        self.width = max(1, int(width))
        self.height = max(1, int(height))
        self.camera = camera if camera is not None else Camera()
        self.camera.set_aspect(self.width, self.height)
        self.fbo = OffscreenFBO(self.width, self.height, with_id=True)
        self.visible = True

        self.ucs: ViewUCS = ucs if ucs is not None else ViewUCS.global_xy(0.0)
        self.volume: ViewVolume = volume if volume is not None else ViewVolume()
        self.element_filter: ElementFilterQuery | None = element_filter
        self.is_2d: bool = bool(is_2d)

        self.visible_ids: set[int] | None = None
        self._dirty: bool = True

    def set_ucs(self, ucs: ViewUCS, refocus: bool = True) -> None:
        self.ucs = ucs
        self.invalidate()
        if refocus:
            self.focus_on_volume()

    def set_volume(
        self,
        u_min: float | None = None,
        u_max: float | None = None,
        v_min: float | None = None,
        v_max: float | None = None,
        depth_minus: float | None = None,
        depth_plus: float | None = None,
        mode: VolumeClipMode | None = None,
        refocus: bool = False,
    ) -> None:
        self.volume.set_bounds(u_min, u_max, v_min, v_max, depth_minus, depth_plus)
        if mode is not None:
            self.volume.mode = mode
        self.invalidate()
        if refocus:
            self.focus_on_volume()

    def set_depth(self, depth_minus: float | None, depth_plus: float | None, refocus: bool = False) -> None:
        self.volume.set_depth(depth_minus, depth_plus)
        self.invalidate()
        if refocus:
            self.focus_on_volume()

    def set_clip_mode(self, mode: VolumeClipMode) -> None:
        self.volume.mode = mode
        self.invalidate()

    def clear_volume(self) -> None:
        self.volume.clear()
        self.invalidate()

    def fit_volume_to_model(self, math_model, margin_ratio: float = 0.05, min_margin: float = 100.0, include_depth: bool = True) -> None:
        nodes = list(math_model.nodes.values()) if math_model is not None else []
        if not nodes:
            self.volume.clear()
            self.invalidate()
            return
        pts = np.array([self.ucs.world_to_local((n.x, n.y, n.z)) for n in nodes], dtype=float)
        mins = pts.min(axis=0)
        maxs = pts.max(axis=0)
        spans = maxs - mins
        margins = np.maximum(spans * margin_ratio, min_margin)
        d_minus = max(0.0, -(mins[2] - margins[2])) if include_depth else self.volume.depth_minus
        d_plus = max(0.0, maxs[2] + margins[2]) if include_depth else self.volume.depth_plus
        self.volume.set_bounds(
            mins[0] - margins[0],
            maxs[0] + margins[0],
            mins[1] - margins[1],
            maxs[1] + margins[1],
            depth_minus=d_minus,
            depth_plus=d_plus,
        )
        self.invalidate()

    def set_element_filter(self, query: ElementFilterQuery | None) -> None:
        self.element_filter = query
        self.invalidate()

    def set_2d_mode(self, enabled: bool, refocus: bool = True) -> None:
        self.is_2d = bool(enabled)
        if refocus:
            self.focus_on_volume()

    def focus_on_volume(self, fallback_center=None, fallback_radius: float = 2000.0) -> None:
        if self.volume.is_unbounded and fallback_center is not None:
            center = np.asarray(fallback_center, dtype=float)
        else:
            center = self.ucs.local_to_world(self.volume.center_local())
        r = self.volume.radius()
        fit_radius = (r * 1.25) if r is not None else float(fallback_radius)
        if self.is_2d:
            self.camera.look_at_plane(
                origin=center,
                u=self.ucs.u,
                v=self.ucs.v,
                n=self.ucs.normal,
                fit_radius=fit_radius,
            )
        else:
            self.camera.look_at_plane_iso(
                origin=center,
                u=self.ucs.u,
                v=self.ucs.v,
                n=self.ucs.normal,
                fit_radius=fit_radius,
            )

    def invalidate(self) -> None:
        self._dirty = True

    def rebuild_visible_ids(self, math_model) -> set[int] | None:
        if not self._dirty:
            return self.visible_ids

        if math_model is None:
            self.visible_ids = None
            self._dirty = False
            return None

        has_volume = not self.volume.is_unbounded and self.volume.mode != VolumeClipMode.CLIP
        has_filter = self.element_filter is not None and not self.element_filter.is_empty()

        if not has_volume and not has_filter:
            self.visible_ids = None
            self._dirty = False
            return None

        vol_ids: set[int] | None = None
        if has_volume:
            vol_ids = self._compute_volume_ids(math_model)

        flt_ids: set[int] | None = None
        if has_filter:
            flt_ids = set(ModelFilterEngine.filter_to_ids(math_model, self.element_filter))

        if vol_ids is not None and flt_ids is not None:
            self.visible_ids = vol_ids & flt_ids
        elif vol_ids is not None:
            self.visible_ids = vol_ids
        else:
            self.visible_ids = flt_ids

        self._dirty = False
        return self.visible_ids

    def _compute_volume_ids(self, math_model) -> set[int]:
        ids: set[int] = set()
        strict = self.volume.mode == VolumeClipMode.STRICT
        node_local: dict[int, np.ndarray] = {}

        for nd in math_model.nodes.values():
            loc = self.ucs.world_to_local((nd.x, nd.y, nd.z))
            node_local[nd.unique_id] = loc
            if self.volume.contains_local_point(loc):
                ids.add(nd.unique_id)

        for fr in math_model.frames.values():
            p0 = node_local.get(fr.node_i.unique_id)
            p1 = node_local.get(fr.node_j.unique_id)
            if p0 is None or p1 is None:
                continue
            ok = (
                (self.volume.contains_local_point(p0) and self.volume.contains_local_point(p1))
                if strict
                else self.volume.intersects_local_segment(p0, p1)
            )
            if ok:
                ids.add(fr.unique_id)

        for lk in getattr(math_model, "links", {}).values():
            p0 = node_local.get(lk.node_i.unique_id)
            p1 = node_local.get(lk.node_j.unique_id)
            if p0 is None or p1 is None:
                continue
            ok = (
                (self.volume.contains_local_point(p0) and self.volume.contains_local_point(p1))
                if strict
                else self.volume.intersects_local_segment(p0, p1)
            )
            if ok:
                ids.add(lk.unique_id)

        for ar in getattr(math_model, "areas", {}).values():
            pts = [node_local[n.unique_id] for n in getattr(ar, "nodes", ()) if n.unique_id in node_local]
            if not pts:
                continue
            checks = [self.volume.contains_local_point(p) for p in pts]
            ok = all(checks) if strict else any(checks)
            if ok:
                ids.add(ar.unique_id)

        return ids

    def resize(self, w: int, h: int) -> None:
        w, h = max(1, int(w)), max(1, int(h))
        if (w, h) == (self.width, self.height):
            return
        self.width, self.height = w, h
        self.camera.set_aspect(w, h)
        self.fbo.resize(w, h)

    def bind(self) -> None:
        self.fbo.bind()

    def unbind(self) -> None:
        self.fbo.unbind()

    def texture_id(self) -> int:
        return self.fbo.texture_id()
    
    def pick_at_neighborhood(self, pick_pass, x_px: int, y_px: int, radius: int = 3):
        """Merkez piksel etrafındaki en yakın elementi döndür."""
        if pick_pass is None or self.fbo.id_tex is None:
            return None
        xa = max(0, int(x_px) - radius)
        ya = max(0, int(y_px) - radius)
        xb = min(self.width - 1, int(x_px) + radius)
        yb = min(self.height - 1, int(y_px) + radius)
        ids = pick_pass.pick_rect(
            xa, ya, xb, yb, self.fbo.fbo, (self.width, self.height),
        )
        if not ids:
            return None
        # Merkeze en yakın ID — basit yaklaşım: ilk bulunan
        # (daha iyi: her ID'nin piksel mesafesi hesaplanabilir, ama pick_rect
        #  unique ID'ler döndürüyor, konum bilgisi yok)
        for pid in ids:
            el = pick_pass.get_element(pid)
            if el is not None:
                return el
        return None
    
    def pick_at(self, pick_pass, x_px: int, y_px: int):
        if pick_pass is None or self.fbo.id_tex is None:
            return None
        x = int(x_px)
        y = self.height - 1 - int(y_px)
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return None
        glBindFramebuffer(GL_READ_FRAMEBUFFER, self.fbo.fbo)
        glReadBuffer(GL_COLOR_ATTACHMENT1)
        buf = np.zeros((1, 1), dtype=np.uint32)
        glReadPixels(x, y, 1, 1, GL_RED_INTEGER, GL_UNSIGNED_INT, buf)
        glBindFramebuffer(GL_READ_FRAMEBUFFER, 0)
        pid = int(buf[0, 0])
        if pid <= 0:
            return None
        return pick_pass.get_element(pid)

    def pick_rect(self, pick_pass, x0, y0, x1, y1) -> list:
        if pick_pass is None or self.fbo.id_tex is None:
            return []
        ids = pick_pass.pick_rect(
            x0, y0, x1, y1, self.fbo.fbo, (self.width, self.height),
        )
        result = []
        for pid in ids:
            el = pick_pass.get_element(pid)
            if el is not None:
                result.append(el)
        return result

    def cleanup(self) -> None:
        if self.fbo is not None:
            self.fbo.cleanup()
            self.fbo = None