# ui/plane_manager_panel.py
"""
PlaneManagerPanel — Project.planes listesi + CRUD + assoc önizleme.

Yeni plane kaynakları:
  1) Var olan GridSystem düzlemleri
  2) XY/XZ/YZ uyumlu iki model noktası
  3) Üç model noktası
  4) Seçili Frame, Area veya Polygon

Önizleme plane üretilir (kaydedilmez), "Oluştur" ile project.add_plane.

CadApp'ten sadece `self.app` referansı alır. Callback YOK.
"""

from __future__ import annotations

import glfw
import numpy as np
from imgui_bundle import imgui

from domain.element import Area, Frame, Node, Polygon
from domain.plane import ASSOC_KINDS, Plane
from logging_config import CadLogger
from ui.base_panel import BasePanel

logger = CadLogger.get(__name__)


# Kaynak seçenekleri
SRC_GRID = 0
SRC_2PT = 1
SRC_3PT = 2
SRC_ELEMENT = 3


class PlaneManagerPanel(BasePanel):

    PANEL_W = 640
    PANEL_H = 720

    def __init__(self):
        self.app = None
        self.visible = False

        self._selected_name: str | None = None

        # Yeni plane formu
        self._form_open = False
        self._new_source: int = SRC_GRID

        # Grid kaynağı
        self._grid_plane_name = "XY"
        self._depth_unit_system = None

        # 2pt / 3pt kaynağı: seçilen node ID'leri (unique_id, int)
        self._picked_nodes: list[int] = []
        self._two_point_orientation = "XY"

        # Seçili eleman kaynağı
        self._picked_element_id: int | None = None
        self._frame_local_12 = False

        # Önizleme
        self._preview: Plane | None = None
        self._preview_name: str = ""
        self._preview_error: str | None = None

        # Önizleme sınırları/depth (kullanıcı düzenleyebilir)
        self._edit_bounds_open: bool = False
        self._pv_u_min: float = 0.0
        self._pv_u_max: float = 0.0
        self._pv_v_min: float = 0.0
        self._pv_v_max: float = 0.0
        self._pv_depth_minus: float = 500.0
        self._pv_depth_plus: float = 500.0

        self._pending_delete: str | None = None

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

    def _renderer(self):
        engine = getattr(self.app, "engine", None) if self.app else None
        return getattr(engine, "renderer", None)

    def _set_render_preview(self, plane: Plane | None):
        renderer = self._renderer()
        if renderer is not None:
            renderer.selected_plane = plane

    def _selected_plane(self) -> Plane | None:
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

    def _grid_system(self):
        engine = getattr(self.app, "engine", None) if self.app else None
        return getattr(engine, "grid", None)

    def on_unit_changed(self):
        project = self._project()
        if project is None or self._depth_unit_system is None:
            return
        if self._depth_unit_system != project.unit_system:
            old_depth = Plane.default_grid_plane_depth(self._depth_unit_system)
            new_depth = Plane.default_grid_plane_depth(project.unit_system)
            self._pv_depth_minus *= new_depth / old_depth
            self._pv_depth_plus *= new_depth / old_depth
            self._depth_unit_system = project.unit_system

    def on_key_press(self, key) -> bool:
        if (
            key != glfw.KEY_T
            or not self.visible
            or not self._form_open
            or self._new_source != SRC_ELEMENT
        ):
            return False
        scene = self._scene()
        element = (
            scene.get_element_by_unique_id(self._picked_element_id)
            if scene is not None and self._picked_element_id is not None
            else None
        )
        if not isinstance(element, Frame):
            return False
        self._frame_local_12 = not self._frame_local_12
        self._refresh_preview()
        return True

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
        scene = self._scene()
        if scene is not None:
            refreshed = scene.refresh_plane_associations()
            if refreshed and self._preview is not None:
                self._preview.refresh_assoc(scene)

        imgui.set_next_window_size(imgui.ImVec2(self.PANEL_W, self.PANEL_H), imgui.Cond_.first_use_ever)
        imgui.set_next_window_pos(imgui.ImVec2(1300 - self.PANEL_W - 20, 60), imgui.Cond_.first_use_ever)

        expanded, opened = imgui.begin("Plane Manager", True)
        try:
            if not opened:
                self.visible = False
                self._form_open = False
                self._clear_preview()
                return
            if not expanded:
                return

            self._draw_toolbar()
            imgui.separator()

            imgui.begin_child(
                "pm_list", imgui.ImVec2(230, 0), imgui.ChildFlags_.borders
            )
            try:
                self._draw_list()
            finally:
                imgui.end_child()

            imgui.same_line()

            imgui.begin_child("pm_detail", imgui.ImVec2(0, 0))
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
        imgui.text_colored(imgui.ImVec4(0.7, 0.8, 0.9, 1.0), f'{n} plane')

        imgui.same_line(120)
        if imgui.button("+ Yeni"):
            self._open_new_plane_form()

        imgui.same_line()
        sel = self._selected_plane()
        if sel is None:
            imgui.push_style_color(
                imgui.Col_.button, imgui.ImVec4(0.25, 0.25, 0.25, 1.0)
            )
            imgui.button("Sil", imgui.ImVec2(60, 0))
            imgui.pop_style_color(1)
        else:
            if imgui.button("Sil", imgui.ImVec2(60, 0)):
                self._pending_delete = sel.name

        imgui.same_line()
        if sel is not None and imgui.button("Düzenle", imgui.ImVec2(70, 0)):
            self._open_new_plane_form(from_plane=sel)

        imgui.same_line()
        if sel is not None and imgui.button("Plot", imgui.ImVec2(60, 0)):
            self._do_plot(sel)

        imgui.same_line()
        if sel is not None and imgui.button("Yenile", imgui.ImVec2(70, 0)):
            scene = self._scene()
            if scene is not None:
                sel.refresh_assoc(scene)
                logger.info(f"[PlaneMgr] '{sel.name}' assoc yenilendi.")

        if self._pending_delete:
            self._draw_delete_confirm()

    def _draw_delete_confirm(self):
        imgui.open_popup("##pm_delete_confirm")
        if imgui.begin_popup_modal("##pm_delete_confirm", True,
                                    imgui.WindowFlags_.always_auto_resize)[0]:
            imgui.text(f"'{self._pending_delete}' silinsin mi?")
            imgui.spacing()
            if imgui.button("Sil", imgui.ImVec2(100, 0)):
                name = self._pending_delete
                self._pending_delete = None
                self._do_delete(name)
                imgui.close_current_popup()
            imgui.same_line()
            if imgui.button("Vazgeç", imgui.ImVec2(100, 0)):
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
            imgui.text_colored(imgui.ImVec4(0.6, 0.6, 0.6, 1.0), 'Henüz plane yok.')
            imgui.spacing()
            imgui.text_colored(imgui.ImVec4(0.5, 0.5, 0.5, 1.0), "'+ Yeni' ile başla.")
            return

        for name in sorted(planes.keys()):
            p = planes[name]
            is_sel = (name == self._selected_name)
            flags = imgui.SelectableFlags_.allow_double_click
            if imgui.selectable(f"{name}##pm", is_sel, flags)[1]:
                self._selected_name = name
            imgui.same_line(180)
            n_assoc = sum(len(s) for s in p.associated.values())
            imgui.text_colored(imgui.ImVec4(0.5, 0.7, 0.85, 1.0), f'{n_assoc:4d}')

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
            imgui.text_colored(imgui.ImVec4(0.6, 0.6, 0.6, 1.0), "Bir plane seç veya '+ Yeni'.")
            return

        proj = self._project()
        active_plane = proj.plane_mgr.active_plane
        if active_plane is sel:
            imgui.text_colored(
                imgui.ImVec4(0.4, 0.9, 0.65, 1.0),
                "Aktif çalışma düzlemi",
            )
            if imgui.button("Etkin düzlemi devre dışı bırak"):
                proj.plane_mgr.deactivate()
        elif imgui.button("Bu plane'i etkinleştir"):
            proj.plane_mgr.activate(sel)

        engine = getattr(self.app, "engine", None) if self.app else None
        if engine is not None and imgui.button("Kamerayı plane'e hizala"):
            engine.focus_plane(sel)

        renderer = self._renderer()
        if renderer is not None:
            show_axes = getattr(renderer, "show_active_plane_axes", True)
            changed, show_axes = imgui.checkbox(
                "Plane koordinat eksenlerini göster",
                show_axes,
            )
            if changed:
                renderer.show_active_plane_axes = show_axes

        imgui.separator()

        # --- Kimlik ---
        imgui.text_colored(imgui.ImVec4(0.8, 0.85, 0.95, 1.0), 'Kimlik')
        imgui.text(f"ID: {sel.plane_id[:12]}...")
        imgui.push_item_width(220)
        changed, new_name = imgui.input_text("##pm_name", sel.name, 128)
        imgui.pop_item_width()
        if changed and new_name and new_name != sel.name:
            self._try_rename(sel, new_name)

        imgui.spacing()
        imgui.separator()

        # --- Geometri ---
        imgui.text_colored(imgui.ImVec4(0.8, 0.85, 0.95, 1.0), 'Geometri')
        o, n = sel.origin, sel.normal
        imgui.text(f"origin : ({o[0]:.2f}, {o[1]:.2f}, {o[2]:.2f})")
        imgui.text(f"normal : ({n[0]:.3f}, {n[1]:.3f}, {n[2]:.3f})")
        imgui.text(f"u : [{self._fmt(sel.u_min)}, {self._fmt(sel.u_max)}]")
        imgui.text(f"v : [{self._fmt(sel.v_min)}, {self._fmt(sel.v_max)}]")
        imgui.text(f"depth : [-{sel.depth_minus:.1f}, +{sel.depth_plus:.1f}]")

        imgui.spacing()
        imgui.separator()

        # --- Assoc ---
        imgui.text_colored(imgui.ImVec4(0.8, 0.85, 0.95, 1.0), 'Assoc')
        total = 0
        for k in ASSOC_KINDS:
            n_a = len(sel.associated.get(k, set()))
            n_e = len(sel.excluded.get(k, set()))
            total += n_a
            if n_a or n_e:
                imgui.text_colored(imgui.ImVec4(0.75, 0.85, 0.9, 1.0), f'  {k:6s}: {n_a:4d}')
                if n_e:
                    imgui.same_line()
                    imgui.text_colored(imgui.ImVec4(0.9, 0.6, 0.5, 1.0), f'(excluded {n_e})')
        imgui.text_colored(imgui.ImVec4(0.85, 0.9, 0.95, 1.0), f'  toplam: {total}')
        status_counts = sel.association_counts()
        imgui.text(
            "  " + " / ".join(
                f"{status}: {status_counts[status]}"
                for status in ("ON_PLANE", "INTERSECTING", "WITHIN_DEPTH", "OUTSIDE")
            )
        )
        imgui.text_colored(imgui.ImVec4(0.9, 0.85, 0.5, 1.0), f'  pending: {len(sel.pending)}')

        imgui.spacing()
        imgui.separator()

    # ==================================================================
    #  YENİ PLANE FORMU veya DÜZENLE
    # ==================================================================
    def _open_new_plane_form(self, from_plane: Plane | None = None):
        self._clear_preview()
        self._form_open = True
        self._new_source = SRC_GRID   # varsayılan
        self._picked_nodes = []
        self._picked_element_id = None
        self._frame_local_12 = False
        self._preview_error = None
        self._edit_bounds_open = False
        self._editing_plane = from_plane   # ← YENİ: mevcut plane kopyası

        if from_plane is not None:
            # Mevcut plane'in kopyasını preview olarak kullan
            import copy
            self._preview = copy.deepcopy(from_plane)
            self._set_render_preview(self._preview)
            self._preview_name = from_plane.name
            # Sınır/depth alanlarını doldur
            self._pv_u_min = from_plane.u_min or 0.0
            self._pv_u_max = from_plane.u_max or 0.0
            self._pv_v_min = from_plane.v_min or 0.0
            self._pv_v_max = from_plane.v_max or 0.0
            self._pv_depth_minus = from_plane.depth_minus
            self._pv_depth_plus = from_plane.depth_plus
            self._depth_unit_system = self._project().unit_system
            # "kaynak" seçimi anlamsız — düzenleme modunda gizle
        else:
            self._editing_plane = None
            project = self._project()
            unit_system = project.unit_system if project else None
            default_depth = Plane.default_grid_plane_depth(unit_system)
            self._pv_depth_minus = default_depth
            self._pv_depth_plus = default_depth
            self._depth_unit_system = unit_system
            self._refresh_preview()

    def _clear_preview(self):
        renderer = self._renderer()
        if renderer is not None and renderer.selected_plane is self._preview:
            renderer.selected_plane = None
        self._preview = None
        self._preview_error = None

    def _draw_new_plane_form(self):
        editing = getattr(self, "_editing_plane", None) is not None
        
        if editing:
            imgui.text_colored(imgui.ImVec4(0.9, 0.8, 0.5, 1.0), '─── Plane Düzenle ───')
            imgui.text_colored(imgui.ImVec4(0.7, 0.7, 0.7, 1.0), 'Kaynak: mevcut plane (kopya)')
            imgui.spacing()
        else:
            imgui.text_colored(imgui.ImVec4(0.85, 0.9, 0.95, 1.0), '─── Yeni Plane ───')
            imgui.text("Kaynak")
            imgui.same_line(120)
            for i, label in enumerate(
                ("Grid", "2 Nokta", "3 Nokta", "Seçili Eleman")
            ):
                if i > 0:
                    imgui.same_line()
                if imgui.radio_button(
                    f"{label}##pm_source{i}", self._new_source == i
                ):
                    self._new_source = i
                    self._picked_nodes = []
                    self._picked_element_id = None
                    self._preview_error = None
                    self._refresh_preview()
            imgui.spacing()
            if self._new_source == SRC_GRID:
                self._draw_grid_source()
            elif self._new_source == SRC_2PT:
                self._draw_points_source(required=2)
            elif self._new_source == SRC_3PT:
                self._draw_points_source(required=3)
            elif self._new_source == SRC_ELEMENT:
                self._draw_element_source()
            imgui.spacing()

        # Önizleme (düzenleme modunda da)
        if self._preview is not None:
            self._draw_preview()
            imgui.spacing()
            
            if editing:
                if imgui.button("Güncelle", imgui.ImVec2(120, 0)):
                    self._do_update_from_preview()
                imgui.same_line()
                if imgui.button("Vazgeç", imgui.ImVec2(100, 0)):
                    self._form_open = False
                    self._editing_plane = None
                    self._clear_preview()
            else:
                if imgui.button("Oluştur", imgui.ImVec2(120, 0)):
                    self._do_create_from_preview()
                imgui.same_line()
                if imgui.button("Vazgeç", imgui.ImVec2(100, 0)):
                    self._form_open = False
                    self._clear_preview()
        else:
            imgui.text_colored(imgui.ImVec4(0.6, 0.6, 0.6, 1.0), 'Önizleme yok.')
            if self._preview_error:
                imgui.text_colored(
                    imgui.ImVec4(0.95, 0.55, 0.45, 1.0),
                    self._preview_error,
                )
            if imgui.button("Vazgeç", imgui.ImVec2(100, 0)):
                self._form_open = False

    # ------------------------------------------------------------------
    #  Grid kaynağı
    # ------------------------------------------------------------------
    def _draw_grid_source(self):
        project = self._project()
        grid = project.grid if project is not None else None
        if grid is None:
            imgui.text_colored(
                imgui.ImVec4(0.9, 0.6, 0.5, 1.0),
                "Project Grid hazır değil.",
            )
            return

        options = []
        for orientation in ("XY", "XZ", "YZ"):
            level_axis = {"XY": "Z", "XZ": "Y", "YZ": "X"}[orientation]
            options.extend(
                (
                    f"grid::{orientation}::{coordinate!r}",
                    f"{orientation} @ {level_axis}={coordinate:g}",
                )
                for coordinate in Plane.grid_levels(grid, orientation)
            )
        options.extend(
            (f"user::{plane.name}", f"Kullanıcı: {plane.name}")
            for plane in grid.user_planes
        )
        if not options:
            imgui.text_colored(
                imgui.ImVec4(0.9, 0.6, 0.5, 1.0),
                "Grid'de seçilebilir düzlem yok.",
            )
            return
        option_keys = [key for key, _label in options]
        if self._grid_plane_name not in option_keys:
            self._grid_plane_name = next(
                (
                    key for key in option_keys
                    if key.startswith("grid::XY::")
                ),
                option_keys[0],
            )

        imgui.text("Grid düzlemi")
        imgui.same_line(120)
        selected_label = dict(options)[self._grid_plane_name]
        if imgui.begin_combo("##pm_grid_plane", selected_label):
            for name, label in options:
                is_selected = name == self._grid_plane_name
                if imgui.selectable(label, is_selected)[1]:
                    self._grid_plane_name = name
                    self._refresh_preview()
                if is_selected:
                    imgui.set_item_default_focus()
            imgui.end_combo()

    # ------------------------------------------------------------------
    #  2/3 nokta kaynağı
    # ------------------------------------------------------------------
    def _draw_points_source(self, required: int):
        if required == 2:
            imgui.text("Yön")
            imgui.same_line(120)
            for orientation in ("XY", "XZ", "YZ"):
                if orientation != "XY":
                    imgui.same_line()
                if imgui.radio_button(
                    f"{orientation}##pm_2pt_orientation",
                    self._two_point_orientation == orientation,
                ):
                    self._two_point_orientation = orientation
                    self._refresh_preview()

        imgui.text_colored(imgui.ImVec4(0.7, 0.75, 0.8, 1.0), f'Modelden {required} nokta seç (3D sahnede).')




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
            imgui.text_colored(imgui.ImVec4(0.6, 0.85, 0.7, 1.0), f"  Sahnede seçili: {len(live_sel)} node  (ID: {', '.join(str(n.unique_id) for n in live_sel[:5])}{('...' if len(live_sel) > 5 else '')})")





        else:
            imgui.text_colored(imgui.ImVec4(0.8, 0.6, 0.5, 1.0), '  Sahnede seçili node yok.')
        # "Sahneden Al" butonu
        can_take = len(live_sel) >= required
        if not can_take:
            imgui.push_style_color(
                imgui.Col_.button, imgui.ImVec4(0.25, 0.25, 0.25, 1.0)
            )
        if imgui.button("Sahneden Al", imgui.ImVec2(120, 0)) and can_take:
            self._picked_nodes = [n.unique_id for n in live_sel[:required]]
            self._refresh_preview()
        if not can_take:
            imgui.pop_style_color(1)

        # Seçilen noktalar önizlemesi
        if self._picked_nodes:
            imgui.same_line()
            imgui.text_colored(imgui.ImVec4(0.7, 0.85, 0.7, 1.0), f'({len(self._picked_nodes)} seçili)')


            imgui.same_line()
            if imgui.button("Temizle", imgui.ImVec2(80, 0)):
                self._picked_nodes = []
                self._refresh_preview()

            # Nokta koordinatları
            nodes_by_id = self._scene_nodes_by_id()
            for nid in self._picked_nodes:
                nd = nodes_by_id.get(nid)
                if nd is not None:
                    imgui.text_colored(imgui.ImVec4(0.7, 0.75, 0.8, 1.0), f'  N{nid}: ({nd.x:.0f}, {nd.y:.0f}, {nd.z:.0f})')

    def _draw_element_source(self):
        scene = self._scene()
        selected = (
            [
                element
                for element in scene.get_selected()
                if isinstance(element, (Frame, Area, Polygon))
            ]
            if scene is not None
            else []
        )
        imgui.text_colored(
            imgui.ImVec4(0.7, 0.75, 0.8, 1.0),
            "Sahnede bir Frame, Area veya Polygon seçin.",
        )

        if len(selected) > 1:
            imgui.text_colored(
                imgui.ImVec4(0.9, 0.6, 0.5, 1.0),
                "Plane üretmek için yalnızca bir eleman seçili olmalı.",
            )
        elif not selected:
            imgui.text_colored(
                imgui.ImVec4(0.9, 0.6, 0.5, 1.0),
                "Uygun bir eleman seçili değil.",
            )

        can_take = len(selected) == 1
        if not can_take:
            imgui.push_style_color(
                imgui.Col_.button, imgui.ImVec4(0.25, 0.25, 0.25, 1.0)
            )
        if imgui.button("Seçili Elemanı Kullan", imgui.ImVec2(170, 0)) and can_take:
            self._picked_element_id = selected[0].unique_id
            self._frame_local_12 = False
            self._refresh_preview()
        if not can_take:
            imgui.pop_style_color(1)

        if self._picked_element_id is None:
            return
        element = scene.get_element_by_unique_id(self._picked_element_id) if scene else None
        if not isinstance(element, (Frame, Area, Polygon)):
            return

        imgui.same_line()
        if imgui.button("Temizle##pm_element", imgui.ImVec2(80, 0)):
            self._picked_element_id = None
            self._refresh_preview()
            return

        imgui.text(
            f"Eleman: {element.element_type} {element.label or element.unique_id}"
        )
        if isinstance(element, Frame):
            orientation = "Local 1-2" if self._frame_local_12 else "Local 1-3"
            imgui.text(f"Frame düzlemi: {orientation}")
            imgui.same_line()
            if imgui.button("Yönü Değiştir##pm_frame_plane"):
                self._frame_local_12 = not self._frame_local_12
                self._refresh_preview()
            imgui.text("Kısayol: T")

    # ------------------------------------------------------------------
    #  Önizleme
    # ------------------------------------------------------------------
    def _refresh_preview(self):
        renderer = self._renderer()
        if renderer is not None and renderer.selected_plane is self._preview:
            renderer.selected_plane = None
        self._preview = None
        self._preview_name = ""
        self._preview_error = None

        try:
            if self._new_source == SRC_GRID:
                p = self._build_from_grid()
            elif self._new_source == SRC_2PT:
                p = self._build_from_2pt()
            elif self._new_source == SRC_3PT:
                p = self._build_from_3pt()
            elif self._new_source == SRC_ELEMENT:
                p = self._build_from_element()
            else:
                p = None
        except (TypeError, ValueError) as error:
            self._preview_error = str(error)
            logger.warning("[PlaneMgr] Önizleme hatası: %s", error)
            p = None

        if p is None:
            return

        grid_boundary = p.boundary if self._new_source == SRC_GRID else None
        grid_depth = (
            (self._pv_depth_minus, self._pv_depth_plus)
            if self._new_source == SRC_GRID
            else None
        )
        self._apply_smart_bounds(p)
        if grid_boundary is not None:
            p.u_min, p.u_max, p.v_min, p.v_max = grid_boundary
            p.depth_minus, p.depth_plus = grid_depth
            self._sync_pv_from_plane(p)

        scene = self._scene()
        if scene is not None:
            p.refresh_assoc(scene)

        self._preview = p
        self._preview_name = p.name
        self._set_render_preview(p)

    def _apply_smart_bounds(self, p: Plane):
        """Sahne bbox'ından plane uzayında u/v sınırları ve depth ata."""
        bbox = self._scene_bbox()
        if bbox is None:
            # bbox yoksa makul default
            p.u_min, p.u_max = -5000.0, 5000.0
            p.v_min, p.v_max = -5000.0, 5000.0
            p.depth_minus = p.depth_plus = 500.0
            self._sync_pv_from_plane(p)
            return

        center, size = bbox
        scene = self._scene()

        # 1) Sahnedeki tüm noktaları plane uzayına projekte et
        us, vs = [], []
        if scene is not None:
            for nd in scene.nodes.values():
                u, v = p.to_2d((nd.x, nd.y, nd.z))
                us.append(u); vs.append(v)

        if us:
            # 2) Plane uzayında gerçek min/max + marj
            margin_u = max(0.05 * (max(us) - min(us)), 100.0)
            margin_v = max(0.05 * (max(vs) - min(vs)), 100.0)
            p.u_min = min(us) - margin_u
            p.u_max = max(us) + margin_u
            p.v_min = min(vs) - margin_v
            p.v_max = max(vs) + margin_v
        else:
            # Sahne boş — dünya bbox boyutunu plane uzayına projekte et
            half_u = self._world_extent_along(p, size, p.u)
            half_v = self._world_extent_along(p, size, p.v)
            p.u_min, p.u_max = -half_u, +half_u
            p.v_min, p.v_max = -half_v, +half_v

        # 3) Depth: sahnenin plane normali boyunca kalınlığı
        if scene is not None and scene.nodes:
            ds = [p.distance((nd.x, nd.y, nd.z)) for nd in scene.nodes.values()]
            d_min, d_max = min(ds), max(ds)
            margin_d = max(0.1 * (d_max - d_min), 100.0)
            p.depth_minus = max(-d_min, 0.0) + margin_d
            p.depth_plus = max(d_max, 0.0) + margin_d
        else:
            d = max(500.0, size * 0.05)
            p.depth_minus = p.depth_plus = d

        self._sync_pv_from_plane(p)

    def _sync_pv_from_plane(self, p: Plane):
        self._pv_u_min = p.u_min or 0.0
        self._pv_u_max = p.u_max or 0.0
        self._pv_v_min = p.v_min or 0.0
        self._pv_v_max = p.v_max or 0.0
        self._pv_depth_minus = p.depth_minus
        self._pv_depth_plus = p.depth_plus

    @staticmethod
    def _world_extent_along(plane: Plane, size: float, axis: np.ndarray) -> float:
        """Dünya bbox boyutunun `axis` yönüne izdüşümünün yarısı."""
        # size tek sayı ise küp varsay
        if np.isscalar(size):
            return 0.5 * size
        # vektör ise: yarı-boyut vektörünün axis'e izdüşümü
        half_vec = 0.5 * np.asarray(size, dtype=float)
        return float(np.dot(np.abs(half_vec), np.abs(axis)))

    def _build_from_grid(self) -> Plane | None:
        project = self._project()
        grid = project.grid if project is not None else None
        if grid is None:
            raise ValueError("Project Grid hazır değil.")
        if self._depth_unit_system != project.unit_system:
            default_depth = Plane.default_grid_plane_depth(project.unit_system)
            self._pv_depth_minus = default_depth
            self._pv_depth_plus = default_depth
            self._depth_unit_system = project.unit_system
        name = self._grid_plane_name
        if name.startswith("grid::"):
            _, orientation, raw_coordinate = name.split("::", 2)
            return Plane.from_grid(
                grid,
                orientation,
                grid_coordinate=float(raw_coordinate),
                name=(
                    f"Plane_Grid_{orientation}_"
                    f"{float(raw_coordinate):g}"
                ),
                depth_minus=self._pv_depth_minus,
                depth_plus=self._pv_depth_plus,
            )
        return Plane.from_grid(
            grid,
            name,
            name=f"Plane_Grid_{name.replace('user::', '')}",
            depth_minus=self._pv_depth_minus,
            depth_plus=self._pv_depth_plus,
        )

    def _build_from_2pt(self) -> Plane | None:
        if len(self._picked_nodes) != 2:
            return None
        nodes = self._scene_nodes_by_id()
        n1 = nodes.get(self._picked_nodes[0])
        n2 = nodes.get(self._picked_nodes[1])
        if n1 is None or n2 is None:
            return None
        p1 = np.array([n1.x, n1.y, n1.z])
        p2 = np.array([n2.x, n2.y, n2.z])
        return Plane.from_2_points(
            p1,
            p2,
            self._two_point_orientation,
            name=f"Plane_2pt_{self._picked_nodes[0]}_{self._picked_nodes[1]}",
        )

    def _build_from_3pt(self) -> Plane | None:
        if len(self._picked_nodes) != 3:
            return None
        nodes = self._scene_nodes_by_id()
        nds = [nodes.get(nid) for nid in self._picked_nodes]
        if any(n is None for n in nds):
            return None
        p1 = np.array([nds[0].x, nds[0].y, nds[0].z])
        p2 = np.array([nds[1].x, nds[1].y, nds[1].z])
        p3 = np.array([nds[2].x, nds[2].y, nds[2].z])
        return Plane.from_3_points(
            p1, p2, p3,
            name=f"Plane_3pt_{self._picked_nodes[0]}",
        )

    def _build_from_element(self) -> Plane | None:
        scene = self._scene()
        if scene is None or self._picked_element_id is None:
            return None
        element = scene.get_element_by_unique_id(self._picked_element_id)
        if element is None:
            return None
        return Plane.from_element(
            element,
            frame_local_12=self._frame_local_12,
            name=f"Plane_Element_{element.unique_id}",
        )

    def _draw_preview(self):
        p = self._preview
        imgui.text_colored(imgui.ImVec4(0.85, 0.9, 0.95, 1.0), '─── Önizleme ───')
        imgui.push_item_width(220)
        _, self._preview_name = imgui.input_text("İsim##pm_pvname",
                                                  self._preview_name, 128)
        imgui.pop_item_width()

        o, n = p.origin, p.normal
        imgui.text(f"origin : ({o[0]:.2f}, {o[1]:.2f}, {o[2]:.2f})")
        imgui.text(f"normal : ({n[0]:.3f}, {n[1]:.3f}, {n[2]:.3f})")

        # Assoc özeti
        total = sum(len(s) for s in p.associated.values())
        imgui.text_colored(imgui.ImVec4(0.6, 0.85, 0.7, 1.0), f'assoc : {total}')
        for k in ASSOC_KINDS:
            n_a = len(p.associated.get(k, set()))
            if n_a:
                imgui.text_colored(imgui.ImVec4(0.7, 0.8, 0.85, 1.0), f'  {k:6s}: {n_a}')

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
            logger.debug(f"[PlaneMgr] '{p.name}' zaten var, oluşturulmadı.")
            return

        # Sınır/depth son değerler (form'dan)
        p.u_min = self._pv_u_min
        p.u_max = self._pv_u_max
        p.v_min = self._pv_v_min
        p.v_max = self._pv_v_max
        p.depth_minus = self._pv_depth_minus
        p.depth_plus = self._pv_depth_plus

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
            logger.debug("[PlaneMgr] Sahne yok, edit açılamadı.")
            return
        pp = None
        if self.app and hasattr(self.app, "panels"):
            pp_info = self.app.panels.get("plane_plot")   # ← "plane_plot"
            if pp_info:
                pp = pp_info["instance"]
        if pp is None:
            logger.debug("[PlaneMgr] PlanePlotPanel bulunamadı.")
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
            logger.debug(f"[PlaneMgr] '{new_name}' zaten var.")
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
            logger.debug("[PlaneMgr] PlanePlotPanel bulunamadı")
            return
        pp.open(scene=scene, plane=plane)
        logger.info(f"[PlaneMgr] Plot: {plane.name}")
        
    @staticmethod
    def _fmt(v):
        return "None" if v is None else f"{v:.1f}"