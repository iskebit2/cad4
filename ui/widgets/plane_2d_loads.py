# ui/widgets/plane_2d_loads.py
"""2D view'da yük gösterim katmanı."""

from __future__ import annotations
import math
import numpy as np
from imgui_bundle import imgui

from domain.definition import LoadDirection


class LoadOverlay:
    """Frame/node/area yüklerini 2D view'da çizer.

    - FrameDistributedLoad → trapezoid + oklar
    - PointLoad → ok + değer
    - AreaUniformLoad → taralı alan
    """
    COL_DIST_LOAD     = 0xFF40B0FF     # turuncu-amber
    COL_DIST_LOAD_SEL = 0xFFFFE040
    COL_POINT_LOAD    = 0xFFFF8040
    COL_AREA_LOAD     = 0x50FFB040     # yarı saydam turuncu
    COL_TEXT          = 0xFFE0E0E0
    COL_ARROW_HEAD    = 0xFFFFFFFF

    # Görsel ölçek
    ARROW_LEN_PX      = 28.0          # yük vektörü uzunluğu (ekranda)
    ARROW_SPACING_PX  = 18.0          # ardışık ok mesafesi
    TEXT_SIZE_PX      = 11.0

    def __init__(self):
        self.show_loads = True
        self.show_values = True
        self.show_arrows = True
        self.pattern_filter: str | None = None

    # ------------------------------------------------------------------
    def draw(self, dl, plane, scene, frame_map, node_map,
             to_screen, selected_set, hover):
        if not self.show_loads:
            return
        self._draw_frame_loads(dl, plane, frame_map, to_screen, selected_set, hover)
        self._draw_node_loads(dl, plane, node_map, to_screen, selected_set, hover)

    # ------------------------------------------------------------------
    def _draw_frame_loads(self, dl, plane, frame_map, to_screen, selected, hover):
        for fid, frame in frame_map.items():
            loadsets = getattr(frame, "dist_load_sets", {})
            if not loadsets:
                continue
            for pat, load_set in loadsets.items():
                if self.pattern_filter and pat != self.pattern_filter:
                    continue

                # Frame'in 2D uçları
                ni_uv = plane.to_2d((frame.node_i.x, frame.node_i.y, frame.node_i.z))
                nj_uv = plane.to_2d((frame.node_j.x, frame.node_j.y, frame.node_j.z))
                p0 = to_screen(*ni_uv)
                p1 = to_screen(*nj_uv)

                is_sel = ("frame", fid) in selected
                is_hov = (hover == ("frame", fid))

                col = (self.COL_DIST_LOAD_SEL if is_sel or is_hov
                       else self.COL_DIST_LOAD)

                for seg in load_set.segments:
                    self._draw_dist_segment(
                        dl, p0, p1, seg, col, plane, load_set,
                    )

    def _draw_dist_segment(self, dl, p0, p1, seg, col, plane, load_set):
        """Bir yayılı yük segmenti — trapezoid + oklar."""
        # Ekran uzunluğu
        dx = p1[0] - p0[0]
        dy = p1[1] - p0[1]
        L = math.hypot(dx, dy)
        if L < 1e-3:
            return
        ux, uy = dx / L, dy / L            # birim vektör (frame yönü)
        nx, ny = -uy, ux                    # normal (yük yönü ekran)

        # q değerleri (S2K birimi, proj birimine çevirmek gerekmez — sadece görsel)
        q1, q2 = seg.q1, seg.q2
        if abs(q1) < 1e-12 and abs(q2) < 1e-12:
            return

        # Rel → ekran
        s0 = (p0[0] + ux * L * seg.x1, p0[1] + uy * L * seg.x1)
        s1 = (p0[0] + ux * L * seg.x2, p0[1] + uy * L * seg.x2)
        seg_len = L * (seg.x2 - seg.x1)

        # q_max → ARROW_LEN_PX oranı (görsel ölçek)
        q_abs_max = max(abs(q1), abs(q2), 1e-9)
        scale = self.ARROW_LEN_PX / q_abs_max
        # İşaret: q negatifse ters yön
        sign1 = 1.0 if q1 >= 0 else -1.0
        sign2 = 1.0 if q2 >= 0 else -1.0

        a0 = (s0[0] + nx * q1 * scale * sign1, s0[1] + ny * q1 * scale * sign1)
        a1 = (s1[0] + nx * q2 * scale * sign2, s1[1] + ny * q2 * scale * sign2)

        # Trapezoid (yarı saydam)
        fill = self._alpha(col, 0.20)
        dl.add_quad_filled(
            imgui.ImVec2(*s0), imgui.ImVec2(*s1),
            imgui.ImVec2(*a1), imgui.ImVec2(*a0),
            fill,
        )
        # Çerçeve (dış çizgi)
        dl.add_line(imgui.ImVec2(*s0), imgui.ImVec2(*a0), col, 1.5)
        dl.add_line(imgui.ImVec2(*s1), imgui.ImVec2(*a1), col, 1.5)
        dl.add_line(imgui.ImVec2(*a0), imgui.ImVec2(*a1), col, 1.0)

        # Oklar (ardışık)
        if self.show_arrows:
            n_arrows = max(2, int(seg_len / self.ARROW_SPACING_PX))
            for k in range(n_arrows + 1):
                t = k / n_arrows
                q_interp = q1 * (1 - t) + q2 * t
                sign = 1.0 if q_interp >= 0 else -1.0
                base_x = s0[0] + (s1[0] - s0[0]) * t
                base_y = s0[1] + (s1[1] - s0[1]) * t
                tip_x = base_x + nx * q_interp * scale * sign
                tip_y = base_y + ny * q_interp * scale * sign
                self._draw_arrow(dl, (base_x, base_y), (tip_x, tip_y), col)

        # Değer metni
        if self.show_values:
            mid_x = (a0[0] + a1[0]) * 0.5
            mid_y = (a0[1] + a1[1]) * 0.5
            text = f"{q1:.2f}" if abs(q1 - q2) < 1e-6 else f"{q1:.2f}/{q2:.2f}"
            self._draw_text(dl, (mid_x, mid_y), text, col)

    def _draw_arrow(self, dl, base, tip, col, head_size=4.0):
        """Ok başı çiz."""
        dx = tip[0] - base[0]
        dy = tip[1] - base[1]
        L = math.hypot(dx, dy)
        if L < 1e-3:
            return
        ux, uy = dx / L, dy / L
        # Ok başı
        px, py = -uy, ux
        h = head_size
        dl.add_triangle_filled(
            imgui.ImVec2(*tip),
            imgui.ImVec2(tip[0] - ux * h + px * h * 0.6, tip[1] - uy * h + py * h * 0.6),
            imgui.ImVec2(tip[0] - ux * h - px * h * 0.6, tip[1] - uy * h - py * h * 0.6),
            col,
        )

    def _draw_node_loads(self, dl, plane, node_map, to_screen, selected, hover):
        for nid, node in node_map.items():
            if not node.loads:
                continue
            uv = plane.to_2d((node.x, node.y, node.z))
            p = to_screen(*uv)
            is_sel = ("node", nid) in selected
            col = self.COL_POINT_LOAD if not is_sel else self.COL_DIST_LOAD_SEL

            # Force bileşenleri
            for load in node.loads:
                fx, fy, fz = load.fx, load.fy, load.fz
                # 2D vektör — plane u/v projeksiyonu
                u, v, _ = plane.uv_basis()
                vec_2d = (
                    float(np.dot([fx, fy, fz], u)),
                    float(np.dot([fx, fy, fz], v)),
                )
                mag = math.hypot(*vec_2d)
                if mag < 1e-6:
                    continue
                # Görsel ölçek: ARROW_LEN_PX'e oranla
                scale = self.ARROW_LEN_PX / max(abs(mag), 1e-6)
                # UX/UV normalize
                ex = vec_2d[0] / mag * self.ARROW_LEN_PX
                ey = vec_2d[1] / mag * self.ARROW_LEN_PX
                # Ekran Y ters
                tip = (p[0] + ex, p[1] - ey)
                self._draw_arrow(dl, p, tip, col, head_size=5.0)
                if self.show_values:
                    self._draw_text(
                        dl, ((p[0] + tip[0]) * 0.5, (p[1] + tip[1]) * 0.5),
                        f"{mag:.2f}", col,
                    )

    # ------------------------------------------------------------------
    @staticmethod
    def _alpha(col, a):
        """ABGR → alfa azalt."""
        if a >= 1.0:
            return col
        rgb = col & 0x00FFFFFF
        alpha = int((col >> 24) & 0xFF)
        new_alpha = int(alpha * a)
        return (new_alpha << 24) | rgb

    def _draw_text(self, dl, screen_pos, text, col):
        dl.add_text(imgui.ImVec2(*screen_pos), col, text)