# ui/plane_manager_panel.py
"""
PlaneManagerPanel — Project.planes listesi + CRUD + assoc önizleme.

Yeni plane kaynakları:
  1) Grid'den (project.grid.x/y/z_coords)
  2) Modelden 2 nokta + Z up (from_2_points_z_up)
  3) Modelden 3 nokta (from_3_points)

Önizleme plane üretilir (kaydedilmez), "Oluştur" ile project.add_plane.

CadApp'ten sadece `self.app` referansı alır. Callback YOK.
"""

from __future__ import annotations

from logging_config import CadLogger
from typing import Optional, List

import imgui
import numpy as np

from domain.plane import Plane, ASSOC_KINDS
from domain.element import Node
from ui.base_panel import BasePanel

logger = CadLogger.get(__name__)


_AXIS_LABELS = ("X", "Y", "Z")

# Kaynak seçenekleri
SRC_GRID = 0
SRC_2PT = 1
SRC_3PT = 2


class PlaneManagerPanel(BasePanel):

    PANEL_W = 640
    PANEL_H = 720

    def __init__(self):
        self.app = None
        self.visible = False

        self._selected_name: Optional[str] = None

        # Yeni plane formu
        self._form_open = False
        self._new_source: int = SRC_GRID

        # Grid kaynağı
        self._grid_axis: int = 1                # 0=X, 1=Y, 2=Z
        self._grid_coord_index: int = 0

        # 2pt / 3pt kaynağı: seçilen node ID'leri (unique_id, int)
        self._picked_nodes: List[int] = []

        # Önizleme
        self._preview: Optional[Plane] = None
        self._preview_name: str = ""

        # Önizleme sınırları/depth (kullanıcı düzenleyebilir)
        self._edit_bounds_open: bool = False
        self._pv_u_min: float = 0.0
        self._pv_u_max: float = 0.0
        self._pv_v_min: float = 0.0
        self._pv_v_max: float = 0.0
        self._pv_depth_minus: float = 500.0
        self._pv_depth_plus: float = 500.0

        self._pending_delete: Optional[str] = None

    # ------------------------------------------------------------------
    #  Context helpers
    # ------------------------------------------------------------------
    def _project(self):
        return getattr(self.app, "current_project", None) if self.app else None

    def _scene(self):
        if not self.app:
            return None
        eng = getattr(self.app, "engine", None)
        if eng is not None and eng.scene is not None:
            return eng.scene
        proj = self._project()
        return proj.scene if proj else None

    def _selected_plane(self) -> Optional[Plane]:
        proj = self._project()
        if not proj:
            
            return None
        if not self._selected_name:
            
            return None
        plane = proj.planes.get(self._selected_name)
        
        return plane

    def _scene_nodes_by_id(self) -> dict:
        scene = self._scene()
        if scene is None:
            return {}
        return dict(scene.nodes)

    def _scene_bbox(self):
        """Sahnenin (center, size) sınırları. Boşsa None."""
        scene = self._scene()
        if scene is None:
            return None
        try:
            return scene.get_bounds()
        except Exception:
            return None

    # ------------------------------------------------------------------
    #  open / close
    # ------------------------------------------------------------------
    def open(self):
        self.visible = True
        proj = self._project()
        if proj and proj.planes and self._selected_name is None:
            self._selected_name = next(iter(proj.planes.keys()))

    def close(self):
        self.visible = False
        self._clear_preview()

    # ------------------------------------------------------------------
    #  draw
    # ------------------------------------------------------------------
    def draw(self):
        if not self.visible:
            return
        proj = self._project()
        if proj is None:
            return

        imgui.set_next_window_size(self.PANEL_W, self.PANEL_H, imgui.FIRST_USE_EVER)
        imgui.set_next_window_position(1300 - self.PANEL_W - 20, 60, imgui.FIRST_USE_EVER)

        expanded, opened = imgui.begin("Plane Manager", True)
        try:
            if not opened:
                self.visible = False
                return
            if not expanded:
                return

            self._draw_toolbar()
            imgui.separator()

            imgui.begin_child("pm_list", width=230, height=0, border=True)
            try:
                self._draw_list()
            finally:
                imgui.end_child()

            imgui.same_line()

            imgui.begin_child("pm_detail", width=0, height=0, border=False)
            try:
                self._draw_detail()
            finally:
                imgui.end_child()

        finally:
            imgui.end()

    # ------------------------------------------------------------------
    #  Toolbar
    # ------------------------------------------------------------------
    def _draw_toolbar(self):
        proj = self._project()
        n = len(proj.planes) if proj else 0
        imgui.text_colored(f"{n} plane", 0.7, 0.8, 0.9, 1.0)

        imgui.same_line(120)
        if imgui.button("+ Yeni"):
            self._open_new_plane_form()

        imgui.same_line()
        sel = self._selected_plane()
        if sel is None:
            imgui.push_style_color(imgui.COLOR_BUTTON, 0.25, 0.25, 0.25, 1.0)
            imgui.button("Sil", width=60)
            imgui.pop_style_color(1)
        else:
            if imgui.button("Sil", width=60):
                self._pending_delete = sel.name

        imgui.same_line()
        if sel is not None and imgui.button("Düzenle", width=70):
            self._open_new_plane_form(from_plane=sel)

        imgui.same_line()
        if sel is not None and imgui.button("Plot", width=60):
            self._do_plot(sel)

        imgui.same_line()
        if sel is not None and imgui.button("Yenile", width=70):
            scene = self._scene()
            if scene is not None:
                sel.refresh_assoc(scene)
                logger.info(f"[PlaneMgr] '{sel.name}' assoc yenilendi.")

        if self._pending_delete:
            self._draw_delete_confirm()

    def _draw_delete_confirm(self):
        imgui.open_popup("##pm_delete_confirm")
        if imgui.begin_popup_modal("##pm_delete_confirm", True,
                                    imgui.WINDOW_ALWAYS_AUTO_RESIZE)[0]:
            imgui.text(f"'{self._pending_delete}' silinsin mi?")
            imgui.spacing()
            if imgui.button("Sil", width=100):
                name = self._pending_delete
                self._pending_delete = None
                self._do_delete(name)
                imgui.close_current_popup()
            imgui.same_line()
            if imgui.button("Vazgeç", width=100):
                self._pending_delete = None
                imgui.close_current_popup()
            imgui.end_popup()

    # ------------------------------------------------------------------
    #  Liste
    # ------------------------------------------------------------------
    def _draw_list(self):
        proj = self._project()
        if not proj:
            return
        planes = proj.planes
        if not planes:
            imgui.text_colored("Henüz plane yok.", 0.6, 0.6, 0.6, 1.0)
            imgui.spacing()
            imgui.text_colored("'+ Yeni' ile başla.", 0.5, 0.5, 0.5, 1.0)
            return

        for name in sorted(planes.keys()):
            p = planes[name]
            is_sel = (name == self._selected_name)
            flags = imgui.SELECTABLE_ALLOW_DOUBLE_CLICK
            if imgui.selectable(f"{name}##pm", is_sel, flags)[1]:
                self._selected_name = name
            imgui.same_line(180)
            n_assoc = sum(len(s) for s in p.associated.values())
            imgui.text_colored(f"{n_assoc:4d}", 0.5, 0.7, 0.85, 1.0)

    # ------------------------------------------------------------------
    #  Detay
    # ------------------------------------------------------------------
    def _draw_detail(self):
        # Yeni plane formu her zaman üstte (açıksa)
        if self._form_open:
            self._draw_new_plane_form()
            imgui.separator()
            imgui.spacing()

        sel = self._selected_plane()
        if sel is None:
            if not self._form_open:
                imgui.text_colored("Bir plane seç veya '+ Yeni'.", 0.6, 0.6, 0.6, 1.0)
            return

        # --- Kimlik ---
        imgui.text_colored("Kimlik", 0.8, 0.85, 0.95, 1.0)
        imgui.text(f"ID: {sel.plane_id[:12]}...")
        imgui.push_item_width(220)
        changed, new_name = imgui.input_text("##pm_name", sel.name, 128)
        imgui.pop_item_width()
        if changed and new_name and new_name != sel.name:
            self._try_rename(sel, new_name)

        imgui.spacing()
        imgui.separator()

        # --- Geometri ---
        imgui.text_colored("Geometri", 0.8, 0.85, 0.95, 1.0)
        o, n = sel.origin, sel.normal
        imgui.text(f"origin : ({o[0]:.2f}, {o[1]:.2f}, {o[2]:.2f})")
        imgui.text(f"normal : ({n[0]:.3f}, {n[1]:.3f}, {n[2]:.3f})")
        imgui.text(f"u : [{self._fmt(sel.u_min)}, {self._fmt(sel.u_max)}]")
        imgui.text(f"v : [{self._fmt(sel.v_min)}, {self._fmt(sel.v_max)}]")
        imgui.text(f"depth : [-{sel.depth_minus:.1f}, +{sel.depth_plus:.1f}]")

        imgui.spacing()
        imgui.separator()

        # --- Assoc ---
        imgui.text_colored("Assoc", 0.8, 0.85, 0.95, 1.0)
        total = 0
        for k in ASSOC_KINDS:
            n_a = len(sel.associated.get(k, set()))
            n_e = len(sel.excluded.get(k, set()))
            total += n_a
            if n_a or n_e:
                imgui.text_colored(f"  {k:6s}: {n_a:4d}", 0.75, 0.85, 0.9, 1.0)
                if n_e:
                    imgui.same_line()
                    imgui.text_colored(f"(excluded {n_e})", 0.9, 0.6, 0.5, 1.0)
        imgui.text_colored(f"  toplam: {total}", 0.85, 0.9, 0.95, 1.0)
        imgui.text_colored(f"  pending: {len(sel.pending)}", 0.9, 0.85, 0.5, 1.0)

        imgui.spacing()
        imgui.separator()

    # ==================================================================
    #  YENİ PLANE FORMU veya DÜZENLE
    # ==================================================================
    def _open_new_plane_form(self, from_plane: Optional[Plane] = None):
        self._form_open = True
        self._new_source = SRC_GRID   # varsayılan
        self._picked_nodes = []
        self._preview = None
        self._edit_bounds_open = False
        self._editing_plane = from_plane   # ← YENİ: mevcut plane kopyası

        if from_plane is not None:
            # Mevcut plane'in kopyasını preview olarak kullan
            import copy
            self._preview = copy.deepcopy(from_plane)
            self._preview_name = from_plane.name
            # Sınır/depth alanlarını doldur
            self._pv_u_min = from_plane.u_min or 0.0
            self._pv_u_max = from_plane.u_max or 0.0
            self._pv_v_min = from_plane.v_min or 0.0
            self._pv_v_max = from_plane.v_max or 0.0
            self._pv_depth_minus = from_plane.depth_minus
            self._pv_depth_plus = from_plane.depth_plus
            # "kaynak" seçimi anlamsız — düzenleme modunda gizle
        else:
            self._editing_plane = None
            self._refresh_preview()

    def _clear_preview(self):
        self._preview = None

    def _draw_new_plane_form(self):
        editing = getattr(self, "_editing_plane", None) is not None
        
        if editing:
            imgui.text_colored("─── Plane Düzenle ───", 0.9, 0.8, 0.5, 1.0)
            imgui.text_colored(f"Kaynak: mevcut plane (kopya)", 0.7, 0.7, 0.7, 1.0)
            imgui.spacing()
        else:
            imgui.text_colored("─── Yeni Plane ───", 0.85, 0.9, 0.95, 1.0)
            # Kaynak seçimi (radio_button)
            imgui.text("Kaynak")
            imgui.same_line(120)
            for i, label in enumerate(("Grid", "2 Nokta", "3 Nokta")):
                ...
            imgui.spacing()
            if self._new_source == SRC_GRID:
                self._draw_grid_source()
            elif self._new_source == SRC_2PT:
                self._draw_points_source(required=2)
            elif self._new_source == SRC_3PT:
                self._draw_points_source(required=3)
            imgui.spacing()

        # Önizleme (düzenleme modunda da)
        if self._preview is not None:
            self._draw_preview()
            imgui.spacing()
            
            if editing:
                if imgui.button("Güncelle", width=120):
                    self._do_update_from_preview()
                imgui.same_line()
                if imgui.button("Vazgeç", width=100):
                    self._form_open = False
                    self._editing_plane = None
                    self._clear_preview()
            else:
                if imgui.button("Oluştur", width=120):
                    self._do_create_from_preview()
                imgui.same_line()
                if imgui.button("Vazgeç", width=100):
                    self._form_open = False
                    self._clear_preview()
        else:
            imgui.text_colored("Önizleme yok.", 0.6, 0.6, 0.6, 1.0)
            if imgui.button("Vazgeç", width=100):
                self._form_open = False

    # ------------------------------------------------------------------
    #  Grid kaynağı
    # ------------------------------------------------------------------
    def _draw_grid_source(self):
        proj = self._project()
        if not proj:
            return
        grid = proj.grid

        # Axis seçimi
        imgui.text("Eksen")
        imgui.same_line(120)
        for i, ax in enumerate(_AXIS_LABELS):
            if i > 0:
                imgui.same_line()
            clicked = imgui.radio_button(f"{ax}##pm_gax{i}", self._grid_axis == i)
            if clicked and self._grid_axis != i:
                self._grid_axis = i
                self._grid_coord_index = 0
                self._refresh_preview()

        # Koordinat listesi (axis'e göre)
        coords = self._coords_for_axis(grid, self._grid_axis)
        if not coords:
            imgui.text_colored("  (Grid'de bu eksende koordinat yok)", 0.9, 0.6, 0.5, 1.0)
            return

        imgui.text("Koordinat")
        imgui.same_line(120)

        # Combo box
        _AXIS_NAMES = ("x", "y", "z")
        preview_label = f"{_AXIS_NAMES[self._grid_axis]} = {coords[self._grid_coord_index]:.0f}"
        if imgui.begin_combo("##pm_coord", preview_label):
            for i, c in enumerate(coords):
                is_sel = (i == self._grid_coord_index)
                if imgui.selectable(f"{_AXIS_NAMES[self._grid_axis]} = {c:.0f}##pm_c{i}",
                                    is_sel)[1]:
                    self._grid_coord_index = i
                    self._refresh_preview()
                if is_sel:
                    imgui.set_item_default_focus()
            imgui.end_combo()

    def _coords_for_axis(self, grid, axis: int) -> list:
        if axis == 0:
            return list(grid.x_coords or [])
        if axis == 1:
            return list(grid.y_coords or [])
        return list(grid.z_coords or [])

    # ------------------------------------------------------------------
    #  2/3 nokta kaynağı
    # ------------------------------------------------------------------
    def _draw_points_source(self, required: int):
        imgui.text_colored(
            f"Modelden {required} nokta seç (3D sahnede).",
            0.7, 0.75, 0.8, 1.0
        )

        # Sahnede seçili node'ları göster (canlı)
        scene = self._scene()
        live_sel = []
        if scene is not None:
            try:
                live_sel = [el for el in scene.get_selected()
                            if isinstance(el, Node)]
            except Exception:
                live_sel = []

        if live_sel:
            imgui.text_colored(
                f"  Sahnede seçili: {len(live_sel)} node  "
                f"(ID: {', '.join(str(n.unique_id) for n in live_sel[:5])}"
                f"{'...' if len(live_sel) > 5 else ''})",
                0.6, 0.85, 0.7, 1.0
            )
        else:
            imgui.text_colored("  Sahnede seçili node yok.", 0.8, 0.6, 0.5, 1.0)

        # "Sahneden Al" butonu
        can_take = len(live_sel) >= required
        if not can_take:
            imgui.push_style_color(imgui.COLOR_BUTTON, 0.25, 0.25, 0.25, 1.0)
        if imgui.button("Sahneden Al", width=120) and can_take:
            self._picked_nodes = [n.unique_id for n in live_sel[:required]]
            self._refresh_preview()
        if not can_take:
            imgui.pop_style_color(1)

        # Seçilen noktalar önizlemesi
        if self._picked_nodes:
            imgui.same_line()
            imgui.text_colored(
                f"({len(self._picked_nodes)} seçili)", 0.7, 0.85, 0.7, 1.0
            )
            imgui.same_line()
            if imgui.button("Temizle", width=80):
                self._picked_nodes = []
                self._refresh_preview()

            # Nokta koordinatları
            nodes_by_id = self._scene_nodes_by_id()
            for nid in self._picked_nodes:
                nd = nodes_by_id.get(nid)
                if nd is not None:
                    imgui.text_colored(
                        f"  N{nid}: ({nd.x:.0f}, {nd.y:.0f}, {nd.z:.0f})",
                        0.7, 0.75, 0.8, 1.0
                    )

    # ------------------------------------------------------------------
    #  Önizleme
    # ------------------------------------------------------------------
    def _refresh_preview(self):
        """Kaynağa göre geçici Plane üret. Kaydetmez."""
        self._preview = None
        self._preview_name = ""

        try:
            if self._new_source == SRC_GRID:
                p = self._build_from_grid()
            elif self._new_source == SRC_2PT:
                p = self._build_from_2pt()
            elif self._new_source == SRC_3PT:
                p = self._build_from_3pt()
            else:
                p = None
        except Exception as e:
            logger.warning(f"[PlaneMgr] Önizleme hatası: {e}")
            p = None

        if p is None:
            return

        # Default sınır/depth (sahne bbox'tan)
        self._apply_smart_bounds(p)
        self._preview = p
        self._preview_name = p.name

    def _apply_smart_bounds(self, p: Plane):
        """
        Sahnenin bbox'ından otomatik u/v sınırları ve makul depth ata.
        Kullanıcı bunları düzenleyebilir.
        """
        bbox = self._scene_bbox()
        if bbox is None:
            return
        center, size = bbox
        half = max(size * 0.5, 1000.0)

        # u/v sınırları: p.origin etrafında half kadar
        # (grid'den gelen plane'de origin zaten koordinat merkezinde)
        uc = 0.0
        vc = 0.0
        p.u_min = uc - half
        p.u_max = uc + half
        p.v_min = vc - half
        p.v_max = vc + half

        # Depth: sahnenin %10'u veya 500, hangisi büyükse
        d = max(500.0, size * 0.05)
        p.depth_minus = d
        p.depth_plus = d

        # Önizleme sınırlarını güncelle
        self._pv_u_min = p.u_min
        self._pv_u_max = p.u_max
        self._pv_v_min = p.v_min
        self._pv_v_max = p.v_max
        self._pv_depth_minus = p.depth_minus
        self._pv_depth_plus = p.depth_plus

    def _build_from_grid(self) -> Optional[Plane]:
        proj = self._project()
        if not proj:
            return None
        grid = proj.grid
        coords = self._coords_for_axis(grid, self._grid_axis)
        if not coords:
            return None
        idx = min(self._grid_coord_index, len(coords) - 1)
        coord = float(coords[idx])

        axis_name = "xyz"[self._grid_axis]
        plane = Plane.from_axis_offset(
            axis_name, coord,
            name=f"Plane_{axis_name}{int(coord)}",
        )
        # Assoc için scene gerekli
        scene = self._scene()
        if scene is not None:
            plane.refresh_assoc(scene)
        return plane

    def _build_from_2pt(self) -> Optional[Plane]:
        if len(self._picked_nodes) != 2:
            return None
        nodes = self._scene_nodes_by_id()
        n1 = nodes.get(self._picked_nodes[0])
        n2 = nodes.get(self._picked_nodes[1])
        if n1 is None or n2 is None:
            return None
        p1 = np.array([n1.x, n1.y, n1.z])
        p2 = np.array([n2.x, n2.y, n2.z])
        try:
            plane = Plane.from_2_points_z_up(
                p1, p2,
                name=f"Plane_2pt_{self._picked_nodes[0]}_{self._picked_nodes[1]}",
            )
        except Exception as e:
            logger.warning(f"[PlaneMgr] 2pt plane hatası: {e}")
            return None
        scene = self._scene()
        if scene is not None:
            plane.refresh_assoc(scene)
        return plane

    def _build_from_3pt(self) -> Optional[Plane]:
        if len(self._picked_nodes) != 3:
            return None
        nodes = self._scene_nodes_by_id()
        nds = [nodes.get(nid) for nid in self._picked_nodes]
        if any(n is None for n in nds):
            return None
        p1 = np.array([nds[0].x, nds[0].y, nds[0].z])
        p2 = np.array([nds[1].x, nds[1].y, nds[1].z])
        p3 = np.array([nds[2].x, nds[2].y, nds[2].z])
        try:
            plane = Plane.from_3_points(
                p1, p2, p3,
                name=f"Plane_3pt_{self._picked_nodes[0]}",
            )
        except Exception as e:
            logger.warning(f"[PlaneMgr] 3pt plane hatası: {e}")
            return None
        scene = self._scene()
        if scene is not None:
            plane.refresh_assoc(scene)
        return plane

    def _draw_preview(self):
        p = self._preview
        imgui.text_colored("─── Önizleme ───", 0.85, 0.9, 0.95, 1.0)

        imgui.push_item_width(220)
        _, self._preview_name = imgui.input_text("İsim##pm_pvname",
                                                  self._preview_name, 128)
        imgui.pop_item_width()

        o, n = p.origin, p.normal
        imgui.text(f"origin : ({o[0]:.2f}, {o[1]:.2f}, {o[2]:.2f})")
        imgui.text(f"normal : ({n[0]:.3f}, {n[1]:.3f}, {n[2]:.3f})")

        # Assoc özeti
        total = sum(len(s) for s in p.associated.values())
        imgui.text_colored(f"assoc : {total}", 0.6, 0.85, 0.7, 1.0)
        for k in ASSOC_KINDS:
            n_a = len(p.associated.get(k, set()))
            if n_a:
                imgui.text_colored(f"  {k:6s}: {n_a}", 0.7, 0.8, 0.85, 1.0)

        # Sınırları düzenle (collapsible)
        if imgui.tree_node("Sınırları Düzenle##pm_bounds"):
            imgui.push_item_width(120)
            imgui.text("u")
            imgui.same_line()
            _, self._pv_u_min = imgui.input_float("##pv_umin", self._pv_u_min, 0.0, 0.0)
            imgui.same_line()
            _, self._pv_u_max = imgui.input_float("##pv_umax", self._pv_u_max, 0.0, 0.0)

            imgui.text("v")
            imgui.same_line()
            _, self._pv_v_min = imgui.input_float("##pv_vmin", self._pv_v_min, 0.0, 0.0)
            imgui.same_line()
            _, self._pv_v_max = imgui.input_float("##pv_vmax", self._pv_v_max, 0.0, 0.0)

            imgui.text("depth -")
            imgui.same_line()
            _, self._pv_depth_minus = imgui.input_float("##pv_dm", self._pv_depth_minus, 0.0, 0.0)
            imgui.text("depth +")
            imgui.same_line()
            _, self._pv_depth_plus = imgui.input_float("##pv_dp", self._pv_depth_plus, 0.0, 0.0)
            imgui.pop_item_width()

            # Değiştiyse preview'a uygula
            p.u_min = self._pv_u_min
            p.u_max = self._pv_u_max
            p.v_min = self._pv_v_min
            p.v_max = self._pv_v_max
            p.depth_minus = self._pv_depth_minus
            p.depth_plus = self._pv_depth_plus

            # Assoc'u yeniden hesapla (sınır değişti)
            scene = self._scene()
            if scene is not None:
                p.refresh_assoc(scene)

            imgui.tree_pop()

    # ------------------------------------------------------------------
    #  Create / edit / rename / delete
    # ------------------------------------------------------------------
    def _do_create_from_preview(self):
        proj = self._project()
        if not proj or self._preview is None:
            return

        p = self._preview
        if self._preview_name.strip():
            p.name = self._preview_name.strip()
        if p.name in proj.planes:
            logger.warning(f"[PlaneMgr] '{p.name}' zaten var, oluşturulmadı.")
            return

        # Sınır/depth son değerler (form'dan)
        p.u_min = self._pv_u_min
        p.u_max = self._pv_u_max
        p.v_min = self._pv_v_min
        p.v_max = self._pv_v_max
        p.depth_minus = self._pv_depth_minus
        p.depth_plus = self._pv_depth_plus

        # Assoc'u son kez yenile
        scene = self._scene()
        if scene is not None:
            p.refresh_assoc(scene)

        proj.add_plane(p)
        self._selected_name = p.name
        self._form_open = False
        self._clear_preview()

        logger.info(
            f"[PlaneMgr] Yeni plane: {p.name} "
            f"(assoc={sum(len(s) for s in p.associated.values())}, "
            f"depth=±{p.depth_plus:.0f})"
        )

    def _do_edit(self, plane: Plane):
        scene = self._scene()
        if scene is None:
            logger.warning("[PlaneMgr] Sahne yok, edit açılamadı.")
            return
        pp = None
        if self.app and hasattr(self.app, "panels"):
            pp_info = self.app.panels.get("plane_plot")   # ← "plane_plot"
            if pp_info:
                pp = pp_info["instance"]
        if pp is None:
            logger.warning("[PlaneMgr] PlanePlotPanel bulunamadı.")
            return
        pp.open(scene=scene, plane=plane)
        logger.info(f"[PlaneMgr] Plane Plot: {plane.name}")

    def _do_delete(self, name: str):
        proj = self._project()
        if not proj:
            return
        proj.remove_plane(name)
        if self._selected_name == name:
            self._selected_name = next(iter(proj.planes.keys()), None)
        logger.info(f"[PlaneMgr] Silindi: {name}")

    def _try_rename(self, plane: Plane, new_name: str):
        proj = self._project()
        if not proj:
            return
        old = plane.name
        if new_name in proj.planes and new_name != old:
            logger.warning(f"[PlaneMgr] '{new_name}' zaten var.")
            return
        proj.planes.pop(old, None)
        plane.name = new_name
        proj.planes[new_name] = plane
        self._selected_name = new_name
        logger.info(f"[PlaneMgr] Yeniden adlandırıldı: '{old}' → '{new_name}'")

    def _do_update_from_preview(self):
        """Düzenleme modunda mevcut plane'i güncelle."""
        editing = getattr(self, "_editing_plane", None)
        if editing is None or self._preview is None:
            return
        proj = self._project()
        if not proj:
            return

        # Preview'dan geometriyi al
        p = self._preview
        
        # Mevcut plane'in alanlarını güncelle
        editing.u_min = self._pv_u_min
        editing.u_max = self._pv_u_max
        editing.v_min = self._pv_v_min
        editing.v_max = self._pv_v_max
        editing.depth_minus = self._pv_depth_minus
        editing.depth_plus = self._pv_depth_plus
        if self._preview_name.strip() and self._preview_name.strip() != editing.name:
            editing.name = self._preview_name.strip()
        
        # Assoc yenile
        scene = self._scene()
        if scene is not None:
            editing.refresh_assoc(scene)

        self._form_open = False
        self._editing_plane = None
        self._clear_preview()
        logger.info(f"[PlaneMgr] '{editing.name}' güncellendi")

    def _do_plot(self, plane: Plane):
        """Plane Plot panelini aç."""
        scene = self._scene()
        if scene is None:
            return
        pp = None
        if self.app and hasattr(self.app, "panels"):
            pp_info = self.app.panels.get("plane_plot")
            if pp_info:
                pp = pp_info["instance"]
        if pp is None:
            logger.warning("[PlaneMgr] PlanePlotPanel bulunamadı")
            return
        pp.open(scene=scene, plane=plane)
        logger.info(f"[PlaneMgr] Plot: {plane.name}")
        
    @staticmethod
    def _fmt(v):
        return "None" if v is None else f"{v:.1f}"