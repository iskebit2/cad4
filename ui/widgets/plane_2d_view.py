# ui/widgets/plane_2d_view.py
"""
Plane2DView — Plane üzerindeki assoc elemanları 2D canvas'ta gösterir.

- Koordinat sistemi: plane.to_2d / plane.to_3d
- View rotasyonu (orthogonal, sadece görüntü)
- Pan / zoom
- Seçim (node / frame / poly / area / link)
- Pending ADD draft'ları sarı kesikli (henüz çizim araçları yok, sadece görsel)

Model verisine YAZMAZ.
"""

from __future__ import annotations

import math
from typing import Optional, List, Tuple, Set, Dict

import imgui
import numpy as np

from domain.plane import Plane, ChangeOp


def _rot(v, deg):
    r = math.radians(deg)
    cs, sn = math.cos(r), math.sin(r)
    return (v[0] * cs - v[1] * sn, v[0] * sn + v[1] * cs)


class Plane2DView:

    # --- Renkler (ABGR) ---
    COL_BG          = 0xFF1A1A1A
    COL_GRID        = 0xFF2A2A2A
    COL_GRID_MAJOR  = 0xFF3A3A3A
    COL_AXIS_U      = 0xFF4040C0   # U ekseni kırmızımsı
    COL_AXIS_V      = 0xFF40C040   # V ekseni yeşilimsi

    # Assoc eleman renkleri
    COL_FRAME       = 0xFFB0B0B0
    COL_FRAME_SEL   = 0xFF60D0FF
    COL_FRAME_HOVER = 0xFFFFD060
    COL_NODE        = 0xFFE0E0E0
    COL_NODE_SEL    = 0xFF60D0FF
    COL_NODE_HOVER  = 0xFFFFD060
    COL_POLY_FILL   = 0x308080C0
    COL_POLY_EDGE   = 0xFFA0A0C0
    COL_AREA_FILL   = 0x3060C060
    COL_AREA_EDGE   = 0xFF80C080
    COL_LINK        = 0xFFC080A0

    # Excluded / pending
    COL_EXCLUDED    = 0x50808080   # soluk gri
    COL_PENDING_ADD = 0xFFFFD060   # sarı

    # Rubber
    COL_RUBBER      = 0x60FFD060

    # Sabitler
    HIT_RADIUS_PX   = 10.0
    MIN_ZOOM        = 0.02
    MAX_ZOOM        = 80.0
    ZOOM_STEP       = 1.15

    def __init__(self):
        self.plane: Optional[Plane] = None
        self.scene = None

        # View
        self.zoom = 1.0
        self.pan = (0.0, 0.0)          # dünya uzayında merkez ofseti (u, v)
        self.view_rotation = 0.0       # 0/90/180/270
        self.show_grid = True
        self.show_axes = True

        # Etkileşim
        self.selected = set()          # {(kind, id)} — kind: "frame"/"node"/...
        self.hover = None              # (kind, id) veya None
        self.clicked = None            # (kind, id) veya None (panel tüketir)
        self.clicked_empty = False

        self._mods_getter = None    # () -> (ctrl: bool, shift: bool)

        # Pan / rubber
        self._panning = False
        self._pan_anchor = None
        self._rubber = False
        self._rubber_start = None
        self._rubber_end = None

        # İçerik bounds cache (u/v)
        self._bounds = None
        self._first_load = True

    def _get_mods(self):
        if self._mods_getter:
            try:
                return self._mods_getter()
            except Exception:
                pass
        io = imgui.get_io()
        return bool(getattr(io, "key_ctrl", False)), bool(getattr(io, "key_shift", False))

    # ------------------------------------------------------------------
    #  Yükleme
    # ------------------------------------------------------------------
    def load_plane(self, plane: Plane, scene):
        self.plane = plane
        self.scene = scene
        self._bounds = self._compute_bounds()
        if self._first_load and self._bounds:
            self.fit_to_content()
            self._first_load = False

    def refresh(self):
        if self.plane is not None:
            self._bounds = self._compute_bounds()

    # ------------------------------------------------------------------
    #  View API
    # ------------------------------------------------------------------
    def rotate_view(self, delta_deg: float, absolute=False):
        if absolute:
            self.view_rotation = float(delta_deg)
        else:
            self.view_rotation += float(delta_deg)
        self.view_rotation = round(self.view_rotation / 90.0) * 90.0
        self.view_rotation %= 360.0

    def zoom_at_center(self, factor: float):
        self.zoom = max(self.MIN_ZOOM, min(self.zoom * factor, self.MAX_ZOOM))

    def fit_to_content(self, view_w=800.0, view_h=500.0, margin=0.85):
        b = self._bounds
        if not b:
            return
        umin, umax, vmin, vmax = b
        w = max(1e-6, umax - umin)
        h = max(1e-6, vmax - vmin)
        self.zoom = max(self.MIN_ZOOM,
                        min(margin * min(view_w / w, view_h / h), self.MAX_ZOOM))
        uc = 0.5 * (umin + umax)
        vc = 0.5 * (vmin + vmax)
        self.pan = (-uc, -vc)

    def reset_view(self):
        self.view_rotation = 0.0
        self.pan = (0.0, 0.0)
        self.fit_to_content()

    # ------------------------------------------------------------------
    #  Bounds (u/v)
    # ------------------------------------------------------------------
    def _compute_bounds(self):
        if self.plane is None or self.scene is None:
            return None

        us, vs = [], []
        for kind, eid in self._iter_assoc_ids():
            for uv in self._element_uvs(kind, eid):
                us.append(uv[0])
                vs.append(uv[1])

        if not us:
            # Assoc boş → plane sınırından fit
            if self.plane.u_min is not None:
                return (self.plane.u_min, self.plane.u_max,
                        self.plane.v_min, self.plane.v_max)
            return None
        return (min(us), max(us), min(vs), max(vs))

    # ------------------------------------------------------------------
    #  Assoc erişimciler
    # ------------------------------------------------------------------
    def _iter_assoc_ids(self):
        """(kind, id) — assoc'takiler (excluded değil)."""
        p = self.plane
        if p is None:
            return
        for kind in ("frame", "node", "poly", "area", "link"):
            for eid in p.associated.get(kind, set()):
                yield (kind, eid)

    def _iter_excluded_ids(self):
        p = self.plane
        if p is None:
            return
        for kind in ("frame", "node", "poly", "area", "link"):
            for eid in p.excluded.get(kind, set()):
                yield (kind, eid)

    def _iter_pending_add_ids(self):
        """(kind, id, data) — pending ADD draft'ları."""
        p = self.plane
        if p is None:
            return
        for (kind, eid), ch in p.pending.items():
            if ch.op == ChangeOp.ADD:
                yield (kind, ch.id, ch.data or {})

    def _element_uvs(self, kind: str, eid) -> List[Tuple[float, float]]:
        """Bir elemanın 2D noktaları (assoc veya excluded)."""
        if self.plane is None or self.scene is None:
            return []
        coll_name = {"frame": "frames", "node": "nodes", "poly": "polygons",
                     "area": "areas", "link": "links"}.get(kind)
        if coll_name is None:
            return []
        coll = getattr(self.scene, coll_name, {}) or {}
        el = coll.get(eid)
        if el is None:
            return []
        pts = self._points_3d_of(el, kind)
        return [self.plane.to_2d(p) for p in pts]

    @staticmethod
    def _points_3d_of(el, kind: str) -> List[np.ndarray]:
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

    # ------------------------------------------------------------------
    #  Dönüşüm
    # ------------------------------------------------------------------
    def _factory(self, cx, cy, cw, ch):
        rot = self.view_rotation
        zoom = self.zoom
        pan = self.pan
        hw = cw * 0.5
        hh = ch * 0.5

        def to_screen(u, v):
            ur, vr = _rot((u, v), rot)
            sx = cx + hw + (ur + pan[0]) * zoom
            sy = cy + hh - (vr + pan[1]) * zoom
            return sx, sy

        def from_screen(sx, sy):
            du = (sx - cx - hw) / zoom - pan[0]
            dv = -(sy - cy - hh) / zoom - pan[1]
            return _rot((du, dv), -rot)

        return to_screen, from_screen

    # ------------------------------------------------------------------
    #  Draw
    # ------------------------------------------------------------------
    def draw(self, imgui_ctx, draw_list, canvas_pos, canvas_size):
        cx, cy = canvas_pos
        cw, ch = canvas_size
        if cw <= 2 or ch <= 2:
            return

        dl = draw_list
        dl.add_rect_filled(cx, cy, cx + cw, cy + ch, self.COL_BG)

        to_screen, from_screen = self._factory(cx, cy, cw, ch)

        # Grid
        if self.show_grid:
            self._draw_grid(dl, cx, cy, cw, ch, to_screen, from_screen)

        # Eksenler
        if self.show_axes:
            self._draw_axes(dl, to_screen)

        # --- Assoc elemanlar ---
        for kind, eid in self._iter_assoc_ids():
            self._draw_element(dl, kind, eid, to_screen, mode="assoc")

        # --- Excluded (soluk) ---
        for kind, eid in self._iter_excluded_ids():
            self._draw_element(dl, kind, eid, to_screen, mode="excluded")

        # --- Pending ADD draft'ları (sarı kesikli) ---
        for kind, eid, data in self._iter_pending_add_ids():
            self._draw_draft(dl, kind, eid, data, to_screen)

        # --- Rubber ---
        if self._rubber and self._rubber_start and self._rubber_end:
            x0, y0 = self._rubber_start
            x1, y1 = self._rubber_end
            rx0, rx1 = min(x0, x1), max(x0, x1)
            ry0, ry1 = min(y0, y1), max(y0, y1)
            dl.add_rect_filled(rx0, ry0, rx1, ry1, self.COL_RUBBER)
            dl.add_rect(rx0, ry0, rx1, ry1, 0xFFFFD060)

        # --- Input ---
        self._handle_input(imgui_ctx, cx, cy, cw, ch, to_screen, from_screen)

    # ------------------------------------------------------------------
    def _draw_grid(self, dl, cx, cy, cw, ch, to_screen, from_screen):
        # Görünür u/v aralığı
        corners = [
            from_screen(cx, cy),
            from_screen(cx + cw, cy),
            from_screen(cx + cw, cy + ch),
            from_screen(cx, cy + ch),
        ]
        us = [c[0] for c in corners]
        vs = [c[1] for c in corners]
        umin, umax = min(us), max(us)
        vmin, vmax = min(vs), max(vs)

        # Güzel step
        target_px = 40.0
        world_step = target_px / max(self.zoom, 1e-6)
        exp = math.floor(math.log10(max(world_step, 1e-9)))
        base = 10 ** exp
        for m in (1, 2, 5, 10):
            if base * m >= world_step:
                world_step = base * m
                break

        # Dikey çizgiler (u sabit)
        u = math.floor(umin / world_step) * world_step
        while u <= umax:
            sx0, sy0 = to_screen(u, vmin)
            sx1, sy1 = to_screen(u, vmax)
            major = abs((u / (world_step * 5)) - round(u / (world_step * 5))) < 1e-6
            dl.add_line(sx0, sy0, sx1, sy1,
                        self.COL_GRID_MAJOR if major else self.COL_GRID)
            u += world_step

        # Yatay (v sabit)
        v = math.floor(vmin / world_step) * world_step
        while v <= vmax:
            sx0, sy0 = to_screen(umin, v)
            sx1, sy1 = to_screen(umax, v)
            major = abs((v / (world_step * 5)) - round(v / (world_step * 5))) < 1e-6
            dl.add_line(sx0, sy0, sx1, sy1,
                        self.COL_GRID_MAJOR if major else self.COL_GRID)
            v += world_step

    def _draw_axes(self, dl, to_screen):
        # U ekseni (v=0)
        x0, y0 = to_screen(-1e7, 0)
        x1, y1 = to_screen(1e7, 0)
        dl.add_line(x0, y0, x1, y1, self.COL_AXIS_U, 1.2)
        # V ekseni (u=0)
        x0, y0 = to_screen(0, -1e7)
        x1, y1 = to_screen(0, 1e7)
        dl.add_line(x0, y0, x1, y1, self.COL_AXIS_V, 1.2)
        # Orijin
        ox, oy = to_screen(0, 0)
        dl.add_circle_filled(ox, oy, 3.0, 0xFFFFFFFF)

    # ------------------------------------------------------------------
    def _draw_element(self, dl, kind: str, eid, to_screen, mode="assoc"):
        uvs = self._element_uvs(kind, eid)
        if not uvs:
            return

        is_sel = (kind, eid) in self.selected
        is_hov = (self.hover == (kind, eid))
        is_excluded = (mode == "excluded")

        # Renk seçimi
        if kind == "node":
            if is_excluded:
                col = self.COL_EXCLUDED
            elif is_sel:
                col = self.COL_NODE_SEL
            elif is_hov:
                col = self.COL_NODE_HOVER
            else:
                col = self.COL_NODE
            p = to_screen(*uvs[0])
            r = 6.0 if is_sel else (5.0 if is_hov else 4.0)
            dl.add_circle_filled(p[0], p[1], r, col)
            dl.add_circle(p[0], p[1], r + 0.8, 0xFF000000, 1.0)
            return

        if kind in ("frame", "link"):
            if len(uvs) < 2:
                return
            if is_excluded:
                col = self.COL_EXCLUDED
            elif kind == "link":
                col = self.COL_LINK if not (is_sel or is_hov) else self.COL_FRAME_SEL
            else:
                col = (self.COL_FRAME_SEL if is_sel
                       else self.COL_FRAME_HOVER if is_hov
                       else self.COL_FRAME)
            p0 = to_screen(*uvs[0])
            p1 = to_screen(*uvs[1])
            thickness = 2.5 if is_sel else (2.0 if is_hov else 1.5)
            dl.add_line(p0[0], p0[1], p1[0], p1[1], col, thickness)
            # Uç noktaları (küçük)
            if not is_excluded:
                r = 2.5
                dl.add_circle_filled(p0[0], p0[1], r, col)
                dl.add_circle_filled(p1[0], p1[1], r, col)
            return

        if kind in ("poly", "area"):
            if len(uvs) < 3:
                return
            if is_excluded:
                fill = 0x20808080
                edge = self.COL_EXCLUDED
            else:
                fill = self.COL_AREA_FILL if kind == "area" else self.COL_POLY_FILL
                edge = self.COL_AREA_EDGE if kind == "area" else self.COL_POLY_EDGE
                if is_sel or is_hov:
                    edge = self.COL_FRAME_SEL
            # Fan triangulation (dışbükey varsayımı)
            p0 = to_screen(*uvs[0])
            for i in range(1, len(uvs) - 1):
                p1 = to_screen(*uvs[i])
                p2 = to_screen(*uvs[i + 1])
                dl.add_triangle_filled(p0[0], p0[1], p1[0], p1[1],
                                        p2[0], p2[1], fill)
            # Kenarlar
            n = len(uvs)
            for i in range(n):
                a = to_screen(*uvs[i])
                b = to_screen(*uvs[(i + 1) % n])
                dl.add_line(a[0], a[1], b[0], b[1], edge, 1.2 if not is_sel else 2.0)
            return

    def _draw_draft(self, dl, kind: str, eid: str, data: dict, to_screen):
        """Pending ADD draft'ları — sarı, kesikli/özel."""
        p = self.plane
        if p is None:
            return

        # data'dan 2D noktaları çıkar
        uvs = []
        if kind == "node":
            x = data.get("x", 0.0); y = data.get("y", 0.0); z = data.get("z", 0.0)
            uvs.append(p.to_2d((x, y, z)))
        elif kind in ("frame", "link"):
            for key in ("node_i_xyz", "node_j_xyz"):
                xyz = data.get(key)
                if xyz and len(xyz) == 3:
                    uvs.append(p.to_2d(xyz))
        elif kind in ("poly", "area"):
            ref_pts = data.get("points_xyz") or []
            for xyz in ref_pts:
                if len(xyz) == 3:
                    uvs.append(p.to_2d(xyz))

        if not uvs:
            return

        col = self.COL_PENDING_ADD

        if kind == "node":
            sx, sy = to_screen(*uvs[0])
            dl.add_circle(sx, sy, 6.0, col, 1.8)
            dl.add_circle_filled(sx, sy, 2.5, col)
            return

        if kind in ("frame", "link") and len(uvs) >= 2:
            p0 = to_screen(*uvs[0]); p1 = to_screen(*uvs[1])
            dl.add_line(p0[0], p0[1], p1[0], p1[1], col, 1.8)
            return

        if kind in ("poly", "area") and len(uvs) >= 3:
            n = len(uvs)
            for i in range(n):
                a = to_screen(*uvs[i])
                b = to_screen(*uvs[(i + 1) % n])
                dl.add_line(a[0], a[1], b[0], b[1], col, 1.5)

    # ------------------------------------------------------------------
    #  Input
    # ------------------------------------------------------------------
    def _handle_input(self, imgui_ctx, cx, cy, cw, ch, to_screen, from_screen):
        ctrl, shift = self._get_mods()
        io = imgui_ctx.get_io()
        mx, my = io.mouse_pos
        over = cx <= mx <= cx + cw and cy <= my <= cy + ch

        self.clicked = None
        self.clicked_empty = False

        if not over:
            self.hover = None
            self._panning = False
            self._pan_anchor = None
            self._rubber = False
            return

        # Hover
        self.hover = self._hit_test(mx, my, to_screen)

        # Zoom
        if io.mouse_wheel != 0:
            self._apply_zoom(io.mouse_wheel, mx, my, cx, cy, cw, ch)

        # Pan
        space = self._is_space(imgui_ctx)
        start_pan = (
            imgui_ctx.is_mouse_clicked(2)
            or imgui_ctx.is_mouse_clicked(1)
            or (space and imgui_ctx.is_mouse_clicked(0))
        )
        if start_pan and not self._rubber:
            self._panning = True
            self._pan_anchor = (mx, my)

        if self._panning:
            if (imgui_ctx.is_mouse_down(2) or imgui_ctx.is_mouse_down(1)
                    or imgui_ctx.is_mouse_down(0)):
                if self._pan_anchor:
                    du = (mx - self._pan_anchor[0]) / self.zoom
                    dv = (my - self._pan_anchor[1]) / self.zoom
                    # Ekran deltası → view deltası (rotation dikkate)
                    r = math.radians(self.view_rotation)
                    cs, sn = math.cos(r), math.sin(r)
                    ddu = du * cs - dv * sn
                    ddv = -(du * sn + dv * cs)
                    self.pan = (self.pan[0] + ddu, self.pan[1] + ddv)
                    self._pan_anchor = (mx, my)
            else:
                self._panning = False
                self._pan_anchor = None

        # Seçim
        if imgui_ctx.is_mouse_clicked(0) and not self._panning and not space:
            hit = self._hit_test(mx, my, to_screen)
            if hit is not None:
                self.clicked = hit
            else:
                self._rubber = True
                self._rubber_start = (mx, my)
                self._rubber_end = (mx, my)

        if self._rubber:
            self._rubber_end = (mx, my)
            if imgui_ctx.is_mouse_released(0):
                self._finish_rubber(to_screen)
                self._rubber = False
                self._rubber_start = None
                self._rubber_end = None

    def _finish_rubber(self, to_screen):
        if not (self._rubber_start and self._rubber_end):
            return
        x0, y0 = self._rubber_start
        x1, y1 = self._rubber_end
        if abs(x1 - x0) < 3 and abs(y1 - y0) < 3:
            self.clicked_empty = True
            return
        rx0, rx1 = min(x0, x1), max(x0, x1)
        ry0, ry1 = min(y0, y1), max(y0, y1)

        io = imgui.get_io()
        hit = set()
        for kind, eid in self._iter_assoc_ids():
            for uv in self._element_uvs(kind, eid):
                sx, sy = to_screen(*uv)
                if rx0 <= sx <= rx1 and ry0 <= sy <= ry1:
                    hit.add((kind, eid))
                    break

        ctrl, shift = self._get_mods()
        if ctrl:
            self.selected ^= hit
        elif shift:
            self.selected |= hit
        else:
            self.selected = hit

    def _apply_zoom(self, wheel, mx, my, cx, cy, cw, ch):
        factor = self.ZOOM_STEP if wheel > 0 else 1.0 / self.ZOOM_STEP
        old = self.zoom
        new = max(self.MIN_ZOOM, min(old * factor, self.MAX_ZOOM))
        if new == old:
            return
        to_screen, from_screen = self._factory(cx, cy, cw, ch)
        u, v = from_screen(mx, my)
        self.zoom = new
        r = math.radians(self.view_rotation)
        cs, sn = math.cos(r), math.sin(r)
        ur, vr = _rot((u, v), r)
        hw = cw * 0.5
        hh = ch * 0.5
        pan_u = (mx - cx - hw) / new - ur
        pan_v = -(my - cy - hh) / new - vr
        self.pan = (pan_u, pan_v)

    def _hit_test(self, mx, my, to_screen):
        best = None
        best_d = self.HIT_RADIUS_PX

        # Önce node'lar
        for kind, eid in self._iter_assoc_ids():
            if kind != "node":
                continue
            for uv in self._element_uvs(kind, eid):
                sx, sy = to_screen(*uv)
                d = math.hypot(sx - mx, sy - my)
                if d < best_d:
                    best_d = d
                    best = (kind, eid)

        if best is not None:
            return best

        # Frame/link: nokta-doğru parçası mesafesi
        for kind, eid in self._iter_assoc_ids():
            if kind not in ("frame", "link"):
                continue
            uvs = self._element_uvs(kind, eid)
            if len(uvs) < 2:
                continue
            p0 = to_screen(*uvs[0])
            p1 = to_screen(*uvs[1])
            d = _dist_point_segment((mx, my), p0, p1)
            if d < best_d:
                best_d = d
                best = (kind, eid)

        return best

    @staticmethod
    def _is_space(imgui_ctx):
        io = imgui_ctx.get_io()
        if hasattr(io, "key_space"):
            return bool(io.key_space)
        try:
            return imgui_ctx.is_key_down(imgui.KEY_SPACE)
        except Exception:
            return False


# ----------------------------------------------------------------------
def _dist_point_segment(p, a, b):
    px, py = p
    ax, ay = a
    bx, by = b
    dx = bx - ax
    dy = by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-9:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / L2
    t = max(0.0, min(1.0, t))
    cx = ax + dx * t
    cy = ay + dy * t
    return math.hypot(px - cx, py - cy)