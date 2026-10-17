# ui/frame_load_panel.py
"""
Frame Distributed Load Atama Paneli - Segment Bazlı (v2)
- SAP2000 uyumlu 10 yön (Local/Global/Gravity/Projected)
- Kompakt segment tablosu, pencere genişliğine yayılan
- +/- butonları küçük ikon tarzı
- Frame üzerinde kalıcı saklama
"""
import imgui
import math
from typing import List, Optional, Callable
from data.enums import SAP_DIR_LABELS
from domain.definition import FrameDistributedLoad, LoadSegment
from domain.element import Frame


class FrameLoadPanel:
    CANVAS_WIDTH = 620
    CANVAS_HEIGHT = 300
    CANVAS_PADDING = 55
    POINT_RADIUS = 5.0
    HIT_RADIUS = 11.0
    SEGMENT_COLORS = [
        (1.00, 0.45, 0.20),
        (0.30, 0.80, 0.45),
        (0.40, 0.65, 1.00),
        (1.00, 0.80, 0.20),
        (0.85, 0.40, 0.85),
        (0.30, 0.85, 0.85),
        (0.95, 0.55, 0.65),
    ]

    def __init__(self, on_apply: Callable = None):
        self.visible = False
        self.on_apply = on_apply

        self.pattern_name = "DEAD"
        self.coord_sys = "Local"
        self.load_dir = "7"        # ← varsayılan Gravity (en sık kullanılan)
        self.mode = "REPLACE"
        self.is_relative = True

        self.active_set: FrameDistributedLoad = FrameDistributedLoad()
        self.target_frames: List[Frame] = []

        self.selected_segment_idx: Optional[int] = None
        self.hovered_segment_idx: Optional[int] = None
        self.dragging: Optional[tuple] = None

        self.max_q = 10.0
        self.min_q = 0.0
        self.available_patterns = ["DEAD", "LIVE", "WIND", "SNOW", "EQ"]

        self._canvas_origin = (0.0, 0.0)
        self._canvas_size = (0.0, 0.0)

    # ------------------------------------------------------------------
    # PUBLIC
    # ------------------------------------------------------------------
    def open(self, patterns: List[str] = None, target_frames: List[Frame] = None):
        self.visible = True
        if patterns:
            self.available_patterns = patterns
            if self.pattern_name not in patterns and patterns:
                self.pattern_name = patterns[0]
        self.target_frames = target_frames or []
        self._load_from_target()

    def close(self):
        self.visible = False
        self.dragging = None

    def set_target_frames(self, frames: List[Frame]):
        self.target_frames = frames
        self._load_from_target()

    def _load_from_target(self):
        """Hedef frame'lerin ilkinden mevcut yükü yükle."""
        if not self.target_frames:
            self.active_set = self._new_empty_set()
            self._ensure_default_segments()
            return

        first = self.target_frames[0]
        sets = getattr(first, "dist_load_sets", {}) or {}

        if self.pattern_name in sets:
            raw = sets[self.pattern_name]
            self.active_set = self._ensure_set_type(raw)
            self.coord_sys = self.active_set.coord_sys
            self.load_dir = self.active_set.load_dir
            self.mode = self.active_set.mode
        else:
            existing = [dl for dl in getattr(first, "dist_loads", [])
                        if dl.pattern_name == self.pattern_name]
            if existing:
                self.active_set = FrameDistributedLoad.from_sap_loads(existing)
                self.coord_sys = self.active_set.coord_sys
                self.load_dir = self.active_set.load_dir
                self.mode = self.active_set.mode
            else:
                self.active_set = self._new_empty_set()
                self._ensure_default_segments()

        self._update_q_range()

    def _ensure_set_type(self, raw):
        """dict gelirse FrameDistributedLoad'a çevir + segment'leri düzelt."""
        if isinstance(raw, FrameDistributedLoad):
            s = raw
        elif isinstance(raw, dict):
            s = FrameDistributedLoad(
                pattern_name=raw.get("pattern_name", self.pattern_name),
                coord_sys=raw.get("coord_sys", "Local"),
                load_dir=raw.get("load_dir", "2"),
                mode=raw.get("mode", "REPLACE"),
                is_relative=raw.get("is_relative", True),
            )
            raw_segs = raw.get("segments", [])
            fixed = []
            for seg in raw_segs:
                if isinstance(seg, LoadSegment):
                    fixed.append(seg)
                elif isinstance(seg, dict):
                    fixed.append(LoadSegment(
                        x1=float(seg.get("x1", 0.0)),
                        x2=float(seg.get("x2", 1.0)),
                        q1=float(seg.get("q1", 0.0)),
                        q2=float(seg.get("q2", 0.0)),
                    ))
            s.segments = fixed
            return s
        else:
            return self._new_empty_set()

        # Segment'lerin kesinlikle LoadSegment olduğundan emin ol
        fixed = []
        for seg in s.segments:
            if isinstance(seg, LoadSegment):
                fixed.append(seg)
            elif isinstance(seg, dict):
                fixed.append(LoadSegment(
                    x1=float(seg.get("x1", 0.0)),
                    x2=float(seg.get("x2", 1.0)),
                    q1=float(seg.get("q1", 0.0)),
                    q2=float(seg.get("q2", 0.0)),
                ))
        s.segments = fixed
        return s

    def _new_empty_set(self):
        return FrameDistributedLoad(
            pattern_name=self.pattern_name,
            coord_sys=self.coord_sys,
            load_dir=self.load_dir,
            mode=self.mode,
        )

    def _ensure_default_segments(self):
        if not self.active_set.segments:
            self.active_set.add_segment(0.0, 1.0, 0.0, 0.0)

    # ------------------------------------------------------------------
    # DRAW
    # ------------------------------------------------------------------
    def draw(self):
        if not self.visible:
            return

        # Pencereyi ekranın %65'ine yay
        io = imgui.get_io()
        w = min(max(int(io.display_size[0] * 0.55), 720), 1100)
        h = min(max(int(io.display_size[1] * 0.85), 640), 950)
        imgui.set_next_window_size(w, h, imgui.FIRST_USE_EVER)
        imgui.set_next_window_position(80, 60, imgui.FIRST_USE_EVER)

        expanded, opened = imgui.begin("Frame Distributed Load", True)
        if not opened:
            self.close()
            imgui.end()
            return

        if expanded:
            self._draw_header()
            imgui.separator()
            self._draw_load_settings()
            imgui.separator()
            self._draw_canvas()
            imgui.separator()
            self._draw_segment_table()
            imgui.separator()
            self._draw_actions()

        imgui.end()

    # ------------------------------------------------------------------
    def _draw_header(self):
        imgui.text_colored("Hedef Frame'ler:", 0.7, 0.8, 0.9, 1.0)
        if not self.target_frames:
            imgui.same_line()
            imgui.text_colored("(Seçili frame yok — sahne üzerinden seçin)",
                               1.0, 0.5, 0.3, 1.0)
        else:
            labels = [getattr(f, "label", None) or f"F_{f.unique_id}"
                      for f in self.target_frames[:6]]
            text = ", ".join(labels)
            if len(self.target_frames) > 6:
                text += f" ... (+{len(self.target_frames) - 6})"
            imgui.same_line()
            imgui.text_colored(f"{len(self.target_frames)} adet: {text}",
                               0.5, 0.9, 0.5, 1.0)

    # ------------------------------------------------------------------
    def _draw_load_settings(self):
        """2 satır halinde kompakt ayarlar."""
        # --- Satır 1: Pattern | CoordSys ---
        imgui.text("Pattern:")
        imgui.same_line(80)
        imgui.push_item_width(140)
        if imgui.begin_combo("##pattern", self.pattern_name):
            for pat in self.available_patterns:
                sel = (pat == self.pattern_name)
                if imgui.selectable(pat, sel)[0]:
                    self.pattern_name = pat
                    self.active_set.pattern_name = pat
                    self._load_from_target()
                if sel:
                    imgui.set_item_default_focus()
            imgui.end_combo()
        imgui.pop_item_width()

        imgui.same_line(240)
        imgui.text("CoordSys:")
        imgui.same_line(310)
        imgui.push_item_width(110)
        coord_opts = ["Local", "Global"]
        cidx = coord_opts.index(self.coord_sys) if self.coord_sys in coord_opts else 0
        ch, nidx = imgui.combo("##coord", cidx, coord_opts)
        if ch:
            self.coord_sys = coord_opts[nidx]
        imgui.pop_item_width()

        imgui.same_line(440)
        imgui.text("Mode:")
        imgui.same_line(490)
        imgui.push_item_width(120)
        mode_opts = ["REPLACE", "ADD"]
        midx = mode_opts.index(self.mode) if self.mode in mode_opts else 0
        ch, nidx = imgui.combo("##mode", midx, mode_opts)
        if ch:
            self.mode = mode_opts[nidx]
        imgui.pop_item_width()

        # --- Satır 2: Direction | DistType ---
        imgui.text("Dir:")
        imgui.same_line(80)
        imgui.push_item_width(240)
        dir_keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
        dir_labels = [SAP_DIR_LABELS[k] for k in dir_keys]
        didx = dir_keys.index(self.load_dir) if self.load_dir in dir_keys else 6
        ch, nidx = imgui.combo("##dir", didx, dir_labels)
        if ch:
            self.load_dir = dir_keys[nidx]
            # Local <-> Global uyumluluk kontrolü
            if self.coord_sys == "Local" and self.load_dir in ("4", "5", "6", "7"):
                imgui.open_popup("coord_warn")
        imgui.pop_item_width()

        imgui.same_line(340)
        imgui.text("DistType:")
        imgui.same_line(415)
        imgui.push_item_width(150)
        rel_opts = ["Relative", "Absolute"]
        ridx = 0 if self.is_relative else 1
        ch, nidx = imgui.combo("##disttype", ridx, rel_opts)
        if ch:
            self.is_relative = (nidx == 0)
        imgui.pop_item_width()

    # ------------------------------------------------------------------
    # CANVAS
    # ------------------------------------------------------------------
    def _draw_canvas(self):
        imgui.text_colored("Segment Diyagramı:", 0.8, 0.8, 0.6, 1.0)
        imgui.same_line()
        imgui.text_colored("(sol tık sürükle: tutamaç | Ctrl+tık: böl | sağ tık: sil)",
                           0.55, 0.55, 0.6, 1.0)

        avail = imgui.get_content_region_available_width()
        canvas_w = max(self.CANVAS_WIDTH, avail - 10)

        cpos = imgui.get_cursor_screen_pos()
        imgui.invisible_button("##canvas", canvas_w, self.CANVAS_HEIGHT)
        cend = imgui.get_item_rect_max()

        dl = imgui.get_window_draw_list()
        dl.add_rect_filled(cpos[0], cpos[1], cend[0], cend[1],
                           imgui.get_color_u32_rgba(0.09, 0.11, 0.15, 1.0))
        dl.add_rect(cpos[0], cpos[1], cend[0], cend[1],
                    imgui.get_color_u32_rgba(0.28, 0.32, 0.38, 1.0), 0, 1.5)

        ox = cpos[0] + self.CANVAS_PADDING
        oy = cpos[1] + self.CANVAS_PADDING
        cw = canvas_w - 2 * self.CANVAS_PADDING
        ch = self.CANVAS_HEIGHT - 2 * self.CANVAS_PADDING
        beam_y = oy + ch

        self._canvas_origin = (ox, oy)
        self._canvas_size = (cw, ch)

        self._draw_grid(dl, ox, oy, cw, ch)
        dl.add_line(ox, beam_y, ox + cw, beam_y,
                    imgui.get_color_u32_rgba(0.95, 0.95, 0.95, 1.0), 3.0)

        self._draw_segments(dl, ox, oy, cw, ch, beam_y)
        self._draw_axis_labels(dl, ox, oy, cw, ch)
        self._handle_canvas_input(ox, oy, cw, ch, beam_y, cpos, cend)

    def _draw_grid(self, dl, ox, oy, cw, ch):
        gc = imgui.get_color_u32_rgba(0.20, 0.22, 0.28, 1.0)
        for i in range(5):
            x = ox + cw * (i / 4.0)
            dl.add_line(x, oy, x, oy + ch, gc, 1.0)
        for i in range(5):
            y = oy + ch * (i / 4.0)
            dl.add_line(ox, y, ox + cw, y, gc, 1.0)

    def _q_to_y(self, q, oy, ch, beam_y):
        q_range = max(self.max_q - self.min_q, 1e-6)
        norm = (q - self.min_q) / q_range
        norm = max(0.0, min(1.0, norm))
        return beam_y - ch * norm

    def _draw_segments(self, dl, ox, oy, cw, ch, beam_y):
        for i, seg in enumerate(self.active_set.segments):
            base = self.SEGMENT_COLORS[i % len(self.SEGMENT_COLORS)]
            is_hov = (i == self.hovered_segment_idx)
            is_sel = (i == self.selected_segment_idx)
            alpha = 0.35 if (is_hov or is_sel) else 0.20

            x1 = ox + cw * seg.x1
            x2 = ox + cw * seg.x2
            y1 = self._q_to_y(seg.q1, oy, ch, beam_y)
            y2 = self._q_to_y(seg.q2, oy, ch, beam_y)

            fill = imgui.get_color_u32_rgba(base[0], base[1], base[2], alpha)
            dl.add_quad_filled(x1, y1, x2, y2, x2, beam_y, x1, beam_y, fill)

            lc = imgui.get_color_u32_rgba(*base, 1.0)
            thick = 3.0 if is_sel else (2.5 if is_hov else 2.0)
            dl.add_line(x1, y1, x2, y2, lc, thick)

            edge = imgui.get_color_u32_rgba(*base, 0.6)
            dl.add_line(x1, y1, x1, beam_y, edge, 1.2)
            dl.add_line(x2, y2, x2, beam_y, edge, 1.2)

            for (hx, hy) in [(x1, y1), (x2, y2)]:
                dl.add_circle_filled(hx, hy, self.POINT_RADIUS,
                                     imgui.get_color_u32_rgba(1, 1, 1, 1))
                dl.add_circle(hx, hy, self.POINT_RADIUS,
                              imgui.get_color_u32_rgba(*base, 1), 0, 2.0)

            # Etiketler
            mid_x = (x1 + x2) * 0.5
            top_y = min(y1, y2)
            dl.add_text(mid_x - 35, top_y - 18,
                        imgui.get_color_u32_rgba(1, 0.95, 0.7, 1),
                        f"q={seg.q1:.2f}→{seg.q2:.2f}")
            dl.add_text(mid_x - 35, beam_y + 22,
                        imgui.get_color_u32_rgba(0.7, 0.7, 0.75, 1),
                        f"x={seg.x1:.2f}→{seg.x2:.2f}")

    def _draw_axis_labels(self, dl, ox, oy, cw, ch):
        beam_y = oy + ch
        for i in range(5):
            x = ox + cw * (i / 4.0)
            dl.add_text(x - 14, beam_y + 5,
                        imgui.get_color_u32_rgba(0.6, 0.6, 0.6, 1),
                        f"{i*0.25:.2f}")
        q_range = max(self.max_q - self.min_q, 1e-6)
        for i in range(5):
            y = oy + ch * (i / 4.0)
            q_val = self.max_q - q_range * (i / 4.0)
            dl.add_text(ox - 45, y - 8,
                        imgui.get_color_u32_rgba(0.6, 0.6, 0.6, 1),
                        f"{q_val:.2f}")

    # ------------------------------------------------------------------
    # INPUT
    # ------------------------------------------------------------------
    def _handle_canvas_input(self, ox, oy, cw, ch, beam_y, cpos, cend):
        io = imgui.get_io()
        mouse = io.mouse_pos
        in_canvas = (cpos[0] <= mouse[0] <= cend[0] and
                     cpos[1] <= mouse[1] <= cend[1])

        if not in_canvas:
            self.hovered_segment_idx = None
            if not imgui.is_mouse_down(0):
                self.dragging = None
            return

        hit = self._find_nearest_handle(mouse, ox, oy, cw, ch, beam_y)
        self.hovered_segment_idx = hit[0] if hit else None

        if imgui.is_mouse_clicked(0) and hit:
            if io.key_ctrl:
                self._split_segment(hit[0], mouse, ox, cw)
            else:
                self.selected_segment_idx = hit[0]
                self.dragging = hit

        if imgui.is_mouse_down(0) and self.dragging:
            self._drag_handle(self.dragging[0], self.dragging[1],
                              mouse, ox, cw, oy, ch, beam_y)

        if imgui.is_mouse_released(0):
            self.dragging = None

        if imgui.is_mouse_clicked(1) and hit:
            if len(self.active_set.segments) > 1:
                del self.active_set.segments[hit[0]]
                self.selected_segment_idx = None
                self.hovered_segment_idx = None
                self._update_q_range()

    def _find_nearest_handle(self, mouse, ox, oy, cw, ch, beam_y):
        best = None
        best_d = self.HIT_RADIUS
        for i, seg in enumerate(self.active_set.segments):
            for side, (xr, q) in [("left", (seg.x1, seg.q1)),
                                  ("right", (seg.x2, seg.q2))]:
                sx = ox + cw * xr
                sy = self._q_to_y(q, oy, ch, beam_y)
                d = math.hypot(mouse[0] - sx, mouse[1] - sy)
                if d < best_d:
                    best_d = d
                    best = (i, side)
        return best

    def _drag_handle(self, seg_idx, side, mouse, ox, cw, oy, ch, beam_y):
        seg = self.active_set.segments[seg_idx]
        q_range = max(self.max_q - self.min_q, 1e-6)

        new_xr = (mouse[0] - ox) / cw
        new_xr = max(0.0, min(1.0, new_xr))

        norm_q = (beam_y - mouse[1]) / ch
        norm_q = max(0.0, min(1.0, norm_q))
        new_q = self.min_q + norm_q * q_range

        if side == "left":
            left_lim = self.active_set.segments[seg_idx - 1].x2 if seg_idx > 0 else 0.0
            new_xr = max(left_lim, min(seg.x2, new_xr))
            seg.x1, seg.q1 = new_xr, new_q
        else:
            right_lim = (self.active_set.segments[seg_idx + 1].x1
                         if seg_idx < len(self.active_set.segments) - 1 else 1.0)
            new_xr = min(right_lim, max(seg.x1, new_xr))
            seg.x2, seg.q2 = new_xr, new_q

        self._update_q_range()

    def _split_segment(self, idx, mouse, ox, cw):
        seg = self.active_set.segments[idx]
        mid_x = (mouse[0] - ox) / cw
        mid_x = max(seg.x1 + 0.01, min(seg.x2 - 0.01, mid_x))
        t = (mid_x - seg.x1) / max(seg.x2 - seg.x1, 1e-6)
        mid_q = seg.q1 + (seg.q2 - seg.q1) * t
        right_seg = LoadSegment(mid_x, seg.x2, mid_q, seg.q2)
        seg.x2 = mid_x
        seg.q2 = mid_q
        self.active_set.segments.insert(idx + 1, right_seg)
        self.selected_segment_idx = idx + 1

    def _update_q_range(self):
        segs = self.active_set.segments or []
        if not segs:
            self.max_q, self.min_q = 10.0, 0.0
            return
        qs = []
        for s in segs:
            q1 = getattr(s, "q1", None)
            q2 = getattr(s, "q2", None)
            if q1 is None and isinstance(s, dict):
                q1 = s.get("q1", 0.0)
            if q2 is None and isinstance(s, dict):
                q2 = s.get("q2", 0.0)
            qs.append(float(q1 or 0.0))
            qs.append(float(q2 or 0.0))

        self.max_q = max(max(qs) * 1.2, 1.0)
        self.min_q = min(0.0, min(qs))

    # ------------------------------------------------------------------
    # SEGMENT TABLOSU
    # ------------------------------------------------------------------
    def _draw_segment_table(self):
        imgui.text_colored("Segment Listesi:", 0.8, 0.8, 0.6, 1.0)
        imgui.same_line()

        if imgui.small_button("+##add"):
            self._add_segment_after_selected()
        if imgui.is_item_hovered():
            imgui.set_tooltip("Seçili segmenti ikiye böl")
        imgui.same_line()
        if imgui.small_button("=##uniform"):
            self._make_uniform()
        if imgui.is_item_hovered():
            imgui.set_tooltip("Seçili segmenti uniform yap (q1=q2)")
        imgui.same_line()
        if imgui.small_button("-##del"):
            if (self.selected_segment_idx is not None
                    and len(self.active_set.segments) > 1):
                del self.active_set.segments[self.selected_segment_idx]
                self.selected_segment_idx = None
                self._update_q_range()
        if imgui.is_item_hovered():
            imgui.set_tooltip("Seçili segmenti sil")

        imgui.same_line()
        imgui.text_colored(f"({len(self.active_set.segments)} segment)",
                           0.6, 0.6, 0.7, 1.0)

        imgui.begin_child("seg_list", 0, 0, True)

        avail = imgui.get_content_region_available_width()
        col_idx_w = 32
        col_x_w = (avail - col_idx_w - 40) * 0.22
        col_q_w = (avail - col_idx_w - 40) * 0.28

        imgui.columns(5, "seg_cols", True)
        imgui.set_column_width(0, col_idx_w)
        imgui.set_column_width(1, col_x_w)
        imgui.set_column_width(2, col_x_w)
        imgui.set_column_width(3, col_q_w)
        imgui.set_column_width(4, col_q_w)

        imgui.text("#"); imgui.next_column()
        imgui.text("x1 (rel)"); imgui.next_column()
        imgui.text("x2 (rel)"); imgui.next_column()
        imgui.text("q1"); imgui.next_column()
        imgui.text("q2"); imgui.next_column()

        for i, seg in enumerate(self.active_set.segments):
            imgui.push_id(f"seg_{i}")

            if i == self.selected_segment_idx:
                imgui.push_style_color(imgui.COLOR_TEXT, 0.4, 1.0, 0.5, 1.0)

            if imgui.selectable(f"{i+1}", i == self.selected_segment_idx,
                                width=col_idx_w - 4)[0]:
                self.selected_segment_idx = i
            imgui.next_column()

            ch1, v1 = imgui.input_float("##x1", seg.x1, 0.01, 0.05, "%.3f")
            if ch1:
                seg.x1 = max(0.0, min(seg.x2 - 0.001, v1))
            imgui.next_column()

            ch2, v2 = imgui.input_float("##x2", seg.x2, 0.01, 0.05, "%.3f")
            if ch2:
                seg.x2 = max(seg.x1 + 0.001, min(1.0, v2))
            imgui.next_column()

            cq1, w1 = imgui.input_float("##q1", seg.q1, 0.1, 1.0, "%.3f")
            if cq1:
                seg.q1 = w1
                self._update_q_range()
            imgui.next_column()

            cq2, w2 = imgui.input_float("##q2", seg.q2, 0.1, 1.0, "%.3f")
            if cq2:
                seg.q2 = w2
                self._update_q_range()
            imgui.next_column()

            imgui.pop_item_width()

            if i == self.selected_segment_idx:
                imgui.pop_style_color(1)

            imgui.pop_id()

        imgui.columns(1)
        imgui.end_child()

    def _add_segment_after_selected(self):
        segs = self.active_set.segments
        if not segs:
            self.active_set.add_segment(0.0, 1.0, 0.0, 0.0)
            return
        idx = (self.selected_segment_idx
               if self.selected_segment_idx is not None
               else len(segs) - 1)
        seg = segs[idx]
        mid_x = (seg.x1 + seg.x2) * 0.5
        mid_q = (seg.q1 + seg.q2) * 0.5
        right = LoadSegment(mid_x, seg.x2, mid_q, seg.q2)
        seg.x2, seg.q2 = mid_x, mid_q
        segs.insert(idx + 1, right)
        self.selected_segment_idx = idx + 1

    def _make_uniform(self):
        if self.selected_segment_idx is None:
            return
        seg = self.active_set.segments[self.selected_segment_idx]
        avg = (seg.q1 + seg.q2) * 0.5
        seg.q1 = seg.q2 = avg

    # ------------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------------
    def _draw_actions(self):
        can_apply = bool(self.target_frames) and len(self.active_set.segments) > 0

        if not can_apply:
            imgui.push_style_color(imgui.COLOR_BUTTON, 0.3, 0.3, 0.3, 1.0)

        if imgui.button("  UYGULA  ", 180, 34) and can_apply:
            self._apply_to_frames()

        if not can_apply:
            imgui.pop_style_color(1)

        imgui.same_line()
        if imgui.button("Temizle", 90, 34):
            self.active_set.clear()
            self.active_set.add_segment(0.0, 1.0, 0.0, 0.0)
            self._update_q_range()

        imgui.same_line()
        if imgui.button("Uniform Yap", 110, 34):
            if self.active_set.segments:
                seg = self.active_set.segments[0]
                self.active_set.segments = [seg]
                self.selected_segment_idx = 0

        imgui.same_line()
        if imgui.button("Hedefi Yenile", 130, 34):
            if callable(self.on_refresh_targets):
                self.on_refresh_targets()

        imgui.spacing()
        if not self.target_frames:
            imgui.text_colored("⚠ Seçili frame yok — sahne üzerinden seçin",
                               1.0, 0.6, 0.3, 1.0)
        else:
            dir_label = SAP_DIR_LABELS.get(self.load_dir, self.load_dir)
            imgui.text_colored(
                f"✓ {len(self.target_frames)} frame | "
                f"{len(self.active_set.segments)} segment | "
                f"Pat={self.pattern_name} | "
                f"{self.coord_sys}/{dir_label.split(' - ')[1]} | "
                f"{self.mode}",
                0.6, 0.8, 0.6, 1.0
            )

    def _apply_to_frames(self):
        if not self.target_frames:
            return
        self.active_set.pattern_name = self.pattern_name
        self.active_set.coord_sys = self.coord_sys
        self.active_set.load_dir = self.load_dir
        self.active_set.mode = self.mode

        if callable(self.on_apply):
            self.on_apply(self.target_frames, self.active_set)