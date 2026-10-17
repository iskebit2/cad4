# ui/polygon_edit_panel.py

import logging
import imgui

from ui.base_panel import BasePanel
from ui.widgets.polygon_2d_view import Polygon2DView
from ui.widgets.polygon_info import PolygonInfoWidget
from ui.widgets.frame_assoc import FrameAssocWidget

logger = logging.getLogger(__name__)


class PolygonEditPanel(BasePanel):

    # --- Sabit boyutlar (px) ---
    PANEL_W = 1200
    PANEL_H = 700

    HEADER_H = 36
    INFO_H = 150
    ASSOC_H = 180
    ACTIONS_H = 72

    CANVAS_W = 750
    CANVAS_H = 420

    RIGHT_W = 410  # 750 + 410 = 1160 px (Kenar boşluklarıyla 1200 içine tam oturur)

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
        super().open()

    def set_polygon(self, poly):
        self.selected_poly = poly
        self.selected_fids.clear()
        if self.scene and poly:
            self.view2d.load_polygon(poly, self.scene)
            self.view2d.selected_fids = self.selected_fids

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

        # === ÜST: Başlık (sabit yükseklik) ===
        self._draw_header(poly)
        imgui.spacing()

        # === ORTA: Sol canvas + sağ bilgi/liste ===
        self._draw_body(poly)
        imgui.spacing()

        # === ALT: Aksiyonlar ===
        self._draw_actions(poly)

    # ------------------------------------------------------------------
    def _draw_header(self, poly):
        poly_type = getattr(poly, "poly_type", None)
        type_str = getattr(poly_type, "name", str(poly_type))

        imgui.text_colored(f"ID: {poly.unique_id}", 0.9, 0.8, 0.5, 1.0)
        imgui.same_line(140)
        imgui.text_colored(f"Tip: {type_str}", 0.6, 0.85, 0.95, 1.0)
        imgui.same_line(420)
        imgui.text_colored(f"Label: {poly.label or '-'}", 0.7, 0.7, 0.7, 1.0)

    # ------------------------------------------------------------------
    def _draw_body(self, poly):
        """
        Yatay yerleşim:
            Sol: canvas (CANVAS_W x CANVAS_H)
            Sağ: bilgi + assoc liste (RIGHT_W)
        """
        body_height = self.CANVAS_H + 35

        # Sol: 2D Canvas
        imgui.begin_child("canvas_child", width=self.CANVAS_W,
                          height=body_height, border=False)

        imgui.text_colored("2D ÖNİZLEME (poly düzleminden)",
                           0.8, 0.85, 0.95, 1.0)
        imgui.spacing()

        # Canvas için ImGui alanı
        pos = imgui.get_cursor_screen_pos()
        canvas_pos = (pos.x, pos.y)

        imgui.invisible_button("##canvas_2d", self.CANVAS_W, self.CANVAS_H)

        # Draw list ile çiz
        draw_list = imgui.get_window_draw_list()
        self.view2d.selected_fids = self.selected_fids
        self.view2d.draw(imgui, draw_list, canvas_pos,
                         (self.CANVAS_W, self.CANVAS_H))

        # Canvas tıklaması → frame seçimi
        if self.view2d.clicked_fid is not None:
            ctrl = imgui.get_io().key_ctrl
            if ctrl:
                if self.view2d.clicked_fid in self.selected_fids:
                    self.selected_fids.discard(self.view2d.clicked_fid)
                else:
                    self.selected_fids.add(self.view2d.clicked_fid)
            else:
                self.selected_fids = {self.view2d.clicked_fid}
            self.view2d.clicked_fid = None

        # Zoom/Pan bilgisi
        imgui.spacing()
        imgui.text_colored(
            f"Zoom: {self.view2d.zoom:.2f}  |  "
            f"Fare: sol tık seç  |  Ctrl+tık çoklu seç",
            0.6, 0.6, 0.6, 1.0
        )

        imgui.end_child()

        imgui.same_line()

        # Sağ: Bilgi + Assoc Liste (dikey)
        imgui.begin_child("right_child", width=self.RIGHT_W,
                          height=body_height, border=False)

        # --- Poly Bilgi ---
        imgui.begin_child("info_child", width=self.RIGHT_W, height=self.INFO_H, border=True)
        PolygonInfoWidget.draw(poly, self.view2d.plane)
        imgui.end_child()

        imgui.spacing()

        # --- Assoc Frame Listesi ---
        imgui.text_colored("ASSOC FRAME'LER", 0.8, 0.85, 0.95, 1.0)
        imgui.same_line()
        n_assoc = len(getattr(poly, "associated_frame_ids", []))
        imgui.text_colored(f"({n_assoc})", 0.6, 0.75, 0.9, 1.0)

        imgui.begin_child("assoc_child", width=self.RIGHT_W, height=self.ASSOC_H, border=True)
        self._draw_assoc_list(poly)
        imgui.end_child()

        imgui.end_child()

    # ------------------------------------------------------------------
    def _draw_assoc_list(self, poly):
        """Kompakt assoc liste — sadece scroll'lu satırlar."""
        action, payload = FrameAssocWidget.draw(poly, self.scene, self.selected_fids)
        
        # Widget'tan gelen aksiyonları yönet
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
    def _draw_actions(self, poly):
        """Alt aksiyonlar — 2 satır kompakt."""
        n_sel = len(self.selected_fids)
        n_assoc = len(getattr(poly, "associated_frame_ids", []))

        # === 1. Satır: Assoc düzenleme ===
        imgui.begin_child("actions_row1", width=0, height=32, border=False)

        # Seçili frame'leri çıkar
        if n_sel > 0:
            if imgui.button(f"Seçili {n_sel} frame'i çıkar", width=200, height=28):
                self._remove_selected_frames(poly)
        else:
            imgui.push_style_color(imgui.COLOR_BUTTON, 0.25, 0.25, 0.25, 1.0)
            imgui.button("Seçili frame yok", width=200, height=28)
            imgui.pop_style_color(1)

        imgui.same_line()

        # Tümünü çıkar
        if imgui.button("Tümünü çıkar", width=140, height=28):
            poly.associated_frame_ids = []
            self.selected_fids.clear()
            self.refresh()
            logger.info(f"[PolyEdit] Tüm assoc frame'ler çıkarıldı (poly={poly.unique_id}).")

        imgui.same_line(360)
        imgui.text_colored(
            f"Toplam assoc: {n_assoc}  |  Seçili: {n_sel}",
            0.7, 0.7, 0.7, 1.0
        )

        imgui.end_child()

        # === 2. Satır: Model işlemleri ===
        imgui.begin_child("actions_row2", width=0, height=32, border=False)

        if imgui.button("Modelden Ekle", width=150, height=28):
            if self.on_apply_assoc:
                self.on_apply_assoc("model_add", None)

        imgui.same_line()

        if imgui.button("Modelden Replace", width=160, height=28):
            if self.on_apply_assoc:
                self.on_apply_assoc("model_replace", None)

        imgui.same_line(340)

        if imgui.button("Align", width=100, height=28):
            if callable(self.on_align):
                self.on_align([poly])
                self.refresh()

        imgui.same_line()

        if imgui.button("Mesh", width=100, height=28):
            if callable(self.on_mesh):
                self.on_mesh(poly)

        imgui.same_line()

        if imgui.button("Dağıt", width=100, height=28):
            if callable(self.on_distribute):
                self.on_distribute(poly)

        imgui.end_child()

    # ------------------------------------------------------------------
    def _remove_selected_frames(self, poly):
        """Seçili frame'leri assoc listesinden çıkar."""
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