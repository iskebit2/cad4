# ui/plane_plot_panel.py

from __future__ import annotations

from imgui_bundle import imgui

from domain.plane import ChangeOp, Plane
from logging_config import CadLogger
from ui.base_panel import BasePanel
from ui.widgets.plane_2d_view import Plane2DView

logger = CadLogger.get(__name__)


class PlanePlotPanel(BasePanel):

    PANEL_W = 1100
    PANEL_H = 700
    HEADER_H = 34
    BOTTOM_H = 0

    def __init__(self):
        self.app = None
        self.scene = None
        self.plane: Plane | None = None

        self.view2d = Plane2DView()
        # self.selected = set()       # (kind, id) — view2d ile senkron

        self.visible = False

        # Yeni plane için default boyutlar
        self._pv_u_min = -5000.0
        self._pv_u_max = 5000.0
        self._pv_v_min = -5000.0
        self._pv_v_max = 5000.0
        self._pv_depth_minus = 500.0
        self._pv_depth_plus = 500.0

        # "Assoc filter" Inspector için
        self._assoc_filter_active = False

    @property
    def selected(self):
        return self.view2d.selected

    # ------------------------------------------------------------------
    def _scene(self):
        if self.scene is not None:
            return self.scene
        if self.app and self.app.engine is not None:
            return self.app.engine.scene
        if self.app and self.app.current_project is not None:
            return self.app.current_project.scene
        return None

    def open(self, scene=None, plane: Plane = None):
        if scene is not None:
            self.scene = scene

        if plane is not None:
            self.plane = plane
            self.selected.clear()
            sc = self._scene()
            if sc is not None:
                self.view2d.load_plane(plane, sc)
        elif self.plane is not None:
            sc = self._scene()
            if sc is not None:
                self.view2d.load_plane(self.plane, sc)

        self.view2d._mods_getter = self._read_mods
        # --- sel_mgr bağla ---
        smgr = self._sel_mgr()
        if smgr is not None:
            self.view2d.bind_selection(smgr)

        self.visible = True
        self._set_inspector_assoc_filter(True)

    def close(self):
        self.visible = False
        # self._set_inspector_assoc_filter(False)

    def set_plane(self, plane: Plane):
        self.plane = plane
        self.selected.clear()
        sc = self._scene()
        if sc is not None:
            self.view2d.load_plane(plane, sc)
        self._set_inspector_assoc_filter(True)

    def refresh(self):
        sc = self._scene()
        if self.plane is not None and sc is not None:
            self.view2d.load_plane(self.plane, sc)

    # ------------------------------------------------------------------
    def _read_mods(self):
        try:
            import glfw
            w = self.app.window.window if self.app and self.app.window else None
            if w is None:
                return False, False
            ctrl = (glfw.get_key(w, glfw.KEY_LEFT_CONTROL) == glfw.PRESS or
                    glfw.get_key(w, glfw.KEY_RIGHT_CONTROL) == glfw.PRESS)
            shift = (glfw.get_key(w, glfw.KEY_LEFT_SHIFT) == glfw.PRESS or
                     glfw.get_key(w, glfw.KEY_RIGHT_SHIFT) == glfw.PRESS)
            return bool(ctrl), bool(shift)
        except Exception:
            return False, False

    # ------------------------------------------------------------------
    #  Inspector assoc filtresi
    # ------------------------------------------------------------------
    def _set_inspector_assoc_filter(self, active: bool):
        if self._assoc_filter_active == active:
            return
        self._assoc_filter_active = active
        app = self.app
        if app is None:
            return
        inspector = getattr(app, "inspector", None)
        if inspector is None:
            return
        controller = getattr(inspector, "controller", None)
        if controller is None:
            return

        # Yeni API
        if hasattr(controller, "set_filter_assoc_only"):
            controller.set_filter_assoc_only(self.plane if active else None)
        else:
            # Eski/fallback
            if hasattr(controller, "filter_assoc_only"):
                controller.filter_assoc_only = self.plane if active else None

    # ------------------------------------------------------------------
    #  draw
    # ------------------------------------------------------------------
    def draw(self):
        if not self.visible:
            return

        if self.plane is None:
            imgui.set_next_window_size(imgui.ImVec2(400, 120), imgui.Cond_.first_use_ever)
            imgui.set_next_window_pos(imgui.ImVec2(200, 200), imgui.Cond_.first_use_ever)
            expanded, opened = imgui.begin("Plane Plot", True)
            try:
                if not opened:
                    self.visible = False
                    return
                imgui.text_colored(imgui.ImVec4(0.7, 0.7, 0.7, 1.0), 'Plane seçilmedi.')
                imgui.text_colored(imgui.ImVec4(0.5, 0.5, 0.5, 1.0), "Plane Manager'dan bir plane seç.")
            finally:
                imgui.end()
            return

        imgui.set_next_window_size(imgui.ImVec2(self.PANEL_W, self.PANEL_H), imgui.Cond_.first_use_ever)
        imgui.set_next_window_pos(imgui.ImVec2(20, 60), imgui.Cond_.first_use_ever)

        # Window padding = 0 (canvas kenarlara yapışsın)
        imgui.push_style_var(
            imgui.StyleVar_.window_padding, imgui.ImVec2(4.0, 4.0)
        )
        imgui.push_style_var(imgui.StyleVar_.window_border_size, 0.0)

        expanded, opened = imgui.begin(f"Plane Plot — {self.plane.name}",
                                        True, imgui.WindowFlags_.no_scrollbar)
        try:
            if not opened:
                self.close()
                return
            if not expanded:
                return

            # Layout'u hesapla
            avail = imgui.get_content_region_avail()
            canvas_w = max(200.0, avail[0])
            total_h = avail[1]
            canvas_h = max(100.0, total_h - self.HEADER_H - 8)

            # 1) Header (tek satır butonlar)
            self._draw_header()

            # 2) Canvas (tam genişlik)
            self._draw_canvas(canvas_w, canvas_h)

            

        finally:
            imgui.pop_style_var(2)
            imgui.end()

    # ------------------------------------------------------------------
    #  Header — tek satır butonlar
    # ------------------------------------------------------------------
    def _draw_header(self):
        p = self.plane

        # --- 1. Butonlar (Sol taraf, küçük/ikonumsu ASCII alternatifleri) ---
        if imgui.button("<"):  self.view2d.rotate_view(-90)
        imgui.same_line(0, 2)
        if imgui.button(">"):  self.view2d.rotate_view(90)
        imgui.same_line(0, 2)
        if imgui.button("+"):  self.view2d.zoom_at_center(1.15)
        imgui.same_line(0, 2)
        if imgui.button("-"):  self.view2d.zoom_at_center(1/1.15)
        imgui.same_line(0, 2)
        if imgui.button("Fit"): self.view2d.fit_to_content()

        # --- 2. Grid / Axes ---
        imgui.same_line(0, 8)
        _, self.view2d.show_grid = imgui.checkbox("Grid", self.view2d.show_grid)
        imgui.same_line(0, 4)
        _, self.view2d.show_axes = imgui.checkbox("Axes", self.view2d.show_axes)

        # --- 3-4. Apply / Cancel (Değişiklik varsa) ---
        n_pending = len(p.pending)
        dirty = (n_pending > 0)
        if dirty:
            imgui.same_line(0, 8)
            imgui.push_style_color(
                imgui.Col_.button, imgui.ImVec4(0.20, 0.55, 0.30, 1.0)
            )
            imgui.push_style_color(
                imgui.Col_.button_hovered, imgui.ImVec4(0.28, 0.68, 0.40, 1.0)
            )
            if imgui.button("Ok") and dirty:
                self._do_apply_pending()
            imgui.pop_style_color(2)

            imgui.same_line(0, 2)
            imgui.push_style_color(
                imgui.Col_.button, imgui.ImVec4(0.45, 0.20, 0.20, 1.0)
            )
            imgui.push_style_color(
                imgui.Col_.button_hovered, imgui.ImVec4(0.60, 0.28, 0.28, 1.0)
            )
            if imgui.button("X") and dirty:
                self._do_cancel_pending()
            imgui.pop_style_color(2)

        # --- 5. Dinamik Label Alanları (En sağa yaslı: Seçim, Pending, Depth/Rot/Zoom) ---
        n_sel = len(self.selected)
        if n_sel > 0:
            types = {}
            for kind, _ in self.selected:
                types[kind] = types.get(kind, 0) + 1
            type_str = ", ".join(f"{n}{k[0]}" for k, n in types.items())
            sel_text = f"Sel: {n_sel} ({type_str})"
        else:
            sel_text = "Sel: 0"

        if n_pending > 0:
            adds = sum(1 for ch in p.pending.values() if ch.op == ChangeOp.ADD)
            mods = sum(1 for ch in p.pending.values() if ch.op == ChangeOp.MODIFY)
            dels = sum(1 for ch in p.pending.values() if ch.op == ChangeOp.DELETE)
            pending_text = f"+{adds} ~{mods} -{dels}"
        else:
            pending_text = "+0 ~0 -0"

        stats_text = (
            f"{sel_text} | {pending_text} | "
            f"depth=[-{p.depth_minus:.0f},+{p.depth_plus:.0f}]  "
            f"rot={self.view2d.view_rotation:+.0f}deg  "
            f"zoom={self.view2d.zoom:.2f}"
        )

        # Sağa yaslama hesaplaması
        text_width = imgui.calc_text_size(stats_text).x
        available_width = imgui.get_content_region_avail().x
        if available_width > text_width:
            imgui.same_line(available_width - text_width)

        imgui.text_colored(imgui.ImVec4(0.7, 0.75, 0.85, 1.0), stats_text)

    # ------------------------------------------------------------------
    #  Canvas — tam genişlik, kendi başına çizim
    # ------------------------------------------------------------------
    def _draw_canvas(self, canvas_w, canvas_h):
        pos = imgui.get_cursor_screen_pos()
        canvas_pos = (pos.x, pos.y)

        # Görünmez buton → tıklamaları yakala (arka plan)
        imgui.invisible_button(
            "##pp_canvas_area", imgui.ImVec2(canvas_w, canvas_h)
        )

        # 2D view çiz
        dl = imgui.get_window_draw_list()
        
        self.view2d.draw(imgui, dl, canvas_pos, (canvas_w, canvas_h))

        # Canvas içi overlay — hover tooltip
        self._draw_canvas_overlay(canvas_pos, (canvas_w, canvas_h))

        # Seçim sonuçlarını işle
        self._consume_view_clicks()

    def _draw_canvas_overlay(self, canvas_pos, canvas_size):
        """Canvas içinde HUD — hover bilgisi, mouse pozisyonu."""
        cx, cy = canvas_pos
        cw, ch = canvas_size

        # Hover'daki eleman bilgisi (mouse sağ alt köşede)
        hover = self.view2d.hover
        if hover is None:
            return
        kind, eid = hover
        col_coll = {"frame": "frames", "node": "nodes", "area": "areas",
                    "link": "links", "poly": "polygons"}.get(kind)
        scene = self._scene()
        if not col_coll or scene is None:
            return
        el = getattr(scene, col_coll, {}).get(eid)
        if el is None:
            return

        label = getattr(el, "label", "") or f"{kind}#{eid}"
        txt = f"{kind} #{eid}  {label}"

        # Tooltip gibi sağ alt köşede
        imgui.set_cursor_screen_pos(
            imgui.ImVec2(cx + cw - 300, cy + ch - 26)
        )
        imgui.text_colored(imgui.ImVec4(0.7, 0.85, 0.95, 1.0), txt)

    def _consume_view_clicks(self):
        v = self.view2d

        if v.clicked is not None:
            kind, eid = v.clicked
            el = self._kind_id_to_element(kind, eid)
            ctrl, shift = v._get_mods()

            if el is not None and self._sel_mgr() is not None:
                smgr = self._sel_mgr()
                if ctrl:
                    smgr.select(el, additive=True)   # toggle
                elif shift:
                    smgr.select(el, additive=True)   # add (Ctrl ile aynı şu an)
                else:
                    smgr.select_only(el)
            v.clicked = None

        if v.clicked_empty:
            if not imgui.get_io().key_ctrl:
                smgr = self._sel_mgr()
                if smgr is not None:
                    smgr.clear()
            v.clicked_empty = False

    # ------------------------------------------------------------------
    def _do_apply_pending(self):
        p = self.plane
        sc = self._scene()
        if sc is None:
            return
        report = p.apply_pending(sc)
        logger.info(f"[PlanePlot] Pending uygulandı: {report}")
        self.refresh()

    def _do_cancel_pending(self):
        p = self.plane
        p.clear_pending()
        logger.info("[PlanePlot] Pending iptal edildi.")
        self.refresh()

    def _sel_mgr(self):
        app = self.app
        if app and getattr(app, "engine", None):
            return getattr(app.engine, "sel_mgr", None)
        return None

    def _kind_id_to_element(self, kind, eid):
        scene = self._scene()
        if scene is None:
            return None
        coll = {"node": "nodes", "frame": "frames", "area": "areas",
                "link": "links", "poly": "polygons"}.get(kind)
        if not coll:
            return None
        return getattr(scene, coll, {}).get(eid)