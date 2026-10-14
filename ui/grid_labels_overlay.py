# ui/grid_labels_overlay.py
"""
Grid label overlay — 3D grid anchor'larını ekran uzayına projekte edip
ImGui draw list ile 2D metin olarak çizer.
"""
from typing import List, Dict, Tuple
import glm
import imgui


class GridLabelsOverlay:
    """
    Grid etiketlerini 2D overlay olarak çizer.
    begin_frame() ile end_frame() arasında çağrılmalıdır.
    """

    COLORS = {
        "X": (0.95, 0.35, 0.35, 1.0),
        "Y": (0.35, 0.95, 0.45, 1.0),
        "Z": (0.40, 0.65, 1.00, 1.0),
    }
    BG_COLOR     = (0.08, 0.10, 0.16, 0.85)
    BORDER_COLOR = (0.30, 0.35, 0.45, 1.0)

    SCREEN_OFFSET = (8, -18)   # sağa, yukarı (negatif y = yukarı)
    MIN_W = 0.0001

    def __init__(self):
        self.enabled = True
        self.padding = (4.0, 2.0)
        self.rounding = 3.0

        # Cache
        self._anchor_cache = None
        self._cache_key = None

    # ------------------------------------------------------------------
    def _get_anchors_cached(self, grid_system):
        key = (
            tuple(grid_system.x_coords),
            tuple(grid_system.y_coords),
            tuple(grid_system.z_coords),
            grid_system.origin.x,
            grid_system.origin.y,
            grid_system.origin.z,
            tuple(sorted((p.name, d["visible"]) for p, d in grid_system.planes.items())),
        )
        if key != self._cache_key:
            self._anchor_cache = grid_system.get_label_anchors()
            self._cache_key = key
        return self._anchor_cache

    # ------------------------------------------------------------------
    def draw(self, grid_system, mvp: glm.mat4, view_w: int, view_h: int,
             show_axis: Tuple[bool, bool, bool] = (True, True, True)):
        if not self.enabled or grid_system is None:
            return

        anchors = self._get_anchors_cached(grid_system)
        if not anchors:
            return

        axis_filter = {"X": show_axis[0], "Y": show_axis[1], "Z": show_axis[2]}

        projected = []
        for a in anchors:
            if not axis_filter.get(a["axis"], True):
                continue

            x, y, z = a["pos"]
            clip = mvp * glm.vec4(x, y, z, 1.0)

            if clip.w <= self.MIN_W:
                continue

            ndc_x = clip.x / clip.w
            ndc_y = clip.y / clip.w
            ndc_z = clip.z / clip.w

            # Ekran dışı (biraz toleranslı)
            if not (-1.3 <= ndc_x <= 1.3 and -1.3 <= ndc_y <= 1.3):
                continue

            sx = (ndc_x * 0.5 + 0.5) * view_w
            sy = (1.0 - (ndc_y * 0.5 + 0.5)) * view_h

            projected.append({
                "text": a["text"],
                "axis": a["axis"],
                "x": sx,
                "y": sy,
                "depth": ndc_z,
            })

        if not projected:
            return

        # Uzak → yakın sırala (yakın olanlar üstte çizilsin)
        projected.sort(key=lambda p: -p["depth"])

        # ImGui draw list
        draw_list = self._get_draw_list()
        if draw_list is None:
            return

        # Ekran-uzayı cluster — çok yakın label'ları teke indir
        projected = self._cluster(projected, min_dist=18.0)

        for p in projected:
            self._draw_one(draw_list, p)

    # ------------------------------------------------------------------
    def _get_draw_list(self):
        """Farklı imgui sürümleri için güvenli draw list erişimi."""
        for name in ("get_foreground_draw_list",
                     "get_background_draw_list",
                     "get_overlay_draw_list",
                     "get_window_draw_list"):
            fn = getattr(imgui, name, None)
            if callable(fn):
                try:
                    return fn()
                except Exception:
                    continue
        return None

    # ------------------------------------------------------------------
    def _cluster(self, items, min_dist: float):
        """Aynı piksel bölgesindeki label'lardan ilkini tut."""
        kept = []
        md2 = min_dist * min_dist
        for it in items:
            too_close = False
            for k in kept:
                dx = it["x"] - k["x"]
                dy = it["y"] - k["y"]
                if dx * dx + dy * dy < md2:
                    too_close = True
                    break
            if not too_close:
                kept.append(it)
        return kept

    # ------------------------------------------------------------------
    def _draw_one(self, draw_list, p: Dict):
        text = p["text"]
        color = self.COLORS.get(p["axis"], (1.0, 1.0, 1.0, 1.0))

        text_w, text_h = imgui.calc_text_size(text)

        ox, oy = self.SCREEN_OFFSET
        x = p["x"] + ox
        y = p["y"] + oy

        pad_x, pad_y = self.padding
        x0 = x - pad_x
        y0 = y - pad_y
        x1 = x + text_w + pad_x
        y1 = y + text_h + pad_y

        draw_list.add_rect_filled(
            x0, y0, x1, y1,
            imgui.get_color_u32_rgba(*self.BG_COLOR),
            self.rounding,
        )
        draw_list.add_rect(
            x0, y0, x1, y1,
            imgui.get_color_u32_rgba(*self.BORDER_COLOR),
            self.rounding,
        )
        draw_list.add_text(
            x, y,
            imgui.get_color_u32_rgba(*color),
            text,
        )