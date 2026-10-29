# ui/sd_convert_panel.py
"""
SD Section → Area Dönüşüm Paneli.

Akış:
  1. Seçili SD frame'i tespit et
  2. "Area'ya Çevir" → sd_frame_to_areas ile area listesi üret (sahneye EKLEME)
  3. 2D canvas'ta önizleme (tıkla-seç, Ctrl ile çoklu seçim)
  4. Seçili / tümünü sil
  5. "Modele Aktar" → önce node'lar, sonra area'lar sahneye eklenir
"""
from __future__ import annotations

import math

from pyglm import glm
from imgui_bundle import imgui

from domain.definition import SectionType
from domain.element import Area, Frame, Node
from geometry.sd_to_areas import sd_frame_to_areas
from logging_config import CadLogger
from ui.base_panel import BasePanel

logger = CadLogger.get(__name__)


# ============================================================
# YARDIMCILAR
# ============================================================
def _dist_point_segment(p, a, b):
    px, py = p; ax, ay = a; bx, by = b
    dx = bx - ax; dy = by - ay
    L2 = dx*dx + dy*dy
    if L2 < 1e-9:
        return math.hypot(px-ax, py-ay)
    t = ((px-ax)*dx + (py-ay)*dy) / L2
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax+dx*t), py - (ay+dy*t))

def _node_key(nd: Node) -> tuple[float, float, float]:
    """Aynı 3D konumdaki node'ları birleştirmek için anahtar."""
    return (round(nd.x, 3), round(nd.y, 3), round(nd.z, 3))


def _dedupe_area_nodes(areas: list[Area]) -> list[Node]:
    """
    Aynı konumdaki node'ları tek Node nesnesine indirger.
    Area.nodes listelerini bu paylaşılan Node'larla günceller.
    Returns: paylaşılan Node listesi (tekilleştirilmiş).
    """
    shared: dict[tuple[float, float, float], Node] = {}
    for area in areas:
        new_nodes = []
        for nd in area.nodes:
            key = _node_key(nd)
            if key not in shared:
                shared[key] = nd
            new_nodes.append(shared[key])
        area.nodes = new_nodes
    return list(shared.values())


def _color_u32(r: float, g: float, b: float, a: float = 1.0) -> int:
    return imgui.get_color_u32(imgui.ImVec4(r, g, b, a))


# ============================================================
# PANEL
# ============================================================
class SDConvertPanel(BasePanel):
    def __init__(self):
        self.visible = False
        self.app = None

        # Ayarlar
        self.thickness: float = 250.0       # mm
        self.hide_original: bool = True
        self.delete_after_commit: bool = True   # commit sonrası önizlemeyi temizle

        # Kaynak
        self._last_frame_id: int | None = None

        # Önizleme (sahneye EKLENMEMİŞ)
        self._preview_frame: Frame | None = None
        self._preview_areas: list[Area] = []
        self._preview_nodes: list[Node] = []
        self._preview_selected: set[int] = set()   # area.unique_id

        # 2D canvas bounds (çizim + hit-test için)
        self._canvas_bounds: tuple[float, float, float, float] | None = None  # (umin,umax,vmin,vmax)
        self._canvas_scale: float = 1.0
        self._canvas_origin: tuple[float, float] = (0.0, 0.0)   # screen pos

        # Bilgi
        self._last_error: str = ""

        # Kaynak
        self._preview_frame: Frame | None = None
        self._polygon_points: list[tuple[float, float]] = []   # (u, v) SD koordinatları
        self._edge_selected: set[int] = set()                   # seçili kenar index'leri (0..N-1)

        # Canvas
        self._canvas_origin: tuple[float, float] = (0, 0)
        self._canvas_size: tuple[float, float] = (0, 0)
        self._canvas_scale: float = 1.0
        self._canvas_offset: tuple[float, float] = (0.0, 0.0)   # (cx, cy)
        self._hover_edge: int | None = None

    # -----------------------------------------------------------------
    # LIFECYCLE
    # -----------------------------------------------------------------
    def open(self):
        self.visible = True

    def close(self):
        self.visible = False
        self._clear_preview()

    def _clear_preview(self):
        self._preview_frame = None
        self._preview_areas.clear()
        self._preview_nodes.clear()
        self._preview_selected.clear()
        self._canvas_bounds = None
        self._last_error = ""

    # -----------------------------------------------------------------
    # SEÇİLİ FRAME
    # -----------------------------------------------------------------
    def _get_target_frame(self) -> Frame | None:
        if not self.app or not self.app.engine or not self.app.engine.scene:
            return None
        scn = self.app.engine.scene
        for e in scn.get_selected():
            if isinstance(e, Frame) and self._is_sd_frame(e):
                return e
        return None

    @staticmethod
    def _is_sd_frame(frame: Frame) -> bool:
        sec = frame.section
        return (
            sec is not None
            and sec.profile_type == SectionType.CUSTOM
            and getattr(sec, 'sd_section', None) is not None
        )

    @staticmethod
    def _get_polygon(frame: Frame):
        sd = getattr(frame.section, 'sd_section', None)
        if sd is None:
            return None
        return next(
            (s for s in sd.shapes
             if getattr(s, 'shape_kind', '') == 'Polygon' and len(s.points) >= 3),
            None,
        )

    # =================================================================
    # DRAW
    # =================================================================
    def draw(self):
        if not self.visible:
            return

        imgui.set_next_window_size(imgui.ImVec2(440, 720), imgui.Cond_.first_use_ever)
        expanded, opened = imgui.begin("SD → Area", True)
        try:
            self._draw_panel_content(expanded, opened)
        finally:
            imgui.end()

    def _draw_panel_content(self, expanded: bool, opened: bool):
        if not expanded:
            return
        if not opened:
            self.visible = False
            self._clear_preview()
            return

        # Kaynak frame var mı?
        frame = self._get_target_frame()

        if frame is None:
            imgui.text_colored(imgui.ImVec4(1.0, 0.6, 0.3, 1.0), "SD section'lı bir Frame seçin.")
            imgui.text_wrapped("3D viewport'ta SD kesitli bir çubuğa sol tıklayın.")
            return

        if frame.unique_id != self._last_frame_id:
            self._last_frame_id = frame.unique_id
            self._polygon_points.clear()
            self._edge_selected.clear()
            self._preview_frame = None

        poly = self._get_polygon(frame)
        if poly is None:
            imgui.text_colored(imgui.ImVec4(1.0, 0.4, 0.4, 1.0), "Bu frame'in SD polygon'u yok.")
            return

        # --- Bilgi ---
        imgui.text(f"Frame: {frame.label}")
        imgui.text(f"Kesit: {frame.section.name}")
        mat_name = frame.section.material.name if frame.section.material else "(yok)"
        imgui.text(f"Malzeme: {mat_name}")
        imgui.text(f"Köşe sayısı: {len(poly.points)}")
        imgui.separator()

        # --- "Kenarları Seç" butonu ---
        if not self._polygon_points:
            if imgui.button("Kenarları Seç", imgui.ImVec2(200, 32)):
                self._preview_frame = frame
                self._polygon_points = [(p.x, p.y) for p in poly.points]
                self._edge_selected.clear()
                logger.info(f"[SDPanel] {len(self._polygon_points)} kenar hazır")
            return

        # --- Kenar seçim arayüzü ---
        N = len(self._polygon_points)
        n_sel = len(self._edge_selected)
        imgui.text(f"Kenar: {N}  (Seçili: {n_sel})")

        changed, val = imgui.input_float("Kalınlık (mm)", self.thickness, 10.0, 1.0, "%.2f")
        if changed:
            self.thickness = max(1.0, val)

        imgui.separator()

        # --- Canvas ---
        self._draw_edges_canvas()

        imgui.separator()

        # --- Aksiyonlar ---
        if imgui.button("Tümünü Seç"):
            self._edge_selected = set(range(N))
        imgui.same_line()
        if imgui.button("Temizle"):
            self._edge_selected.clear()
        imgui.same_line()
        if imgui.button("İptal"):
            self._polygon_points.clear()
            self._edge_selected.clear()
            self._preview_frame = None
            return

        imgui.separator()

        can_convert = n_sel > 0
        if not can_convert:
            imgui.push_style_color(
                imgui.Col_.button, imgui.ImVec4(0.3, 0.3, 0.3, 1.0)
            )
        if imgui.button(f"Seçili {n_sel} Kenarı Area'ya Çevir", imgui.ImVec2(260, 32)) and can_convert:
            self._convert_edges_and_commit()
        if not can_convert:
            imgui.pop_style_color()

    # -----------------------------------------------------------------
    # KAYNAK (frame + polygon) UI
    # -----------------------------------------------------------------
    def _draw_source_ui(self):
        frame = self._get_target_frame()
        if frame is None:
            imgui.text_colored(imgui.ImVec4(1.0, 0.6, 0.3, 1.0), "SD section'lı bir Frame seçin.")
            imgui.text_wrapped(
                "3D viewport'ta SD kesitli bir çubuğa sol tıklayın. "
                "Seçim yaptıktan sonra bu panel otomatik güncellenir."
            )
            return

        if frame.unique_id != self._last_frame_id:
            self._last_frame_id = frame.unique_id
            logger.info(f"[SDPanel] hedef frame: {frame.label}")

        poly = self._get_polygon(frame)
        if poly is None:
            imgui.text_colored(imgui.ImVec4(1.0, 0.4, 0.4, 1.0), "Bu frame'in SD polygon'u yok.")
            return

        # --- Bilgi ---
        imgui.text(f"Frame: {frame.label}")
        imgui.text(f"Kesit: {frame.section.name}")
        mat_name = frame.section.material.name if frame.section.material else "(yok)"
        imgui.text(f"Malzeme: {mat_name}")
        imgui.text(f"Köşe sayısı: {len(poly.points)}")
        imgui.separator()

        # --- 2D kaynak polygon önizlemesi ---
        self._draw_source_polygon_2d(poly)

        imgui.separator()

        # --- Kalınlık + gizleme ---
        changed, val = imgui.input_float("Kalınlık (mm)", self.thickness, 10.0, 1.0, "%.2f")
        if changed:
            self.thickness = max(1.0, val)
        _, self.hide_original = imgui.checkbox("Orijinal frame'i gizle", self.hide_original)

        # --- Köşe koordinatları ---
        if imgui.collapsing_header("Köşe koordinatları (mm)"):
            imgui.begin_child(
                "##coords", imgui.ImVec2(0, 120), imgui.ChildFlags_.borders
            )
            for i, p in enumerate(poly.points):
                imgui.text(f"[{i:02d}]  u={p.x:10.2f}   v={p.y:10.2f}")
            imgui.end_child()

        # --- Hata ---
        if self._last_error:
            imgui.text_colored(imgui.ImVec4(1.0, 0.4, 0.4, 1.0), self._last_error)

        imgui.separator()

        # --- Buton ---
        if imgui.button("Area'ya Çevir (Önizleme)", imgui.ImVec2(220, 32)):
            self._build_preview(frame)

    # -----------------------------------------------------------------
    # ÖNİZLEME UI
    # -----------------------------------------------------------------
    def _draw_preview_ui(self):
        n_total = len(self._preview_areas)
        n_sel = len(self._preview_selected)

        imgui.text(f"Kaynak: {self._preview_frame.label if self._preview_frame else '?'}")
        imgui.text(f"Önizleme: {n_total} area  ({len(self._preview_nodes)} node)")
        imgui.text_colored(imgui.ImVec4(0.9, 0.7, 0.3, 1.0), f'Seçili: {n_sel}')
        # Kalınlık (önizleme sırasında değiştirilemez — yeniden üretmek gerek)
        imgui.text_disabled(f"Kalınlık: {self.thickness:.1f} mm (değiştirmek için yeniden çevir)")
        _, self.hide_original = imgui.checkbox("Modele aktarınca orijinal frame'i gizle",
                                                self.hide_original)

        imgui.separator()

        # --- 2D canvas ---
        self._draw_preview_canvas()

        imgui.separator()

        # --- Aksiyonlar ---
        can_delete_sel = n_sel > 0
        if not can_delete_sel:
            imgui.push_style_color(
                imgui.Col_.button, imgui.ImVec4(0.3, 0.3, 0.3, 1.0)
            )
        if imgui.button("Seçilileri Sil", imgui.ImVec2(140, 0)) and can_delete_sel:
            self._preview_areas = [
                a for a in self._preview_areas
                if a.unique_id not in self._preview_selected
            ]
            self._preview_selected.clear()
            self._refresh_preview_nodes()
        if not can_delete_sel:
            imgui.pop_style_color()

        imgui.same_line()
        if imgui.button("Seçimi Temizle", imgui.ImVec2(140, 0)):
            self._preview_selected.clear()

        imgui.same_line()
        if imgui.button("İptal", imgui.ImVec2(90, 0)):
            self._clear_preview()
            return

        imgui.separator()

        if imgui.button("Modele Aktar", imgui.ImVec2(220, 32)):
            self._commit_to_scene()

    # -----------------------------------------------------------------
    # 2D: KAYNAK POLYGON
    # -----------------------------------------------------------------
    def _draw_source_polygon_2d(self, poly):
        us = [p.x for p in poly.points]
        vs = [p.y for p in poly.points]
        self._draw_polygon_or_areas(
            point_list=[(p.x, p.y) for p in poly.points],
            is_preview=False,
        )

    # -----------------------------------------------------------------
    # 2D: ÖNİZLEME AREAS
    # -----------------------------------------------------------------
    def _draw_edges_canvas(self):

        if not self._polygon_points or len(self._polygon_points) < 3:
            imgui.text_disabled("Polygon yok")
            return

        pts = self._polygon_points
        us = [p[0] for p in pts]
        vs = [p[1] for p in pts]
        umin, umax = min(us), max(us)
        vmin, vmax = min(vs), max(vs)
        du = max(umax - umin, 1e-6)
        dv = max(vmax - vmin, 1e-6)

        avail_w = imgui.get_content_region_avail().x
        canvas_w = min(avail_w, 400.0)
        canvas_h = 340.0

        scale = min(canvas_w / du, canvas_h / dv) * 0.85
        cx = canvas_w * 0.5 - (umin + umax) * 0.5 * scale
        cy = canvas_h * 0.5 + (vmin + vmax) * 0.5 * scale

        # --- 1) Çizim için cursor konumunu al ---
        p0 = imgui.get_cursor_screen_pos()
        draw = imgui.get_window_draw_list()

        draw.add_rect_filled(
            p0, imgui.ImVec2(p0.x + canvas_w, p0.y + canvas_h),
            _color_u32(0.10, 0.10, 0.14, 1.0),
        )
        draw.add_rect(
            p0, imgui.ImVec2(p0.x + canvas_w, p0.y + canvas_h),
            _color_u32(0.30, 0.30, 0.35, 1.0),
        )

        def to_screen(u, v):
            return (p0[0] + u * scale + cx,
                    p0[1] - v * scale + cy)

        N = len(pts)
        screen_pts = [to_screen(u, v) for (u, v) in pts]

        # Kenarları çiz
        for i in range(N):
            a = screen_pts[i]
            b = screen_pts[(i + 1) % N]
            is_sel = i in self._edge_selected
            is_hover = (getattr(self, '_hover_edge', None) == i)
            if is_sel:
                color = _color_u32(1.0, 0.55, 0.15, 1.0)
                th = 3.5
            elif is_hover:
                color = _color_u32(1.0, 0.9, 0.3, 1.0)
                th = 3.0
            else:
                color = _color_u32(0.55, 0.80, 1.0, 1.0)
                th = 2.0
            draw.add_line(
                imgui.ImVec2(*a), imgui.ImVec2(*b), color, th
            )

        for (sx, sy) in screen_pts:
            draw.add_circle_filled(
                imgui.ImVec2(sx, sy), 3.5, _color_u32(1, 1, 1, 1)
            )

        # --- 2) Aynı konuma invisible_button koy (tıklama için) ---
        imgui.set_cursor_screen_pos(p0)
        imgui.invisible_button(
            "##edges_canvas", imgui.ImVec2(canvas_w, canvas_h)
        )

        # --- 3) Hover + click ---
        io = imgui.get_io()
        mx, my = io.mouse_pos

        # Hover için en yakın kenar
        if imgui.is_item_hovered():
            best_i, best_d = None, 8.0
            for i in range(N):
                a = screen_pts[i]
                b = screen_pts[(i + 1) % N]
                d = _dist_point_segment((mx, my), a, b)
                if d < best_d:
                    best_d = d
                    best_i = i
            self._hover_edge = best_i
        else:
            self._hover_edge = None

        # Click
        if imgui.is_item_clicked(0):
            if self._hover_edge is not None:
                ctrl = self._ctrl_pressed()          # ← buradan
                if ctrl:
                    self._edge_selected ^= {self._hover_edge}
                else:
                    self._edge_selected = {self._hover_edge}
            else:
                if not self._ctrl_pressed():
                    self._edge_selected.clear()

    def _ctrl_pressed(self) -> bool:
        """Ctrl basılı mı? key_ctrl yerine keys_down (daha güvenilir)."""
        try:
            import glfw
            io = imgui.get_io()
            left = io.keys_down.get(glfw.KEY_LEFT_CONTROL, False)
            right = io.keys_down.get(glfw.KEY_RIGHT_CONTROL, False)
            return bool(left or right or io.key_ctrl)
        except Exception:
            return bool(imgui.get_io().key_ctrl)
        
    def _convert_edges_and_commit(self):
        """
        Seçili kenarları Area'ya çevir ve doğrudan sahneye aktar.
        - sd_frame_to_areas mantığını **tek kenar** için uygular
        - Önce paylaşılan Node'ları ekler, sonra Area'ları
        """
        if not self._preview_frame or not self._edge_selected:
            logger.debug("[SDPanel] Dönüşüm için frame veya seçili kenar yok")
            return

        if not self.app or not self.app.engine or not self.app.engine.scene:
            logger.debug("[SDPanel] engine veya scene yok")
            return

        frame = self._preview_frame
        scn = self.app.engine.scene
        section = frame.section

        sd = getattr(section, 'sd_section', None)
        if sd is None:
            logger.debug(f"[SDPanel] '{frame.label}' sd_section yok")
            return

        poly = next(
            (s for s in sd.shapes
            if getattr(s, 'shape_kind', '') == 'Polygon' and len(s.points) >= 3),
            None,
        )
        if poly is None:
            logger.debug(f"[SDPanel] '{frame.label}' Polygon shape yok")
            return

        # Frame düşey mi?
        dx = frame.node_j.x - frame.node_i.x
        dy = frame.node_j.y - frame.node_i.y
        dz = frame.node_j.z - frame.node_i.z
        L = (dx * dx + dy * dy + dz * dz) ** 0.5
        if L < 1e-9:
            logger.error(f"[SDPanel] '{frame.label}': sıfır uzunluklu frame")
            return
        if abs(abs(dz) / L - 1.0) > 1e-3:
            logger.error(f"[SDPanel] '{frame.label}': düşey değil (|axis.z/L|={abs(dz/L):.4f})")
            return

        # Local frame
        e1 = glm.vec3(dx / L, dy / L, dz / L)
        ref = glm.vec3(0, 0, 1) if abs(e1.z) < 0.9999 else glm.vec3(1, 0, 0)
        e2 = glm.normalize(ref - e1 * glm.dot(ref, e1))
        e3 = glm.normalize(glm.cross(e1, e2))
        if abs(frame.rotation_deg) > 1e-9:
            a = math.radians(frame.rotation_deg)
            ca, sa = math.cos(a), math.sin(a)
            e2_new = e2 * ca + e3 * sa
            e3_new = -e2 * sa + e3 * ca
            e2, e3 = glm.normalize(e2_new), glm.normalize(e3_new)

        if abs(e2.z) > 1e-3 or abs(e3.z) > 1e-3:
            logger.error(f"[SDPanel] '{frame.label}': kesit düzlemi XY'de değil")
            return

        # Polygon köşelerinden 3D i ve j uçları
        ni, nj = frame.node_i, frame.node_j
        pts_uv = [(p.x, p.y) for p in poly.points]
        N = len(pts_uv)

        P_i = [glm.vec3(ni.x, ni.y, ni.z) + u * e2 + v * e3 for (u, v) in pts_uv]
        P_j = [glm.vec3(nj.x, nj.y, nj.z) + u * e2 + v * e3 for (u, v) in pts_uv]

        # Seçili her kenar için bir dörtgen
        new_areas = []
        for k in sorted(self._edge_selected):
            k2 = (k + 1) % N
            corners = [P_i[k], P_i[k2], P_j[k2], P_j[k]]

            # Node'ları oluştur
            nodes = [
                Node(float(p.x), float(p.y), float(p.z))
                for p in corners
            ]
            area = Area(
                nodes,
                thickness=self.thickness,
                label=f"{frame.label}_e{k}",
            )
            area.material = section.material
            area.section_name = section.name
            new_areas.append(area)

        if not new_areas:
            logger.debug("[SDPanel] Üretilecek area yok")
            return

        # Node paylaşımı — aynı 3D konumdaki node'ları tek nesneye indir
        shared_nodes = _dedupe_area_nodes(new_areas)

        # 1) Node'ları ekle (paylaşılan)
        for nd in shared_nodes:
            scn.add_node(nd)

        # 2) Area'ları ekle
        for area in new_areas:
            scn.add_area(area)

        # 3) Orijinal frame'i gizle
        if self.hide_original:
            frame.is_visible = False
            frame.mark_dirty()

        # 4) Show-only modundaysa filtreyi güncelle
        if getattr(self.app, "_show_only_ids", None) is not None:
            self.app._show_only_ids.update(a.unique_id for a in new_areas)
            self.app._show_only_ids.discard(frame.unique_id)
            scn._render_filter = self.app._show_only_ids

        # 5) Sahneyi yenile
        scn.mark_dirty()

        logger.info(
            f"[SDPanel] '{frame.label}' → {len(new_areas)} area, "
            f"{len(shared_nodes)} node eklendi "
            f"(kenarlar: {sorted(self._edge_selected)}, kalınlık={self.thickness:.1f} mm)"
        )

        # 6) Önizleme state'ini temizle
        self._polygon_points.clear()
        self._edge_selected.clear()
        self._preview_frame = None
        self.visible = False
    # -----------------------------------------------------------------
    # HIT-TEST (ekran koordinatlarından area bul)
    # -----------------------------------------------------------------
    def _hit_test_area_screen(
        self,
        mx: float, my: float,
        p0: tuple[float, float],
        scale: float,
        cx: float, cy: float,
    ) -> Area | None:
        """
        Ekran noktası → hangi area?
        Nokta-in-polygon (ray casting) kullanır.
        """
        if scale <= 0:
            return None

        def to_screen(u, v):
            return (p0[0] + u * scale + cx,
                    p0[1] - v * scale + cy)

        # En üstteki area'yı bul (üst üste binme durumunda son eklenen kazanır)
        for area in reversed(self._preview_areas):
            if len(area.nodes) < 3:
                continue
            pts = [to_screen(nd.x, nd.y) for nd in area.nodes]
            if _point_in_polygon((mx, my), pts):
                return area
        return None

    # -----------------------------------------------------------------
    # ÖNİZLEME ÜRETİMİ
    # -----------------------------------------------------------------
    def _build_preview(self, frame: Frame):
        areas, errors = sd_frame_to_areas(
            frame,
            thickness=self.thickness,
            label_prefix=f"F{frame.label}",
        )
        if errors:
            self._last_error = "; ".join(errors)
            for e in errors:
                logger.error(f"[SDPanel] {e}")
            return

        # Node'ları birleştir (paylaşılan köşeler)
        shared_nodes = _dedupe_area_nodes(areas)

        self._preview_frame = frame
        self._preview_areas = list(areas)
        self._preview_nodes = shared_nodes
        self._preview_selected.clear()
        self._last_error = ""

        logger.info(
            f"[SDPanel] '{frame.label}' → önizleme: {len(areas)} area, "
            f"{len(shared_nodes)} paylaşılan node"
        )

    def _refresh_preview_nodes(self):
        """Area silindikten sonra paylaşılan node listesini yeniden hesapla."""
        if not self._preview_areas:
            self._preview_nodes = []
            return
        shared: dict[tuple[float, float, float], Node] = {}
        for a in self._preview_areas:
            for nd in a.nodes:
                key = _node_key(nd)
                if key not in shared:
                    shared[key] = nd
        self._preview_nodes = list(shared.values())

    # -----------------------------------------------------------------
    # MODELE AKTARMA
    # -----------------------------------------------------------------
    def _commit_to_scene(self):
        if not self.app or not self.app.engine or not self.app.engine.scene:
            return
        if not self._preview_areas:
            return

        scn = self.app.engine.scene

        # 1) Node'ları ekle (paylaşılan Node nesneleri)
        for nd in self._preview_nodes:
            # Zaten sahnede olan bir node ile çakışmasın — unique_id yeni
            scn.add_node(nd)

        # 2) Area'ları ekle
        mat = self._preview_frame.section.material if self._preview_frame else None
        sec_name = self._preview_frame.section.name if self._preview_frame else ""
        for area in self._preview_areas:
            area.material = mat
            area.section_name = sec_name
            scn.add_area(area)

        # 3) Orijinal frame'i gizle
        if self.hide_original and self._preview_frame is not None:
            self._preview_frame.is_visible = False
            self._preview_frame.mark_dirty()

        # 4) Show-only modundaysa filtreyi güncelle
        if getattr(self.app, "_show_only_ids", None) is not None:
            self.app._show_only_ids.update(a.unique_id for a in self._preview_areas)
            if self._preview_frame is not None:
                self.app._show_only_ids.discard(self._preview_frame.unique_id)
            scn._render_filter = self.app._show_only_ids

        # 5) Sahneyi yenile
        scn.mark_dirty()

        logger.info(
            f"[SDPanel] Modele aktarıldı: {len(self._preview_areas)} area, "
            f"{len(self._preview_nodes)} node "
            f"(frame={self._preview_frame.label if self._preview_frame else '?'})"
        )

        # 6) Önizlemeyi temizle
        if self.delete_after_commit:
            self._clear_preview()
            self.visible = False

    # -----------------------------------------------------------------
    # GENEL 2D ÇİZİM (kaynak polygon için fallback)
    # -----------------------------------------------------------------
    def _draw_polygon_or_areas(self, point_list, is_preview=False):
        """Basit polygon önizlemesi (kaynak için)."""
        if len(point_list) < 3:
            return

        us = [p[0] for p in point_list]
        vs = [p[1] for p in point_list]
        umin, umax = min(us), max(us)
        vmin, vmax = min(vs), max(vs)

        avail_w = imgui.get_content_region_avail().x
        canvas_h = 300.0
        canvas_w = min(avail_w, 380.0)
        du = max(umax - umin, 1e-6)
        dv = max(vmax - vmin, 1e-6)
        scale = min(canvas_w / du, canvas_h / dv) * 0.9
        cx = canvas_w * 0.5 - (umin + umax) * 0.5 * scale
        cy = canvas_h * 0.5 + (vmin + vmax) * 0.5 * scale

        p0 = imgui.get_cursor_screen_pos()
        draw = imgui.get_window_draw_list()

        draw.add_rect_filled(
            p0, imgui.ImVec2(p0.x + canvas_w, p0.y + canvas_h),
            _color_u32(0.10, 0.10, 0.14, 1.0),
        )
        draw.add_rect(
            p0, imgui.ImVec2(p0.x + canvas_w, p0.y + canvas_h),
            _color_u32(0.30, 0.30, 0.35, 1.0),
        )

        screen_pts = [
            (p0[0] + u * scale + cx,
             p0[1] - v * scale + cy)
            for (u, v) in point_list
        ]
        edge = _color_u32(0.60, 0.85, 1.00, 1.0)
        for i in range(len(screen_pts)):
            a = screen_pts[i]
            b = screen_pts[(i + 1) % len(screen_pts)]
            draw.add_line(
                imgui.ImVec2(*a), imgui.ImVec2(*b), edge, 2.0
            )
        for (sx, sy) in screen_pts:
            draw.add_circle_filled(imgui.ImVec2(sx, sy), 3.0, edge)

        imgui.dummy(imgui.ImVec2(canvas_w, canvas_h))


# ============================================================
# NOKTА-IN-POLYGON (ray casting)
# ============================================================
def _point_in_polygon(p: tuple[float, float], poly: list[tuple[float, float]]) -> bool:
    """
    Ray-casting nokta-in-polygon testi.
    p: (x, y), poly: [(x0,y0), (x1,y1), ...] (kapalı, son=ilk değil)
    """
    if len(poly) < 3:
        return False
    x, y = p
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        # Kenar (xi,yi)-(xj,yj) yatay ışını kesiyor mu?
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside