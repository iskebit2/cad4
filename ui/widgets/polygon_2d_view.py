# ui/widgets/polygon_2d_view.py
"""
Polygon2DView — Poly'yi kendi düzleminden (u-v) 2D gösterir.
Frame'ler çizgi, node'lar daire olarak çizilir.
Tıklama ile frame seçimi.
"""
import math
import imgui
import numpy as np

from domain.plane import Plane


class Polygon2DView:

    def __init__(self):
        self.plane = None
        self.poly_2d = []          # [(u, v), ...]
        self.frames_2d = []        # [(fid, (u1,v1), (u2,v2), frame_obj)]
        self.selected_fids = set()
        self.hover_fid = None
        self.clicked_fid = None

        # Görünüm
        self.zoom = 1.0
        self.pan_u = 0.0
        self.pan_v = 0.0
        self._fit_pending = True

        # Stil
        self.col_bg = (0.10, 0.12, 0.18, 1.0)
        self.col_poly = (0.85, 0.65, 0.35, 1.0)      # poly sınırı
        self.col_poly_fill = (0.85, 0.65, 0.35, 0.10) # çok şeffaf dolgu
        self.col_frame = (0.65, 0.75, 0.85, 1.0)
        self.col_frame_sel = (0.95, 0.55, 0.30, 1.0)
        self.col_frame_hover = (0.95, 0.85, 0.40, 1.0)
        self.col_node = (0.55, 0.85, 1.0, 1.0)
        self.col_node_first = (0.95, 0.40, 0.40, 1.0)

    # ------------------------------------------------------------------
    def load_polygon(self, poly, scene):
        """Poly'yi ve assoc frame'leri yükle."""
        self.plane = Plane.from_polygon(poly)
        self.poly_2d = self.plane.polygon_to_2d(poly)
        self.frames_2d = []

        assoc = list(getattr(poly, "associated_frame_ids", []))
        for fid in assoc:
            frame = scene.frames.get(fid)
            if frame is None or not frame.node_i or not frame.node_j:
                continue
            p1 = (frame.node_i.x, frame.node_i.y, frame.node_i.z)
            p2 = (frame.node_j.x, frame.node_j.y, frame.node_j.z)
            uv1 = self.plane.to_2d(p1)
            uv2 = self.plane.to_2d(p2)
            self.frames_2d.append((fid, uv1, uv2, frame))

        self._fit_pending = True

    # ------------------------------------------------------------------
    def _compute_bounds(self):
        """Tüm çizilecek şeylerin u-v sınırları."""
        us, vs = [], []
        for (u, v) in self.poly_2d:
            us.append(u); vs.append(v)
        for (_, uv1, uv2, _) in self.frames_2d:
            us.extend([uv1[0], uv2[0]])
            vs.extend([uv1[1], uv2[1]])
        if not us or not vs:
            return 0.0, 1.0, 0.0, 1.0
        u_min, u_max = min(us), max(us)
        v_min, v_max = min(vs), max(vs)
        pad_u = (u_max - u_min) * 0.05 + 1e-6
        pad_v = (v_max - v_min) * 0.05 + 1e-6
        return u_min - pad_u, u_max + pad_u, v_min - pad_v, v_max + pad_v

    # ------------------------------------------------------------------
    def draw(self, imgui, draw_list, canvas_pos, canvas_size):
        """
        ImGui draw_list ile çizim.
        canvas_pos: (x, y) ekran koordinatı (sol üst)
        canvas_size: (w, h) piksel
        """
        cx, cy = canvas_pos
        cw, ch = canvas_size

        # Arka plan
        draw_list.add_rect_filled(cx, cy, cx + cw, cy + ch, imgui.get_color_u32_rgba(*self.col_bg))

        if not self.poly_2d:
            draw_list.add_text(cx + 10, cy + 10,
                              imgui.get_color_u32_rgba(0.6, 0.6, 0.6, 1.0),
                              "Polygon yüklenmedi")
            return

        # Sınırlar
        u_min, u_max, v_min, v_max = self._compute_bounds()
        u_span = max(u_max - u_min, 1e-6)
        v_span = max(v_max - v_min, 1e-6)

        # Ekran dönüşümü (eşit ölçek, ortala)
        margin = 20
        scale_x = (cw - 2 * margin) / u_span
        scale_y = (ch - 2 * margin) / v_span
        scale = min(scale_x, scale_y) * self.zoom

        # Merkez offset
        offset_u = (u_min + u_max) * 0.5 + self.pan_u
        offset_v = (v_min + v_max) * 0.5 + self.pan_v

        def to_screen(u, v):
            sx = cx + cw * 0.5 + (u - offset_u) * scale
            # v eksenini ters çevir (ekranda +v yukarı olsun)
            sy = cy + ch * 0.5 - (v - offset_v) * scale
            return sx, sy

        def to_world(sx, sy):
            u = (sx - cx - cw * 0.5) / scale + offset_u
            v = -(sy - cy - ch * 0.5) / scale + offset_v
            return u, v

        # 1. Poly dolgusu (çok şeffaf)
        if len(self.poly_2d) >= 3:
            pts = [to_screen(u, v) for (u, v) in self.poly_2d]
            fill_col = imgui.get_color_u32_rgba(*self.col_poly_fill)
            # ImGui triangle fan ile dolgu
            for i in range(1, len(pts) - 1):
                draw_list.add_triangle_filled(
                    pts[0][0], pts[0][1],
                    pts[i][0], pts[i][1],
                    pts[i + 1][0], pts[i + 1][1],
                    fill_col,
                )

        # 2. Poly sınırı
        if len(self.poly_2d) >= 2:
            pts = [to_screen(u, v) for (u, v) in self.poly_2d]
            poly_col = imgui.get_color_u32_rgba(*self.col_poly)
            for i in range(len(pts)):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % len(pts)]
                draw_list.add_line(x1, y1, x2, y2, poly_col, 2.0)

        # 3. Frame'ler
        mouse = imgui.get_mouse_pos()
        self.hover_fid = None
        hover_dist = 8.0  # piksel
        for (fid, uv1, uv2, _frame) in self.frames_2d:
            sx1, sy1 = to_screen(*uv1)
            sx2, sy2 = to_screen(*uv2)

            is_sel = fid in self.selected_fids

            # Hover testi (çizgiye mesafe)
            mx, my = mouse
            dist = self._point_to_segment_dist((mx, my), (sx1, sy1), (sx2, sy2))
            is_hover = dist < hover_dist and (self.hover_fid is None or dist < hover_dist)
            if is_hover:
                self.hover_fid = fid

            if is_sel:
                col = imgui.get_color_u32_rgba(*self.col_frame_sel)
                thickness = 3.0
            elif is_hover:
                col = imgui.get_color_u32_rgba(*self.col_frame_hover)
                thickness = 3.0
            else:
                col = imgui.get_color_u32_rgba(*self.col_frame)
                thickness = 1.5

            draw_list.add_line(sx1, sy1, sx2, sy2, col, thickness)

        # 4. Node'lar
        for i, (u, v) in enumerate(self.poly_2d):
            sx, sy = to_screen(u, v)
            col = self.col_node_first if i == 0 else self.col_node
            draw_list.add_circle_filled(sx, sy, 4.0, imgui.get_color_u32_rgba(*col))

        # 5. Etkileşim
        self._handle_input(imgui, canvas_pos, canvas_size, to_world)

    # ------------------------------------------------------------------
    @staticmethod
    def _point_to_segment_dist(p, a, b):
        px, py = p
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        if L2 < 1e-9:
            return math.hypot(px - ax, py - ay)
        t = ((px - ax) * dx + (py - ay) * dy) / L2
        t = max(0.0, min(1.0, t))
        cx, cy = ax + t * dx, ay + t * dy
        return math.hypot(px - cx, py - cy)

    # ------------------------------------------------------------------
    def _handle_input(self, imgui, canvas_pos, canvas_size, to_world):
        cx, cy = canvas_pos
        cw, ch = canvas_size
        mx, my = imgui.get_mouse_pos()

        hovered = imgui.is_mouse_hovering_rect(cx, cy, cx + cw, cy + ch)

        # Tıklama
        if hovered and imgui.is_mouse_clicked(0):  # sol tık
            if self.hover_fid is not None:
                self.clicked_fid = self.hover_fid

        # Zoom
        if hovered:
            wheel = imgui.get_io().mouse_wheel
            if wheel != 0.0:
                # Mouse noktasını merkez alarak zoom
                old_zoom = self.zoom
                self.zoom *= (1.0 + wheel * 0.1)
                self.zoom = max(0.1, min(20.0, self.zoom))

                # Pan'ı ayarla ki mouse noktası sabit kalsın
                u_m, v_m = to_world(mx, my)
                # to_world'da kullanılan zoom eski, yenisini hesaba kat
                # Basit yaklaşım: merkezi kaydır
                # (Detaylı zoom-at-mouse için biraz daha matematik gerekli)