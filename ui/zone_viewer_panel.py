# ui/zone_viewer_panel.py
from __future__ import annotations
from imgui_bundle import imgui
from domain.element import Polygon
from ui.base_panel import BasePanel
from logging_config import CadLogger
from pyglm import glm
logger = CadLogger.get(__name__)

class ZoneViewerPanel(BasePanel):

    _instance: "ZoneViewerPanel | None" = None   # Seçenek B için; A kullanırsan gerek yok

    def __init__(self):
        super().__init__(
            title="Rüzgar Zone Görüntüleyici",
            width=720, height=560,
            pos_first_use=(300, 120),
        )
        self.scene = None
        self._polygon_id: int | None = None
        self._direction: str | None = None
        self._selected_zone_idx: tuple[str, int] | None = None
        self._zoom: float = 1.0
        self._pan = glm.vec2(0, 0)

    @classmethod
    def instance(cls) -> "ZoneViewerPanel":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_context(self, ctx: dict):
        super().set_context(ctx)
        self.scene = ctx.get("scene")

    def show_polygon(self, polygon, direction: str | None = None):
        self._polygon_id = int(polygon.unique_id)
        self._direction = direction
        self._selected_zone_idx = None
        self._zoom = 1.0
        self._pan = glm.vec2(0, 0)
        self.open()

    def _polygon(self):
        if self._polygon_id is None or self.scene is None:
            return None
        return self.scene.polygons.get(self._polygon_id)

    def draw_content(self):
        p = self._polygon()
        if p is None:
            imgui.text_colored(imgui.ImVec4(0.7,0.7,0.7,1), "Polygon yok.")
            return
        if not p.zone_children_by_direction:
            imgui.text_colored(imgui.ImVec4(0.7,0.7,0.7,1), "Bu polygon için zone yok.")
            return

        # ---- üst bar ----
        imgui.text(f"{p.label or 'Polygon'} (id={p.unique_id})")
        imgui.same_line()

        dirs = sorted(p.zone_children_by_direction.keys())
        labels = ["Tümü"] + dirs
        cur = 0 if self._direction is None else (
            labels.index(self._direction) if self._direction in labels else 0
        )
        imgui.push_item_width(120)
        ch, idx = imgui.combo("##dir", cur, labels)
        imgui.pop_item_width()
        if ch:
            self._direction = None if idx == 0 else labels[idx]
            self._selected_zone_idx = None

        imgui.same_line()
        if imgui.button("Fit"):
            self._zoom = 1.0
            self._pan = glm.vec2(0, 0)

        # ---- canvas ----
        avail = imgui.get_content_region_avail()
        canvas_size = (max(avail.x, 100.0), max(avail.y, 100.0))

        imgui.begin_child("##zone_canvas", canvas_size, imgui.ChildFlags_.borders)
        try:
            child_pos = imgui.get_cursor_screen_pos()
            dl = imgui.get_window_draw_list()
            self._draw_2d(dl, child_pos, canvas_size, p)
        finally:
            imgui.end_child()

    def _draw_2d(self, dl, canvas_pos, canvas_size, polygon):
        u, v, n = Polygon.calculate_plane_axes(polygon.nodes)
        origin = glm.vec3(*polygon.centroid())

        # zone listesi
        if self._direction is None:
            records = []
            for dk, zones in polygon.zone_children_by_direction.items():
                for zi, z in enumerate(zones):
                    records.append((dk, zi, z))
        else:
            records = [
                (self._direction, zi, z)
                for zi, z in enumerate(
                    polygon.zone_children_by_direction.get(self._direction, [])
                )
            ]

        # bbox
        pts2d = []
        for _, _, rec in records:
            for (x, y, z) in rec["coords"]:
                d = glm.vec3(x, y, z) - origin
                pts2d.append((glm.dot(d, u), glm.dot(d, v)))
        for nd in polygon.nodes:
            d = glm.vec3(nd._x, nd._y, nd._z) - origin
            pts2d.append((glm.dot(d, u), glm.dot(d, v)))
        if not pts2d:
            return

        min_u = min(p[0] for p in pts2d); max_u = max(p[0] for p in pts2d)
        min_v = min(p[1] for p in pts2d); max_v = max(p[1] for p in pts2d)
        span_u = max(max_u - min_u, 1e-6); span_v = max(max_v - min_v, 1e-6)
        margin = 20.0
        scale = min(
            (canvas_size[0] - 2*margin) / span_u,
            (canvas_size[1] - 2*margin) / span_v,
        ) * self._zoom

        def to_screen(uu, vv):
            return imgui.ImVec2(
                float(canvas_pos.x + margin + (uu - min_u) * scale + self._pan.x),
                float(canvas_pos.y + canvas_size[1] - margin - (vv - min_v) * scale + self._pan.y),
            )

        # ana polygon
        poly_pts = []
        for nd in polygon.nodes:
            d = glm.vec3(nd._x, nd._y, nd._z) - origin
            poly_pts.append(to_screen(glm.dot(d, u), glm.dot(d, v)))
        for i in range(len(poly_pts)):
            dl.add_line(poly_pts[i], poly_pts[(i+1) % len(poly_pts)], 0xFF606060, 1.5)

        # zone'lar
        palette = [
            0xFF4E79A7, 0xFFF28E2B, 0xFFE15759, 0xFF76B7B2, 0xFF59A14F,
            0xFFEDC949, 0xFFAF7AA1, 0xFFFF9DA7, 0xFF9C755F, 0xFFBAB0AC,
        ]
        for i, (dk, zi, rec) in enumerate(records):
            color = palette[i % len(palette)]
            fill = (color & 0x00FFFFFF) | 0x33000000
            zpts = []
            for (x, y, z) in rec["coords"]:
                d = glm.vec3(x, y, z) - origin
                zpts.append(to_screen(glm.dot(d, u), glm.dot(d, v)))
            if len(zpts) >= 3:
                try:
                    dl.add_concave_poly_filled(zpts, fill)
                except AttributeError:
                    pass
            dl.add_polyline(zpts, color, imgui.ImDrawFlags_.closed, 1.5)

            if self._selected_zone_idx == (dk, zi):
                dl.add_polyline(zpts, 0xFFFFFFFF, imgui.ImDrawFlags_.closed, 2.5)

            # centroid
            cu = sum(pt.x for pt in zpts) / len(zpts)
            cv = sum(pt.y for pt in zpts) / len(zpts)

            label = rec.get("label_override") or rec.get("label", "?")
            cpe10 = rec.get("cpe10_override") or rec.get("cpe10", (0, 0))
            cpe1 = rec.get("cpe1_override") or rec.get("cpe1", (0, 0))
            meta = f"{dk} | {rec.get('kind','')}"
            if rec.get("pitch"):
                meta += f" | p={rec['pitch']:.0f}°"

            dl.add_text(imgui.ImVec2(cu - 30, cv - 30), 0xFFFFFFFF, label)
            dl.add_text(imgui.ImVec2(cu - 30, cv - 16), 0xFFD0D0D0,
                        f"cpe10={cpe10[0]:+.2f}/{cpe10[1]:+.2f}")
            dl.add_text(imgui.ImVec2(cu - 30, cv - 2), 0xFFD0D0D0,
                        f"cpe1={cpe1[0]:+.2f}/{cpe1[1]:+.2f}")
            dl.add_text(imgui.ImVec2(cu - 30, cv + 12), 0xFFA0A0A0, meta)

            # tıklama
            rect_min = imgui.ImVec2(min(pt.x for pt in zpts), min(pt.y for pt in zpts))
            rect_max = imgui.ImVec2(max(pt.x for pt in zpts), max(pt.y for pt in zpts))
            if imgui.is_mouse_clicked(0) and imgui.is_mouse_hovering_rect(rect_min, rect_max):
                self._selected_zone_idx = (dk, zi)