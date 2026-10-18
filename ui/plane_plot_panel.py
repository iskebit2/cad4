# ui/plane_plot_panel.py
"""
PlanePlotPanel — bir Plane'i 2D canvas'ta gösterir.

- open(scene=..., plane=...)
- Assoc elemanlar 2D'de çizilir
- Seçim, pan, zoom, view rotation
- Info paneli + Assoc listesi (opsiyonel)
- Aksiyonlar: Uygula (pending), Assoc yenile
"""

from __future__ import annotations

import logging
from typing import Optional

import imgui

from domain.plane import Plane, ASSOC_KINDS, ChangeOp
from ui.widgets.plane_2d_view import Plane2DView
from ui.widgets.frame_assoc import FrameAssocWidget

logger = logging.getLogger(__name__)


class PlanePlotPanel:

    PANEL_W = 1200
    PANEL_H = 740
    HEADER_H = 40
    BOTTOM_H = 56

    def __init__(self):
        self.app = None
        self.scene = None
        self.plane: Optional[Plane] = None

        self.view2d = Plane2DView()
        self.selected = set()       # (kind, id)

        # Widget görünürlüğü
        self.show_info = True
        self.show_assoc = True

        self.visible = False

        # "Uygula" raporu (bir frame boyunca gösterilir)
        self._last_report = None

    # ------------------------------------------------------------------
    #  Context helpers
    # ------------------------------------------------------------------
    def _scene(self):
        if self.scene is not None:
            return self.scene
        if self.app and self.app.engine is not None:
            return self.app.engine.scene
        if self.app and self.app.current_project is not None:
            return self.app.current_project.scene
        return None

    # ------------------------------------------------------------------
    #  open / close
    # ------------------------------------------------------------------
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
        self.visible = True

    def _read_mods(self):
        """GLFW'den anlık ctrl/shift durumunu oku."""
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
        
    def close(self):
        self.visible = False

    def set_plane(self, plane: Plane):
        self.plane = plane
        self.selected.clear()
        sc = self._scene()
        if sc is not None:
            self.view2d.load_plane(plane, sc)

    def refresh(self):
        sc = self._scene()
        if self.plane is not None and sc is not None:
            self.view2d.load_plane(self.plane, sc)

    # ------------------------------------------------------------------
    #  draw
    # ------------------------------------------------------------------
    def draw(self):
        if not self.visible:
            return
        if self.plane is None:
            # Panel açık ama plane yok
            imgui.set_next_window_size(400, 120, imgui.FIRST_USE_EVER)
            imgui.set_next_window_position(200, 200, imgui.FIRST_USE_EVER)
            expanded, opened = imgui.begin("Plane Plot", True)
            try:
                if not opened:
                    self.visible = False
                    return
                imgui.text_colored("Plane seçilmedi.", 0.7, 0.7, 0.7, 1.0)
                imgui.text_colored("Plane Manager'dan bir plane seç.", 0.5, 0.5, 0.5, 1.0)
            finally:
                imgui.end()
            return

        imgui.set_next_window_size(self.PANEL_W, self.PANEL_H, imgui.FIRST_USE_EVER)
        imgui.set_next_window_position(40, 60, imgui.FIRST_USE_EVER)

        expanded, opened = imgui.begin(f"Plane Plot — {self.plane.name}", True)
        try:
            if not opened:
                self.visible = False
                return
            if not expanded:
                return

            self._draw_header()
            imgui.separator()

            self._draw_body()
            imgui.separator()

            self._draw_bottom()

            

        finally:
            imgui.end()

    # ------------------------------------------------------------------
    def _draw_header(self):
        p = self.plane
        imgui.text_colored(f"Plane: {p.name}", 0.9, 0.85, 0.5, 1.0)
        imgui.same_line(320)
        imgui.text_colored(
            f"depth=[-{p.depth_minus:.0f},+{p.depth_plus:.0f}]",
            0.7, 0.75, 0.8, 1.0
        )
        imgui.same_line(500)
        total = sum(len(s) for s in p.associated.values())
        imgui.text_colored(f"assoc={total}", 0.6, 0.85, 0.7, 1.0)

        # View butonları (sağ)
        imgui.same_line(700)
        if imgui.button("↺90"):
            self.view2d.rotate_view(-90)
        imgui.same_line()
        if imgui.button("↻90"):
            self.view2d.rotate_view(90)
        imgui.same_line()
        if imgui.button("Reset"):
            self.view2d.rotate_view(0, absolute=True)
        imgui.same_line()
        if imgui.button("+"):
            self.view2d.zoom_at_center(1.15)
        imgui.same_line()
        if imgui.button("-"):
            self.view2d.zoom_at_center(1 / 1.15)
        imgui.same_line()
        if imgui.button("Fit"):
            self.view2d.fit_to_content()

        imgui.same_line()
        _, self.view2d.show_grid = imgui.checkbox("Grid", self.view2d.show_grid)
        imgui.same_line()
        _, self.show_info = imgui.checkbox("Info", self.show_info)
        imgui.same_line()
        _, self.show_assoc = imgui.checkbox("Assoc", self.show_assoc)

    # ------------------------------------------------------------------
    def _draw_body(self):
        # Sağ panel genişliği
        right_w = 250

        avail = imgui.get_content_region_available()
        canvas_w = max(400, avail[0] - right_w - 20)
        canvas_h = self.PANEL_H - self.HEADER_H - self.BOTTOM_H - 60

        # --- Canvas ---
        imgui.begin_child("pp_canvas", width=canvas_w, height=canvas_h, border=True)
        self._draw_canvas(canvas_w, canvas_h)
        imgui.end_child()

        # --- Sağ paneller ---
        if right_w > 0:
            imgui.same_line()
            imgui.begin_child("pp_right", width=right_w, height=canvas_h, border=False)

            if self.show_info:
                imgui.begin_child("pp_info", width=0, height=200, border=True)
                self._draw_info()
                imgui.end_child()
                imgui.spacing()

            if self.show_assoc:
                imgui.begin_child("pp_assoc", width=0, height=0, border=True)
                self._draw_assoc()
                imgui.end_child()

            imgui.end_child()

    def _draw_canvas(self, canvas_w, canvas_h):
        imgui.text_colored("2D Plane View (plane.to_2d)", 0.8, 0.85, 0.95, 1.0)
        imgui.same_line()
        imgui.text_colored(f"[rot {self.view2d.view_rotation:+.0f}°]",
                           0.6, 0.7, 0.8, 1.0)

        pos = imgui.get_cursor_screen_pos()
        canvas_pos = (pos.x, pos.y)

        imgui.invisible_button("##pp_canvas_area", canvas_w, canvas_h)

        dl = imgui.get_window_draw_list()
        self.view2d.selected = self.selected
        self.view2d.draw(imgui, dl, canvas_pos, (canvas_w, canvas_h))

        # Seçim / tıklama sonuçları
        if self.view2d.clicked is not None:
            ctrl, shift = self.view2d._get_mods()
            hit = self.view2d.clicked
            if ctrl:
                if hit in self.selected:
                    self.selected.discard(hit)
                else:
                    self.selected.add(hit)
            elif shift:
                self.selected.add(hit)
            else:
                self.selected = {hit}
            self.view2d.clicked = None

        if self.view2d.clicked_empty:
            if not imgui.get_io().key_ctrl:
                self.selected.clear()
            self.view2d.clicked_empty = False

        # HUD
        imgui.spacing()
        imgui.text_colored(
            f"Zoom: {self.view2d.zoom:.2f}  |  "
            f"Sol tık: seç | Ctrl: çoklu | Orta/Sağ: pan | Tekerlek: zoom",
            0.55, 0.55, 0.55, 1.0
        )

    def _draw_info(self):
        p = self.plane
        imgui.text_colored("Info", 0.8, 0.85, 0.95, 1.0)
        o, n = p.origin, p.normal
        imgui.text(f"O: ({o[0]:.0f}, {o[1]:.0f}, {o[2]:.0f})")
        imgui.text(f"N: ({n[0]:.2f}, {n[1]:.2f}, {n[2]:.2f})")
        imgui.spacing()

        bounds_changed = False
        imgui.text_colored("Sınır (u/v)", 0.75, 0.8, 0.9, 1.0)
        imgui.push_item_width(120)

        # --- u min ---
        imgui.push_id("u_min")
        ch, val = imgui.input_float("u min", p.u_min if p.u_min is not None else 0.0)
        imgui.pop_id()
        if ch:
            p.u_min = val
            bounds_changed = True

        # --- u max ---
        imgui.push_id("u_max")
        ch, val = imgui.input_float("u max", p.u_max if p.u_max is not None else 0.0)
        imgui.pop_id()
        if ch:
            p.u_max = val
            bounds_changed = True

        # --- v min ---
        imgui.push_id("v_min")
        ch, val = imgui.input_float("v min", p.v_min if p.v_min is not None else 0.0)
        imgui.pop_id()
        if ch:
            p.v_min = val
            bounds_changed = True

        # --- v max ---
        imgui.push_id("v_max")
        ch, val = imgui.input_float("v max", p.v_max if p.v_max is not None else 0.0)
        imgui.pop_id()
        if ch:
            p.v_max = val
            bounds_changed = True

        imgui.spacing()
        imgui.text_colored("Derinlik", 0.75, 0.8, 0.9, 1.0)

        # --- depth_minus ---
        imgui.push_id("d_minus")
        ch, val = imgui.input_float("depth -", p.depth_minus)
        imgui.pop_id()
        if ch and val >= 0:
            p.depth_minus = val
            bounds_changed = True

        # --- depth_plus ---
        imgui.push_id("d_plus")
        ch, val = imgui.input_float("depth +", p.depth_plus)
        imgui.pop_id()
        if ch and val >= 0:
            p.depth_plus = val
            bounds_changed = True

        imgui.pop_item_width()

        # --- "Sınır yok" checkbox'ları (tuple dönüş!) ---
        no_u = (p.u_min is None and p.u_max is None)
        imgui.push_id("no_u")
        changed, _ = imgui.checkbox("u sınırı yok", no_u)
        imgui.pop_id()
        if changed:
            if no_u:
                # False → True: sınırları kaldır
                p.u_min = p.u_max = None
            else:
                # True → False: sınırları varsayılan ata
                p.u_min, p.u_max = -5000.0, 5000.0
            bounds_changed = True

        no_v = (p.v_min is None and p.v_max is None)
        imgui.push_id("no_v")
        changed, _ = imgui.checkbox("v sınırı yok", no_v)
        imgui.pop_id()
        if changed:
            if no_v:
                p.v_min = p.v_max = None
            else:
                p.v_min, p.v_max = -5000.0, 5000.0
            bounds_changed = True

        # Değişiklik varsa assoc'u bir sonraki karede yenile (bu karede değil)
        if bounds_changed:
            self._bounds_dirty = True

    def _draw_assoc(self):
        p = self.plane
        imgui.text_colored("Assoc", 0.8, 0.85, 0.95, 1.0)
        for kind in ASSOC_KINDS:
            n_a = len(p.associated.get(kind, set()))
            n_e = len(p.excluded.get(kind, set()))
            if n_a or n_e:
                imgui.text_colored(f"{kind:6s}: {n_a}", 0.75, 0.85, 0.9, 1.0)
                if n_e:
                    imgui.same_line()
                    imgui.text_colored(f"(exc {n_e})", 0.9, 0.6, 0.5, 1.0)
        imgui.spacing()
        imgui.text_colored(f"Pending: {len(p.pending)}", 0.9, 0.85, 0.5, 1.0)

        imgui.spacing()
        imgui.text_colored("Seçili", 0.8, 0.85, 0.95, 1.0)
        imgui.text(f"{len(self.selected)} eleman")
        if self.selected:
            for kind, eid in sorted(self.selected):
                imgui.text_colored(f"  {kind}#{eid}", 0.7, 0.8, 0.9, 1.0)

    # ------------------------------------------------------------------
    def _draw_bottom(self):
        p = self.plane
        n_sel = len(self.selected)
        n_pending = len(p.pending)

        # Seçili elemanları excluded'a at
        if n_sel > 0:
            if imgui.button(f"Seçili {n_sel} elemanı çıkar", width=200, height=26):
                self._do_remove_selected()
        else:
            imgui.push_style_color(imgui.COLOR_BUTTON, 0.25, 0.25, 0.25, 1.0)
            imgui.button("Seçili yok", width=200, height=26)
            imgui.pop_style_color(1)

        imgui.same_line()
        if imgui.button("Assoc Yenile", width=140, height=26):
            sc = self._scene()
            if sc is not None:
                p.refresh_assoc(sc)
                self.refresh()
                logger.info(f"[PlanePlot] '{p.name}' assoc yenilendi.")

        imgui.same_line()
        if n_pending > 0:
            imgui.push_style_color(imgui.COLOR_BUTTON, 0.2, 0.5, 0.2, 1.0)
            if imgui.button(f"Uygula ({n_pending})", width=160, height=26):
                self._do_apply_pending()
            imgui.pop_style_color(1)
        else:
            imgui.push_style_color(imgui.COLOR_BUTTON, 0.25, 0.25, 0.25, 1.0)
            imgui.button("Uygula (0)", width=160, height=26)
            imgui.pop_style_color(1)

        imgui.same_line()
        imgui.text_colored(
            f"assoc={sum(len(s) for s in p.associated.values())}  "
            f"excluded={sum(len(s) for s in p.excluded.values())}  "
            f"pending={n_pending}",
            0.6, 0.65, 0.7, 1.0
        )

        if self._last_report:
            imgui.spacing()
            r = self._last_report
            imgui.text_colored(
                f"Son uygulama: +{r['added']} ~{r['modified']} -{r['deleted']}"
                + (f"  ({len(r['errors'])} hata)" if r.get("errors") else ""),
                0.7, 0.85, 0.7, 1.0
            )

    def _do_remove_selected(self):
        p = self.plane
        for kind, eid in list(self.selected):
            p.remove_assoc(kind, int(eid), permanent=True)
        logger.info(f"[PlanePlot] {len(self.selected)} eleman excluded'a atıldı.")
        self.selected.clear()
        self.refresh()

    def _do_apply_pending(self):
        p = self.plane
        sc = self._scene()
        if sc is None:
            return
        report = p.apply_pending(sc)
        self._last_report = report
        logger.info(f"[PlanePlot] Pending uygulandı: {report}")
        self.refresh()

    # ------------------------------------------------------------------
    @staticmethod
    def _fv(v):
        return "None" if v is None else f"{v:.0f}"