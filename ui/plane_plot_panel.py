# ui/plane_plot_panel.py

from __future__ import annotations

from imgui_bundle import imgui

from domain.plane import ChangeOp, Plane
from logging_config import CadLogger
from ui.base_panel import BasePanel
from ui.widgets.plane_2d_tools import ToolKind
from ui.widgets.plane_2d_view import Plane2DView

logger = CadLogger.get(__name__)


class PlanePlotPanel(BasePanel):

    PANEL_W = 1100
    PANEL_H = 680
    HEADER_H = 30.0       # tek satır toolbar
    STATS_H = 22.0        # alt istatistik satırı
    PAD = 6.0

    # Tool form ayrı pencere
    TOOL_FORM_W = 340
    TOOL_FORM_H = 520

    def __init__(self):
        self.app = None
        self.scene = None
        self.plane: Plane | None = None

        self.view2d = Plane2DView()
        self.visible = False

        # Tool form penceresi görünürlüğü
        self._tool_form_open = True

        # Yeni plane için default boyutlar
        self._pv_u_min = -5000.0
        self._pv_u_max = 5000.0
        self._pv_v_min = -5000.0
        self._pv_v_max = 5000.0
        self._pv_depth_minus = 500.0
        self._pv_depth_plus = 500.0

        self._assoc_filter_active = False

    @property
    def selected(self):
        return self.view2d.selected

    # ------------------------------------------------------------------
    #  Yaşam döngüsü
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
            sc = self._scene()
            if sc is not None:
                self.view2d.load_plane(plane, sc)
        elif self.plane is not None:
            sc = self._scene()
            if sc is not None:
                self.view2d.load_plane(self.plane, sc)

        self.view2d._mods_getter = self._read_mods
        smgr = self._sel_mgr()
        if smgr is not None:
            self.view2d.bind_selection(smgr)

        self.visible = True
        self._tool_form_open = True
        self._set_inspector_assoc_filter(True)

    def close(self):
        self.visible = False

    def set_plane(self, plane: Plane):
        self.plane = plane
        sc = self._scene()
        if sc is not None:
            self.view2d.load_plane(plane, sc)
        self._set_inspector_assoc_filter(True)

    def refresh(self):
        sc = self._scene()
        if self.plane is not None and sc is not None:
            self.view2d.load_plane(self.plane, sc)

    # ------------------------------------------------------------------
    #  Modifier okuma (GLFW)
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
        if hasattr(controller, "set_filter_assoc_only"):
            controller.set_filter_assoc_only(self.plane if active else None)
        elif hasattr(controller, "filter_assoc_only"):
            controller.filter_assoc_only = self.plane if active else None

    # ------------------------------------------------------------------
    #  Ana draw — iki pencere: ana panel + (opsiyonel) tool form
    # ------------------------------------------------------------------
    def draw(self):
        if not self.visible:
            return

        # Plane yoksa bilgi penceresi
        if self.plane is None:
            self._draw_empty_state()
            return

        # 1) Ana pencere — sabit boyut, resize yok
        self._draw_main_window()

        # 2) Tool form — ayrı, açılıp kapanabilen pencere
        self._draw_tool_form_window()

    # ------------------------------------------------------------------
    def _draw_empty_state(self):
        imgui.set_next_window_size(
            imgui.ImVec2(400, 120), imgui.Cond_.always
        )
        imgui.set_next_window_pos(
            imgui.ImVec2(200, 200), imgui.Cond_.first_use_ever
        )
        expanded, opened = imgui.begin("Plane Plot", True)
        try:
            if not opened:
                self.visible = False
                return
            imgui.text_colored(
                imgui.ImVec4(0.7, 0.7, 0.7, 1.0), "Plane seçilmedi."
            )
            imgui.text_colored(
                imgui.ImVec4(0.5, 0.5, 0.5, 1.0),
                "Plane Manager'dan bir plane seç.",
            )
        finally:
            imgui.end()

    # ------------------------------------------------------------------
    def _draw_main_window(self):
        # Sabit boyut — her frame zorla
        imgui.set_next_window_size(
            imgui.ImVec2(self.PANEL_W, self.PANEL_H), imgui.Cond_.always
        )
        imgui.set_next_window_pos(
            imgui.ImVec2(20, 60), imgui.Cond_.first_use_ever
        )

        flags = (
            imgui.WindowFlags_.no_scrollbar
            | imgui.WindowFlags_.no_resize
            | imgui.WindowFlags_.no_collapse
        )

        imgui.push_style_var(imgui.StyleVar_.window_padding,
                             imgui.ImVec2(self.PAD, self.PAD))
        imgui.push_style_var(imgui.StyleVar_.window_border_size, 0.0)
        imgui.push_style_var(imgui.StyleVar_.item_spacing,
                             imgui.ImVec2(4.0, 2.0))

        expanded, opened = imgui.begin(
            f"Plane Plot — {self.plane.name}", True, flags
        )
        try:
            if not opened:
                self.close()
                return
            if not expanded:
                return

            # Alanı sabit formülle böl — taşma imkansız
            avail = imgui.get_content_region_avail()
            canvas_w = max(200.0, avail[0])
            canvas_h = max(
                100.0,
                avail[1] - self.HEADER_H - self.STATS_H - 2 * self.PAD,
            )

            self._draw_toolbar()          # tek satır, HEADER_H'a sığar
            self._draw_canvas(canvas_w, canvas_h)
            self._draw_stats_line()       # alt istatistik satırı
        finally:
            imgui.pop_style_var(3)
            imgui.end()

    # ------------------------------------------------------------------
    #  Toolbar — TEK satır
    # ------------------------------------------------------------------
    def _draw_toolbar(self):
        tools = [
            (ToolKind.SELECT, "Sel", "Seçim"),
            (ToolKind.DRAW_LINE, "Line", "Çizgi"),
            (ToolKind.DRAW_POLY, "Poly", "Poligon"),
            (ToolKind.PLACE_DIST_LOAD, "Dist", "Yayılı yük"),
            (ToolKind.PLACE_JOINT_LOAD, "Point", "Nokta yük"),
            (ToolKind.MEASURE, "Msr", "Ölçüm"),
        ]
        # Tool seçici
        for kind, label, tip in tools:
            active = (self.view2d.active_tool == kind)
            if active:
                imgui.push_style_color(
                    imgui.Col_.button, imgui.ImVec4(0.2, 0.55, 0.3, 1.0)
                )
                imgui.push_style_color(
                    imgui.Col_.button_hovered, imgui.ImVec4(0.28, 0.68, 0.40, 1.0)
                )
            if imgui.button(label, imgui.ImVec2(52, 24)):
                self.view2d.set_tool(kind)
            if active:
                imgui.pop_style_color(2)
            if imgui.is_item_hovered():
                imgui.set_tooltip(tip)
            imgui.same_line(0, 3)

        # Ayırıcı
        imgui.same_line(0, 8)
        imgui.text_colored(imgui.ImVec4(0.4, 0.4, 0.4, 1.0), "|")
        imgui.same_line(0, 8)

        # View kontrolleri
        if imgui.button("◀", imgui.ImVec2(24, 24)):
            self.view2d.rotate_view(-90)
        imgui.same_line(0, 2)
        if imgui.button("▶", imgui.ImVec2(24, 24)):
            self.view2d.rotate_view(90)
        imgui.same_line(0, 2)
        if imgui.button("+", imgui.ImVec2(24, 24)):
            self.view2d.zoom_at_center(1.15)
        imgui.same_line(0, 2)
        if imgui.button("-", imgui.ImVec2(24, 24)):
            self.view2d.zoom_at_center(1 / 1.15)
        imgui.same_line(0, 2)
        if imgui.button("Fit", imgui.ImVec2(34, 24)):
            self.view2d.fit_to_content()

        imgui.same_line(0, 8)
        _, self.view2d.show_grid = imgui.checkbox(
            "Grid", self.view2d.show_grid
        )
        imgui.same_line(0, 4)
        _, self.view2d.show_axes = imgui.checkbox(
            "Axes", self.view2d.show_axes
        )

        # Apply / Cancel — sadece pending varsa
        p = self.plane
        n_pending = len(p.pending) if p else 0
        if n_pending > 0:
            imgui.same_line(0, 8)
            imgui.push_style_color(
                imgui.Col_.button, imgui.ImVec4(0.20, 0.55, 0.30, 1.0)
            )
            imgui.push_style_color(
                imgui.Col_.button_hovered, imgui.ImVec4(0.28, 0.68, 0.40, 1.0)
            )
            if imgui.button("Apply", imgui.ImVec2(56, 24)):
                self._do_apply_pending()
            imgui.pop_style_color(2)

            imgui.same_line(0, 2)
            imgui.push_style_color(
                imgui.Col_.button, imgui.ImVec4(0.45, 0.20, 0.20, 1.0)
            )
            imgui.push_style_color(
                imgui.Col_.button_hovered, imgui.ImVec4(0.60, 0.28, 0.28, 1.0)
            )
            if imgui.button("Cancel", imgui.ImVec2(56, 24)):
                self._do_cancel_pending()
            imgui.pop_style_color(2)

        # Tool form penceresi aç/kapa
        imgui.same_line(0, 8)
        _, self._tool_form_open = imgui.checkbox(
            "Form", self._tool_form_open
        )

    # ------------------------------------------------------------------
    #  Canvas — tam genişlik, sabit yükseklik
    # ------------------------------------------------------------------
    def _draw_canvas(self, canvas_w, canvas_h):
        pos = imgui.get_cursor_screen_pos()
        canvas_pos = (pos.x, pos.y)

        imgui.invisible_button(
            "##pp_canvas_area", imgui.ImVec2(canvas_w, canvas_h)
        )
        dl = imgui.get_window_draw_list()
        self.view2d.draw(imgui, dl, canvas_pos, (canvas_w, canvas_h))
        self._draw_canvas_overlay(canvas_pos, (canvas_w, canvas_h))
        self._consume_view_clicks()

    def _draw_canvas_overlay(self, canvas_pos, canvas_size):
        cx, cy = canvas_pos
        cw, ch = canvas_size
        hover = self.view2d.hover
        if hover is None:
            return
        kind, eid = hover
        col_coll = {
            "frame": "frames", "node": "nodes", "area": "areas",
            "link": "links", "poly": "polygons",
        }.get(kind)
        scene = self._scene()
        if not col_coll or scene is None:
            return
        el = getattr(scene, col_coll, {}).get(eid)
        if el is None:
            return
        label = getattr(el, "label", "") or f"{kind}#{eid}"
        txt = f"{kind} #{eid}  {label}"
        imgui.set_cursor_screen_pos(
            imgui.ImVec2(cx + cw - 300, cy + ch - 26)
        )
        imgui.text_colored(imgui.ImVec4(0.7, 0.85, 0.95, 1.0), txt)

    # ------------------------------------------------------------------
    #  Alt istatistik satırı — tek satır, taşmaz
    # ------------------------------------------------------------------
    def _draw_stats_line(self):
        p = self.plane
        n_sel = len(self.selected)
        if n_sel > 0:
            types = {}
            for kind, _ in self.selected:
                types[kind] = types.get(kind, 0) + 1
            type_str = ", ".join(f"{n}{k[0]}" for k, n in types.items())
            sel_text = f"Sel: {n_sel} ({type_str})"
        else:
            sel_text = "Sel: 0"

        n_pending = len(p.pending) if p else 0
        if n_pending > 0:
            adds = sum(1 for ch in p.pending.values() if ch.op == ChangeOp.ADD)
            mods = sum(1 for ch in p.pending.values() if ch.op == ChangeOp.MODIFY)
            dels = sum(1 for ch in p.pending.values() if ch.op == ChangeOp.DELETE)
            pending_text = f"+{adds} ~{mods} -{dels}"
        else:
            pending_text = "+0 ~0 -0"

        stats_text = (
            f"{sel_text}  |  {pending_text}  |  "
            f"depth=[-{p.depth_minus:.0f},+{p.depth_plus:.0f}]  "
            f"rot={self.view2d.view_rotation:+.0f}deg  "
            f"zoom={self.view2d.zoom:.2f}"
        )
        imgui.text_colored(imgui.ImVec4(0.65, 0.70, 0.80, 1.0), stats_text)

    # ------------------------------------------------------------------
    #  Tool form — AYRI pencere, açılıp kapanabilir
    # ------------------------------------------------------------------
    def _draw_tool_form_window(self):
        if not self._tool_form_open:
            return
        tool = self.view2d.active_tool_obj
        if tool is None:
            return

        imgui.set_next_window_size(
            imgui.ImVec2(self.TOOL_FORM_W, self.TOOL_FORM_H),
            imgui.Cond_.first_use_ever,
        )
        # Ana panelin sağına yerleştir
        imgui.set_next_window_pos(
            imgui.ImVec2(20 + self.PANEL_W + 10, 60),
            imgui.Cond_.first_use_ever,
        )

        expanded, opened = imgui.begin("Tool — Form", True)
        try:
            if not opened:
                self._tool_form_open = False
                return
            if not expanded:
                return
            tool.draw_ui(self.plane, self._scene())
        finally:
            imgui.end()

    # ------------------------------------------------------------------
    #  View click tüketimi
    # ------------------------------------------------------------------
    def _consume_view_clicks(self):
        v = self.view2d

        if v.clicked is not None:
            kind, eid = v.clicked
            el = self._kind_id_to_element(kind, eid)
            ctrl, shift = v._get_mods()
            smgr = self._sel_mgr()
            if el is not None and smgr is not None:
                if ctrl:
                    smgr.select(el, additive=True)
                elif shift:
                    from core.selection_policy import SelectionMode
                    smgr.select_multiple([el], mode=SelectionMode.ADD)
                else:
                    smgr.select_only(el)
            v.clicked = None

        if v.clicked_empty:
            ctrl, shift = v._get_mods()
            if not ctrl and not shift:
                smgr = self._sel_mgr()
                if smgr is not None:
                    smgr.clear()
            v.clicked_empty = False

    # ------------------------------------------------------------------
    #  Pending apply/cancel
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
        self.plane.clear_pending()
        logger.info("[PlanePlot] Pending iptal edildi.")
        self.refresh()

    # ------------------------------------------------------------------
    def _sel_mgr(self):
        app = self.app
        if app and getattr(app, "engine", None):
            return getattr(app.engine, "sel_mgr", None)
        return None

    def _kind_id_to_element(self, kind, eid):
        scene = self._scene()
        if scene is None:
            return None
        coll = {
            "node": "nodes", "frame": "frames", "area": "areas",
            "link": "links", "poly": "polygons",
        }.get(kind)
        if not coll:
            return None
        return getattr(scene, coll, {}).get(eid)