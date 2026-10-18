# ui/polygon_edit_panel.py

import logging
import math
import imgui

from ui.base_panel import BasePanel
from ui.widgets.polygon_2d_view import Polygon2DView
from ui.widgets.polygon_info import PolygonInfoWidget
from ui.widgets.frame_assoc import FrameAssocWidget

logger = logging.getLogger(__name__)


class PolygonEditPanel(BasePanel):

    # --- Sabit boyutlar (px) ---
    PANEL_W = 1200
    PANEL_H = 760

    HEADER_H = 40
    BOTTOM_H = 72

    # Sağ panel genişlikleri (toggle'lara göre)
    INFO_W = 380
    ASSOC_W = 380

    def __init__(self,
                 on_align=None,
                 on_distribute=None,
                 on_mesh=None,
                 on_apply_assoc=None):
        super().__init__(
            title="Polygon Edit",
            width=self.PANEL_W,
            height=self.PANEL_H,
            pos_first_use=(100, 60),
            closable=True,
        )
        self.scene = None
        self.selected_poly = None
        self.on_align = on_align
        self.on_distribute = on_distribute
        self.on_mesh = on_mesh
        self.on_apply_assoc = on_apply_assoc

        self.view2d = Polygon2DView()
        self.selected_fids = set()

        # Widget toggle durumları (başlık barından yönetilir)
        self.show_info = True
        self.show_assoc = True
        self.show_grid = True

    # ------------------------------------------------------------------
    def open(self, scene=None, poly=None):
        if scene is not None:
            self.scene = scene
        if poly is not None:
            self.selected_poly = poly
            self.selected_fids.clear()
            if self.scene:
                self.view2d.load_polygon(poly, self.scene)
                self.view2d.selected_fids = self.selected_fids
                self.view2d.fit_to_content()
        super().open()

    def set_polygon(self, poly):
        self.selected_poly = poly
        self.selected_fids.clear()
        if self.scene and poly:
            self.view2d.load_polygon(poly, self.scene)
            self.view2d.selected_fids = self.selected_fids
            self.view2d.fit_to_content()

    def refresh(self):
        if self.scene and self.selected_poly:
            self.view2d.load_polygon(self.selected_poly, self.scene)
            self.view2d.selected_fids = self.selected_fids

    # ------------------------------------------------------------------
    def draw_content(self):
        if self.selected_poly is None:
            imgui.text_colored("Polygon seçilmedi.", 0.7, 0.7, 0.7, 1.0)
            imgui.spacing()
            imgui.text_colored("Sahneden bir polygon seçin.", 0.5, 0.5, 0.5, 1.0)
            return

        poly = self.selected_poly

        # === BAŞLIK BAR (butonlar + toggle) ===
        self._draw_header_bar(poly)
        imgui.spacing()

        # === ORTA: Canvas + (opsiyonel) sağ paneller ===
        self._draw_body(poly)

        # === ALT BAR ===
        self._draw_bottom_bar(poly)

    # ------------------------------------------------------------------
    #  HEADER BAR
    # ------------------------------------------------------------------
    def _draw_header_bar(self, poly):
        poly_type = getattr(poly, "poly_type", None)
        type_str = getattr(poly_type, "name", str(poly_type))

        imgui.begin_child("header_bar", width=0, height=self.HEADER_H, border=True)

        # Sol: kimlik bilgisi
        imgui.text_colored(f"ID: {poly.unique_id}", 0.9, 0.8, 0.5, 1.0)
        imgui.same_line(140)
        imgui.text_colored(f"Tip: {type_str}", 0.6, 0.85, 0.95, 1.0)
        imgui.same_line(300)
        imgui.text_colored(f"Label: {poly.label or '-'}", 0.7, 0.7, 0.7, 1.0)

        # Sağ: toggle butonları + view kontrolleri
        imgui.same_line(560)

        # Orthogonal döndürme (sadece view)
        if imgui.button("↺ 90", width=50, height=24):
            self.view2d.rotate_view(-90)
        imgui.same_line()
        if imgui.button("↻ 90", width=50, height=24):
            self.view2d.rotate_view(90)
        imgui.same_line()
        if imgui.button("⟲ Reset", width=60, height=24):
            self.view2d.rotate_view(0, absolute=True)
        imgui.same_line()

        # Zoom kontrolleri
        if imgui.button("+", width=28, height=24):
            self.view2d.zoom_at_center(1.15)
        imgui.same_line()
        if imgui.button("-", width=28, height=24):
            self.view2d.zoom_at_center(1 / 1.15)
        imgui.same_line()
        if imgui.button("Fit", width=40, height=24):
            self.view2d.fit_to_content()
        imgui.same_line()

        # Grid toggle
        changed, self.show_grid = imgui.checkbox("Grid", self.show_grid)
        self.view2d.show_grid = self.show_grid
        imgui.same_line()

        # Widget toggle'ları
        changed, self.show_info = imgui.checkbox("Info", self.show_info)
        imgui.same_line()
        changed, self.show_assoc = imgui.checkbox("Assoc", self.show_assoc)

        imgui.end_child()

    # ------------------------------------------------------------------
    #  BODY (canvas + sağ paneller)
    # ------------------------------------------------------------------
    def _draw_body(self, poly):
        # Sağ panel genişliği toggle durumuna göre
        right_w = 0
        if self.show_info:
            right_w += self.INFO_W
        if self.show_assoc:
            right_w += self.ASSOC_W

        # Canvas genişliği: panel içeriğine göre (kenar boşlukları ~20)
        avail_w = imgui.get_content_region_available()[0]
        canvas_w = max(300, avail_w - right_w - 20)
        canvas_h = self.PANEL_H - self.HEADER_H - self.BOTTOM_H - 80

        # --- Sol: Canvas ---
        imgui.begin_child("canvas_child", width=canvas_w,
                          height=canvas_h, border=True)
        self._draw_canvas(poly, canvas_w, canvas_h)
        imgui.end_child()

        # --- Sağ: Info + Assoc (toggle) ---
        if right_w > 0:
            imgui.same_line()
            imgui.begin_child("right_child", width=right_w,
                              height=canvas_h, border=False)

            if self.show_info:
                imgui.begin_child("info_child", width=self.INFO_W,
                                  height=150, border=True)
                PolygonInfoWidget.draw(poly, self.view2d.plane)
                imgui.end_child()
                imgui.spacing()

            if self.show_assoc:
                imgui.text_colored("ASSOC FRAME'LER", 0.8, 0.85, 0.95, 1.0)
                imgui.same_line()
                n_assoc = len(getattr(poly, "associated_frame_ids", []))
                imgui.text_colored(f"({n_assoc})", 0.6, 0.75, 0.9, 1.0)

                imgui.begin_child("assoc_child", width=self.ASSOC_W,
                                  height=0, border=True)
                self._draw_assoc_list(poly)
                imgui.end_child()

            imgui.end_child()

    def _draw_canvas(self, poly, canvas_w, canvas_h):
        imgui.text_colored("2D ÖNİZLEME (poly düzleminden)",
                           0.8, 0.85, 0.95, 1.0)
        imgui.same_line()
        rot = self.view2d.view_rotation
        imgui.text_colored(f"[rot {rot:+.0f}°]", 0.6, 0.7, 0.8, 1.0)

        pos = imgui.get_cursor_screen_pos()
        canvas_pos = (pos.x, pos.y)

        imgui.invisible_button("##canvas_2d", canvas_w, canvas_h)

        draw_list = imgui.get_window_draw_list()
        self.view2d.selected_fids = self.selected_fids
        self.view2d.draw(imgui, draw_list, canvas_pos, (canvas_w, canvas_h))

        # Canvas tıklaması → seçim
        fid = self.view2d.clicked_fid
        if fid is not None:
            io = imgui.get_io()
            ctrl = io.key_ctrl
            shift = io.key_shift
            if ctrl:
                if fid in self.selected_fids:
                    self.selected_fids.discard(fid)
                else:
                    self.selected_fids.add(fid)
            elif shift:
                self.selected_fids.add(fid)
            else:
                self.selected_fids = {fid}
            self.view2d.clicked_fid = None

        # Boşluğa tık → temizle
        if getattr(self.view2d, "clicked_empty", False):
            if not imgui.get_io().key_ctrl:
                self.selected_fids.clear()
            self.view2d.clicked_empty = False

        # HUD
        imgui.spacing()
        imgui.text_colored(
            f"Zoom: {self.view2d.zoom:.2f}  |  "
            "Sol tık: seç  |  Ctrl+tık: çoklu  |  "
            "Orta tuş / Space+sol: pan  |  Tekerlek: zoom",
            0.55, 0.55, 0.55, 1.0
        )

    # ------------------------------------------------------------------
    def _draw_assoc_list(self, poly):
        action, payload = FrameAssocWidget.draw(poly, self.scene, self.selected_fids)
        if action == "focus":
            logger.info(f"[PolyEdit] Sahneye odaklanıldı: {payload}")
        elif action == "isolate":
            logger.info(f"[PolyEdit] İzole et: {payload}")
        elif action == "remove":
            if payload in poly.associated_frame_ids:
                poly.associated_frame_ids.remove(payload)
                self.selected_fids.discard(payload)
                self.refresh()
        elif action == "remove_selected":
            self._remove_selected_frames(poly)

    # ------------------------------------------------------------------
    #  BOTTOM BAR
    # ------------------------------------------------------------------
    def _draw_bottom_bar(self, poly):
        n_sel = len(self.selected_fids)
        n_assoc = len(getattr(poly, "associated_frame_ids", []))

        imgui.begin_child("bottom_bar", width=0, height=self.BOTTOM_H, border=True)

        # === 1. Satır: Assoc düzenleme ===
        if n_sel > 0:
            if imgui.button(f"Seçili {n_sel} frame'i çıkar", width=200, height=26):
                self._remove_selected_frames(poly)
        else:
            imgui.push_style_color(imgui.COLOR_BUTTON, 0.25, 0.25, 0.25, 1.0)
            imgui.button("Seçili frame yok", width=200, height=26)
            imgui.pop_style_color(1)

        imgui.same_line()
        if imgui.button("Tümünü çıkar", width=140, height=26):
            poly.associated_frame_ids = []
            self.selected_fids.clear()
            self.refresh()
            logger.info(f"[PolyEdit] Tüm assoc frame'ler çıkarıldı (poly={poly.unique_id}).")

        imgui.same_line(360)
        imgui.text_colored(
            f"Toplam assoc: {n_assoc}  |  Seçili: {n_sel}",
            0.7, 0.7, 0.7, 1.0
        )

        # === 2. Satır: Model işlemleri ===
        if imgui.button("Modelden Ekle", width=150, height=26):
            if self.on_apply_assoc:
                self.on_apply_assoc("model_add", None)

        imgui.same_line()
        if imgui.button("Modelden Replace", width=160, height=26):
            if self.on_apply_assoc:
                self.on_apply_assoc("model_replace", None)

        imgui.same_line(340)
        if imgui.button("Align", width=100, height=26):
            if callable(self.on_align):
                self.on_align([poly])
                self.refresh()

        imgui.same_line()
        if imgui.button("Mesh", width=100, height=26):
            if callable(self.on_mesh):
                self.on_mesh(poly)

        imgui.same_line()
        if imgui.button("Dağıt", width=100, height=26):
            if callable(self.on_distribute):
                self.on_distribute(poly)

        imgui.end_child()

    # ------------------------------------------------------------------
    def _remove_selected_frames(self, poly):
        assoc = list(getattr(poly, "associated_frame_ids", []))
        n_removed = 0
        for fid in list(self.selected_fids):
            if fid in assoc:
                assoc.remove(fid)
                n_removed += 1
        poly.associated_frame_ids = assoc
        self.selected_fids.clear()
        self.refresh()
        logger.info(f"[PolyEdit] {n_removed} frame çıkarıldı (poly={poly.unique_id}).")