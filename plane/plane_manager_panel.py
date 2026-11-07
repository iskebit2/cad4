# plane/plane_manager_panel.py

from __future__ import annotations

import glfw
import numpy as np
from imgui_bundle import imgui

from domain.element import Area, Frame, Node
from domain.polygon import Polygon
from plane.plane import ASSOC_KINDS, Plane
from logging_config import CadLogger
from ui.base_panel import BasePanel

logger = CadLogger.get(__name__)

SRC_GRID = 0
SRC_2PT = 1
SRC_3PT = 2
SRC_ELEMENT = 3


class PlaneManagerPanel(BasePanel):

    PANEL_W = 620
    PANEL_H = 700

    def __init__(self):
        self.app = None
        self.visible = False
        self._selected_name: str | None = None

        # Form state
        self._form_open = False
        self._editing_plane: Plane | None = None
        self._new_source: int = SRC_GRID

        # Grid source
        self._grid_plane_name = "XY"
        self._depth_unit_system = None
        self._grid_options_grid = None
        self._grid_options_key = None
        self._grid_options: tuple[tuple[str, str], ...] = ()
        self._grid_option_labels: dict[str, str] = {}

        # 2pt/3pt
        self._picked_nodes: list[int] = []
        self._two_point_orientation = "XY"

        # Element source
        self._picked_element_id: int | None = None
        self._frame_local_12 = False

        # Preview
        self._preview: Plane | None = None
        self._preview_name: str = ""
        self._preview_error: str | None = None

        # Preview editable bounds
        self._pv_u_min = 0.0
        self._pv_u_max = 0.0
        self._pv_v_min = 0.0
        self._pv_v_max = 0.0
        self._pv_depth_minus = 500.0
        self._pv_depth_plus = 500.0

        self._pending_delete: str | None = None
        self._preview_plane: Plane | None = None

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------
    def _project(self):
        return getattr(self.app, "current_project", None) if self.app else None

    def _engine(self):
        return getattr(self.app, "engine", None) if self.app else None

    def _math_model(self):
        eng = self._engine()
        if eng is not None and eng.math_model is not None:
            return eng.math_model
        proj = self._project()
        return proj.math_model if proj else None

    def _scene(self):
        eng = self._engine()
        if eng is not None and eng.scene is not None:
            return eng.scene
        proj = self._project()
        return proj.scene if proj else None

    def _sync_render(self):
        """Project değişti → engine'e haber ver (geometri + plane filter)."""
        proj = self._project()
        eng = self._engine()
        if proj is None:
            return
        if eng is not None:
            # Plane filtresi varsa uygula (grid/plane görünümü için)
            apply_fn = getattr(eng, "apply_plane_filter", None)
            if callable(apply_fn):
                apply_fn()
            eng.update_geo(proj)

    def _selected_plane(self) -> Plane | None:
        proj = self._project()
        if not proj or not self._selected_name:
            return None
        p = proj.custom_planes.get(self._selected_name)
        if p is not None:
            return p
        for gp in proj.grid_planes():
            if gp.name == self._selected_name:
                return gp
        return None

    def _selected_is_custom(self) -> bool:
        proj = self._project()
        if not proj or not self._selected_name:
            return False
        return self._selected_name in proj.custom_planes

    def _scene_nodes_by_id(self) -> dict:
        scene = self._scene()
        return dict(scene.nodes) if scene else {}

    def _scene_bbox(self):
        proj = self._project()
        if proj is None:
            return None
        try:
            bounds = [
                b for b in (proj.scene.bounds, proj.math_model.bounds)
                if b is not None
            ]
            if not bounds:
                return None
            minimum = np.min([b.min for b in bounds], axis=0)
            maximum = np.max([b.max for b in bounds], axis=0)
            return (
                (minimum + maximum) * 0.5,
                float(np.linalg.norm(maximum - minimum)),
            )
        except Exception:
            return None

    def _default_depth(self) -> float:
        proj = self._project()
        return Plane.default_grid_plane_depth(
            proj.unit_system if proj else None
        )

    # ------------------------------------------------------------------
    # open / close
    # ------------------------------------------------------------------
    def open(self):
        self.visible = True

    def close(self):
        self.visible = False
        self._selected_name = None
        self._form_open = False
        self._clear_preview()
        self._preview_off()

    def on_unit_changed(self):
        proj = self._project()
        if proj is None or self._depth_unit_system is None:
            return
        if self._depth_unit_system != proj.unit_system:
            old = Plane.default_grid_plane_depth(self._depth_unit_system)
            new = Plane.default_grid_plane_depth(proj.unit_system)
            ratio = new / old if old else 1.0
            self._pv_depth_minus *= ratio
            self._pv_depth_plus *= ratio
            self._depth_unit_system = proj.unit_system

    def on_key_press(self, key) -> bool:
        if (key != glfw.KEY_T or not self.visible or not self._form_open
                or self._new_source != SRC_ELEMENT):
            return False
        scene = self._scene()
        element = (
            scene.get_element_by_unique_id(self._picked_element_id)
            if scene and self._picked_element_id is not None else None
        )
        if not isinstance(element, Frame):
            return False
        self._frame_local_12 = not self._frame_local_12
        self._refresh_preview()
        return True

    # ------------------------------------------------------------------
    # draw
    # ------------------------------------------------------------------
    def draw(self):
        if not self.visible:
            self._preview_off()
            return
        if self._project() is None:
            self._preview_off()
            return
        self._update_preview()
        imgui.set_next_window_size(
            imgui.ImVec2(self.PANEL_W, self.PANEL_H),
            imgui.Cond_.first_use_ever,
        )
        imgui.set_next_window_pos(
            imgui.ImVec2(1300 - self.PANEL_W - 20, 60),
            imgui.Cond_.first_use_ever,
        )

        opened, visible = imgui.begin("Plane Manager##pm", True)
        try:
            if not visible:
                self.visible = False
                self._form_open = False
                self._selected_name = None
                self._preview_off()
                return
            if not opened:
                return

            self._draw_toolbar()
            imgui.separator()

            # Sol: liste | Sağ: detay
            imgui.begin_child("pm_list", imgui.ImVec2(220, 0),
                              imgui.ChildFlags_.borders)
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

        # Modal popup'lar (window dışında da çalışır)
        if self._pending_delete:
            self._draw_delete_confirm()

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------
    def _draw_toolbar(self):
        proj = self._project()
        custom_n = len(proj.custom_planes) if proj else 0
        grid_n = len(proj.grid_planes()) if proj else 0
        imgui.text_colored(imgui.ImVec4(0.7, 0.8, 0.9, 1.0),
                        f"{grid_n} grid / {custom_n} custom")

        imgui.same_line(180)
        eng = self._engine()
        pdm = getattr(eng, "plane_draw_mgr", None) if eng else None

        if imgui.button("3pt"):
            if pdm:
                pdm.start_3pt()
        imgui.same_line()
        if imgui.button("2pt+Z"):
            if pdm:
                pdm.start_2pt_z()
        imgui.same_line()
        imgui.push_style_color(imgui.Col_.button, imgui.ImVec4(0.25, 0.25, 0.25, 1.0))
        imgui.button("Eleman", imgui.ImVec2(70, 0))
        imgui.pop_style_color(1)

        sel = self._selected_plane()
        is_custom = self._selected_is_custom()

        imgui.same_line()
        can_delete = (sel is not None and is_custom)
        if not can_delete:
            imgui.push_style_color(imgui.Col_.button, imgui.ImVec4(0.25, 0.25, 0.25, 1.0))
        if imgui.button("Sil", imgui.ImVec2(50, 0)) and can_delete:
            self._pending_delete = sel.name
        if not can_delete:
            imgui.pop_style_color(1)

        imgui.same_line()
        if sel is not None and is_custom:
            if imgui.button("Düzenle", imgui.ImVec2(65, 0)):
                self._open_new_plane_form(from_plane=sel)

        imgui.same_line()
        if sel is not None and imgui.button("2D Plot", imgui.ImVec2(70, 0)):
            self._do_plot(sel)

        imgui.same_line()
        if imgui.button("Reset", imgui.ImVec2(60, 0)):
            self._do_reset_camera()

        imgui.same_line()
        if self._selected_name is not None and imgui.button("Cancel", imgui.ImVec2(70, 0)):
            self._selected_name = None
    
    def _draw_delete_confirm(self):
        imgui.open_popup("##pm_delete_confirm")
        ok = imgui.begin_popup_modal("##pm_delete_confirm", True,
                                     imgui.WindowFlags_.always_auto_resize)[0]
        if not ok:
            imgui.end_popup()
            return
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
    # Liste
    # ------------------------------------------------------------------
    def _draw_list(self):
        proj = self._project()
        if not proj:
            return

        active = proj.active_plane
        imgui.text_colored(
            imgui.ImVec4(0.6, 0.6, 0.6, 1.0),
            f"aktif: {active.name if active else '— (tüm scene)'}"
        )
        imgui.separator()

        grid_planes = proj.grid_planes()
        if grid_planes:
            imgui.set_next_item_open(True, imgui.Cond_.once)
            if imgui.tree_node(f"Grid Düzlemleri ({len(grid_planes)})##pm_grid"):
                for gp in grid_planes:
                    is_sel = (self._selected_name == gp.name)
                    is_active = (active is not None
                                and active.plane_id == gp.plane_id)
                    prefix = "● " if is_active else "  "
                    if imgui.selectable(f"{prefix}{gp.name}##pmg", is_sel)[1]:
                        self._selected_name = gp.name
                        self._preview_plane = gp
                        
                imgui.tree_pop()
            imgui.separator()

        if not proj.custom_planes:
            imgui.text_colored(
                imgui.ImVec4(0.6, 0.6, 0.6, 1.0),
                "Henüz custom plane yok."
            )
            return

        imgui.set_next_item_open(True, imgui.Cond_.once)
        if imgui.tree_node(f"Custom Plane'ler ({len(proj.custom_planes)})##pm_custom"):
            for name in sorted(proj.custom_planes.keys()):
                p = proj.custom_planes[name]
                is_sel = (name == self._selected_name)
                is_active = (active is p)
                prefix = "● " if is_active else "  "
                if imgui.selectable(f"{prefix}{name}##pm", is_sel)[1]:
                    self._selected_name = name
                    self._preview_plane = p
                    
                imgui.same_line(180)
                n_assoc = sum(len(s) for s in p.associated.values())
                imgui.text_colored(
                    imgui.ImVec4(0.5, 0.7, 0.85, 1.0),
                    f"{n_assoc:4d}"
                )
            imgui.tree_pop()

    # ------------------------------------------------------------------
    # Detay
    # ------------------------------------------------------------------
    def _draw_detail(self):
        if self._form_open:
            self._draw_new_plane_form()
            imgui.separator()
            imgui.spacing()

        sel = self._selected_plane()
        if sel is None:
            imgui.text_colored(imgui.ImVec4(0.6, 0.6, 0.6, 1.0),
                               "Bir plane seç veya '+ Yeni'.")
            return

        proj = self._project()
        eng = self._engine()
        is_active = (proj.active_plane is sel)

        if is_active:
            imgui.text_colored(imgui.ImVec4(0.4, 0.9, 0.65, 1.0),
                            "Aktif çalışma düzlemi")
            if imgui.button("Deaktif et"):
                proj.deactivate_plane()
                
                self._sync_render()
        else:
            if imgui.button("Aktif et"):
                proj.activate_plane(sel)
                eng.focus_plane(sel)
                
                self._sync_render()

        imgui.same_line()
        
        
        if eng is not None and imgui.button("Kamera hizala"):
            eng.focus_plane(sel)

        imgui.separator()

        # Kimlik
        imgui.text_colored(imgui.ImVec4(0.8, 0.85, 0.95, 1.0), "Kimlik")
        imgui.text(f"ID: {sel.plane_id[:12]}…")
        imgui.push_item_width(220)
        changed, new_name = imgui.input_text("##pm_name", sel.name, 128)
        imgui.pop_item_width()
        if changed and new_name and new_name != sel.name:
            self._try_rename(sel, new_name)

        imgui.separator()

        # Geometri
        imgui.text_colored(imgui.ImVec4(0.8, 0.85, 0.95, 1.0), "Geometri")
        o, n = sel.origin, sel.normal
        imgui.text(f"origin : ({o[0]:.2f}, {o[1]:.2f}, {o[2]:.2f})")
        imgui.text(f"normal : ({n[0]:.3f}, {n[1]:.3f}, {n[2]:.3f})")
        imgui.text(f"u : [{self._fmt(sel.u_min)}, {self._fmt(sel.u_max)}]")
        imgui.text(f"v : [{self._fmt(sel.v_min)}, {self._fmt(sel.v_max)}]")
        imgui.text(f"depth : [-{sel.depth_minus:.1f}, +{sel.depth_plus:.1f}]")

        imgui.separator()

        # Assoc
        imgui.text_colored(imgui.ImVec4(0.8, 0.85, 0.95, 1.0), "Assoc")
        total = 0
        for k in ASSOC_KINDS:
            n_a = len(sel.associated.get(k, set()))
            n_e = len(sel.excluded.get(k, set()))
            total += n_a
            if n_a or n_e:
                imgui.text_colored(imgui.ImVec4(0.75, 0.85, 0.9, 1.0),
                                   f"  {k:6s}: {n_a:4d}")
                if n_e:
                    imgui.same_line()
                    imgui.text_colored(imgui.ImVec4(0.9, 0.6, 0.5, 1.0),
                                       f"(excluded {n_e})")
        imgui.text_colored(imgui.ImVec4(0.85, 0.9, 0.95, 1.0),
                           f"  toplam: {total}")
        counts = sel.association_counts()
        imgui.text("  " + " / ".join(
            f"{s}: {counts[s]}" for s in
            ("ON_PLANE", "INTERSECTING", "WITHIN_DEPTH", "OUTSIDE")
        ))
        imgui.text_colored(imgui.ImVec4(0.9, 0.85, 0.5, 1.0),
                           f"  pending: {len(sel.pending)}")

    # ==================================================================
    # Form (yeni veya düzenle)
    # ==================================================================
    def _open_new_plane_form(self, from_plane: Plane | None = None):
        self._clear_preview()
        self._form_open = True
        self._picked_nodes = []
        self._picked_element_id = None
        self._frame_local_12 = False
        self._preview_error = None

        proj = self._project()
        self._depth_unit_system = proj.unit_system if proj else None

        if from_plane is not None:
            import copy
            self._editing_plane = from_plane
            self._preview = copy.deepcopy(from_plane)
            self._preview_name = from_plane.name
            self._pv_u_min = from_plane.u_min or 0.0
            self._pv_u_max = from_plane.u_max or 0.0
            self._pv_v_min = from_plane.v_min or 0.0
            self._pv_v_max = from_plane.v_max or 0.0
            self._pv_depth_minus = from_plane.depth_minus
            self._pv_depth_plus = from_plane.depth_plus
        else:
            self._editing_plane = None

    def _clear_preview(self):
        self._preview = None
        self._preview_error = None

    # ------------------------------------------------------------------
    # Kaynaklar
    # ------------------------------------------------------------------
    def _draw_grid_source(self):
        proj = self._project()
        grid = proj.grid if proj else None
        if grid is None:
            imgui.text_colored(imgui.ImVec4(0.9, 0.6, 0.5, 1.0),
                               "Project Grid hazır değil.")
            return

        options = self._get_grid_options(grid)
        if not options:
            imgui.text_colored(imgui.ImVec4(0.9, 0.6, 0.5, 1.0),
                               "Grid'de seçilebilir düzlem yok.")
            return
        if self._grid_plane_name not in self._grid_option_labels:
            self._grid_plane_name = next(
                (k for k, _ in options if k.startswith("grid::XY::")),
                options[0][0],
            )

        imgui.text("Grid düzlemi")
        imgui.same_line(120)
        selected_label = self._grid_option_labels[self._grid_plane_name]
        if imgui.begin_combo("##pm_grid_plane", selected_label):
            for name, label in options:
                is_sel = (name == self._grid_plane_name)
                if imgui.selectable(label, is_sel)[1]:
                    self._grid_plane_name = name
                    self._refresh_preview()
                if is_sel:
                    imgui.set_item_default_focus()
            imgui.end_combo()

    def _get_grid_options(self, grid) -> tuple[tuple[str, str], ...]:
        coord_map = {
            "XY": getattr(grid, "z_coords", ()),
            "XZ": getattr(grid, "y_coords", ()),
            "YZ": getattr(grid, "x_coords", ()),
        }
        cache_key = tuple(
            (id(coords), len(coords)) for coords in coord_map.values()
        )
        if grid is self._grid_options_grid and cache_key == self._grid_options_key:
            return self._grid_options

        level_axis = {"XY": "Z", "XZ": "Y", "YZ": "X"}
        options = []
        for orientation, coords in coord_map.items():
            for coordinate in sorted(set(coords)):
                options.append((
                    f"grid::{orientation}::{coordinate!r}",
                    f"{orientation} @ {level_axis[orientation]}={coordinate:g}",
                ))

        self._grid_options_grid = grid
        self._grid_options_key = cache_key
        self._grid_options = tuple(options)
        self._grid_option_labels = dict(options)
        return self._grid_options

    def _draw_points_source(self, required: int):
        if required == 2:
            imgui.text("Yön")
            imgui.same_line(120)
            for orientation in ("XY", "XZ", "YZ"):
                if orientation != "XY":
                    imgui.same_line()
                if imgui.radio_button(f"{orientation}##pm_2pt_orientation",
                                       self._two_point_orientation == orientation):
                    self._two_point_orientation = orientation
                    self._refresh_preview()

        imgui.text_colored(imgui.ImVec4(0.7, 0.75, 0.8, 1.0),
                           f"Modelden {required} nokta seç (3D sahnede).")

        scene = self._scene()
        live_sel = []
        if scene is not None:
            try:
                live_sel = [e for e in scene.get_selected() if isinstance(e, Node)]
            except Exception:
                live_sel = []

        if live_sel:
            ids = ", ".join(str(n.unique_id) for n in live_sel[:5])
            if len(live_sel) > 5:
                ids += "…"
            imgui.text_colored(imgui.ImVec4(0.6, 0.85, 0.7, 1.0),
                               f"  Sahnede seçili: {len(live_sel)} node (ID: {ids})")
        else:
            imgui.text_colored(imgui.ImVec4(0.8, 0.6, 0.5, 1.0),
                               "  Sahnede seçili node yok.")

        can_take = len(live_sel) >= required
        if not can_take:
            imgui.push_style_color(imgui.Col_.button,
                                   imgui.ImVec4(0.25, 0.25, 0.25, 1.0))
        if imgui.button("Sahneden Al", imgui.ImVec2(120, 0)) and can_take:
            self._picked_nodes = [n.unique_id for n in live_sel[:required]]
            self._refresh_preview()
        if not can_take:
            imgui.pop_style_color(1)

        if self._picked_nodes:
            imgui.same_line()
            imgui.text_colored(imgui.ImVec4(0.7, 0.85, 0.7, 1.0),
                               f"({len(self._picked_nodes)} seçili)")
            imgui.same_line()
            if imgui.button("Temizle", imgui.ImVec2(80, 0)):
                self._picked_nodes = []
                self._refresh_preview()
            nodes_by_id = self._scene_nodes_by_id()
            for nid in self._picked_nodes:
                nd = nodes_by_id.get(nid)
                if nd is not None:
                    imgui.text_colored(
                        imgui.ImVec4(0.7, 0.75, 0.8, 1.0),
                        f"  N{nid}: ({nd.x:.0f}, {nd.y:.0f}, {nd.z:.0f})"
                    )

    def _draw_element_source(self):
        scene = self._scene()
        selected = (
            [e for e in scene.get_selected()
             if isinstance(e, (Frame, Area, Polygon))]
            if scene else []
        )
        imgui.text_colored(imgui.ImVec4(0.7, 0.75, 0.8, 1.0),
                           "Sahnede bir Frame, Area veya Polygon seçin.")

        if len(selected) > 1:
            imgui.text_colored(imgui.ImVec4(0.9, 0.6, 0.5, 1.0),
                               "Yalnızca bir eleman seçili olmalı.")
        elif not selected:
            imgui.text_colored(imgui.ImVec4(0.9, 0.6, 0.5, 1.0),
                               "Uygun bir eleman seçili değil.")

        can_take = len(selected) == 1
        if not can_take:
            imgui.push_style_color(imgui.Col_.button,
                                   imgui.ImVec4(0.25, 0.25, 0.25, 1.0))
        if imgui.button("Seçili Elemanı Kullan", imgui.ImVec2(180, 0)) and can_take:
            self._picked_element_id = selected[0].unique_id
            self._frame_local_12 = False
            self._refresh_preview()
        if not can_take:
            imgui.pop_style_color(1)

        if self._picked_element_id is None:
            return
        element = (scene.get_element_by_unique_id(self._picked_element_id)
                   if scene else None)
        if not isinstance(element, (Frame, Area, Polygon)):
            return

        imgui.same_line()
        if imgui.button("Temizle##pm_el", imgui.ImVec2(80, 0)):
            self._picked_element_id = None
            self._refresh_preview()
            return

        imgui.text(f"Eleman: {element.element_type} "
                   f"{element.label or element.unique_id}")
        if isinstance(element, Frame):
            orientation = "Local 1-2" if self._frame_local_12 else "Local 1-3"
            imgui.text(f"Frame düzlemi: {orientation}")
            imgui.same_line()
            if imgui.button("Yönü Değiştir##pm_frame_plane"):
                self._frame_local_12 = not self._frame_local_12
                self._refresh_preview()
            imgui.text("Kısayol: T")

    # ------------------------------------------------------------------
    # Önizleme
    # ------------------------------------------------------------------
    def _refresh_preview(self):
        self._preview = None
        self._preview_name = ""
        self._preview_error = None
        p = None
        try:
            if self._new_source == SRC_GRID:
                proj = self._project()
                grid = proj.grid if proj else None
                if grid is not None:
                    opts = self._get_grid_options(grid)
                    if opts and self._grid_plane_name not in self._grid_option_labels:
                        self._grid_plane_name = next(
                            (k for k, _ in opts if k.startswith("grid::XY::")),
                            opts[0][0],
                        )
            elif self._new_source == SRC_2PT:
                p = self._build_from_2pt()
            elif self._new_source == SRC_3PT:
                p = self._build_from_3pt()
            elif self._new_source == SRC_ELEMENT:
                p = self._build_from_element()
            else:
                p = None
        except (TypeError, ValueError) as e:
            self._preview_error = str(e)
            logger.warning("[PlaneMgr] Önizleme hatası: %s", e)
            return

        if p is None:
            return

        # Grid kaynağından gelen sınır/depth korunur
        grid_boundary = p.boundary if self._new_source == SRC_GRID else None
        grid_depth = (
            (self._pv_depth_minus, self._pv_depth_plus)
            if self._new_source == SRC_GRID else None
        )

        self._apply_smart_bounds(p)

        if grid_boundary is not None:
            p.u_min, p.u_max, p.v_min, p.v_max = grid_boundary
            p.depth_minus, p.depth_plus = grid_depth
            self._sync_pv_from_plane(p)

        scene = self._scene()
        math_model = self._math_model()
        if math_model is not None:
            p.refresh_assoc(math_model, scene)

        self._preview = p
        self._preview_name = p.name

    def _apply_smart_bounds(self, p: Plane):
        """Sahne bbox'tan u/v sınırları, depth program varsayılanı."""
        us, vs = [], []
        scene = self._scene()
        if scene is not None:
            for nd in scene.nodes.values():
                u, v = p.to_2d((nd.x, nd.y, nd.z))
                us.append(u)
                vs.append(v)

        if us:
            mu = max(0.05 * (max(us) - min(us)), 100.0)
            mv = max(0.05 * (max(vs) - min(vs)), 100.0)
            p.u_min, p.u_max = min(us) - mu, max(us) + mu
            p.v_min, p.v_max = min(vs) - mv, max(vs) + mv
        else:
            bbox = self._scene_bbox()
            if bbox is not None:
                _, size = bbox
                half = max(float(size), 1.0) * 0.6
                p.u_min, p.u_max = -half, half
                p.v_min, p.v_max = -half, half
            else:
                p.u_min, p.u_max = -5000.0, 5000.0
                p.v_min, p.v_max = -5000.0, 5000.0

        d = self._default_depth()
        p.depth_minus = d
        p.depth_plus = d
        self._sync_pv_from_plane(p)

    def _sync_pv_from_plane(self, p: Plane):
        self._pv_u_min = p.u_min or 0.0
        self._pv_u_max = p.u_max or 0.0
        self._pv_v_min = p.v_min or 0.0
        self._pv_v_max = p.v_max or 0.0
        self._pv_depth_minus = p.depth_minus
        self._pv_depth_plus = p.depth_plus

    def _build_from_grid(self) -> Plane | None:
        proj = self._project()
        grid = proj.grid if proj else None
        if grid is None:
            raise ValueError("Project Grid hazır değil.")
        if self._depth_unit_system != proj.unit_system:
            d = Plane.default_grid_plane_depth(proj.unit_system)
            self._pv_depth_minus = d
            self._pv_depth_plus = d
            self._depth_unit_system = proj.unit_system

        name = self._grid_plane_name
        if not name.startswith("grid::"):
            # user plane (varsa) — grid'de yoksa hata
            raise ValueError(f"Bilinmeyen grid kaynağı: {name}")

        _, orientation, raw = name.split("::", 2)
        axis = {"XY": "z", "XZ": "y", "YZ": "x"}[orientation]
        return Plane.from_axis_offset(
            axis, float(raw),
            depth_minus=self._pv_depth_minus,
            depth_plus=self._pv_depth_plus,
            name=f"Plane_Grid_{orientation}_{float(raw):g}",
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
            p1, p2, self._two_point_orientation,
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
        el = scene.get_element_by_unique_id(self._picked_element_id)
        if el is None:
            return None
        return Plane.from_element(
            el, frame_local_12=self._frame_local_12,
            name=f"Plane_Element_{el.unique_id}",
        )

    def _draw_preview(self):
        p = self._preview
        imgui.text_colored(imgui.ImVec4(0.85, 0.9, 0.95, 1.0),
                           "─── Önizleme ───")
        imgui.push_item_width(220)
        _, self._preview_name = imgui.input_text(
            "İsim##pm_pvname", self._preview_name, 128
        )
        imgui.pop_item_width()

        o, n = p.origin, p.normal
        imgui.text(f"origin : ({o[0]:.1f}, {o[1]:.1f}, {o[2]:.1f})")
        imgui.text(f"normal : ({n[0]:.2f}, {n[1]:.2f}, {n[2]:.2f})")

        total = sum(len(s) for s in p.associated.values())
        imgui.text_colored(imgui.ImVec4(0.6, 0.85, 0.7, 1.0),
                           f"assoc : {total}")
        for k in ASSOC_KINDS:
            n_a = len(p.associated.get(k, set()))
            if n_a:
                imgui.text_colored(imgui.ImVec4(0.7, 0.8, 0.85, 1.0),
                                   f"  {k:6s}: {n_a}")

        if imgui.tree_node("Sınırları Düzenle##pm_bounds"):
            imgui.push_item_width(120)
            changed = False
            imgui.text("u")
            imgui.same_line()
            c, self._pv_u_min = imgui.input_float("##pv_umin", self._pv_u_min)
            changed |= c
            imgui.same_line()
            c, self._pv_u_max = imgui.input_float("##pv_umax", self._pv_u_max)
            changed |= c
            imgui.text("v")
            imgui.same_line()
            c, self._pv_v_min = imgui.input_float("##pv_vmin", self._pv_v_min)
            changed |= c
            imgui.same_line()
            c, self._pv_v_max = imgui.input_float("##pv_vmax", self._pv_v_max)
            changed |= c
            imgui.pop_item_width()

            if changed:
                p.u_min = self._pv_u_min
                p.u_max = self._pv_u_max
                p.v_min = self._pv_v_min
                p.v_max = self._pv_v_max
                scene = self._scene()
                if scene:
                    p.refresh_assoc(scene)
            imgui.tree_pop()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def _do_create_from_preview(self):
        proj = self._project()
        if not proj or self._preview is None:
            return
        p = self._preview
        if self._preview_name.strip():
            p.name = self._preview_name.strip()
        if p.name in proj.custom_planes:
            logger.debug("[PlaneMgr] '%s' zaten var.", p.name)
            return
        p.u_min, p.u_max = self._pv_u_min, self._pv_u_max
        p.v_min, p.v_max = self._pv_v_min, self._pv_v_max
        p.depth_minus, p.depth_plus = self._pv_depth_minus, self._pv_depth_plus

        proj.add_plane(p)
        self._selected_name = p.name
        self._form_open = False
        self._clear_preview()
        
        self._sync_render()
        logger.info("[PlaneMgr] Yeni plane: %s", p.name)

    def _do_delete(self, name: str):
        proj = self._project()
        if not proj:
            return
        if name not in proj.custom_planes:
            logger.warning("[PlaneMgr] Grid plane silinemez: %s", name)
            return
        was_active = (proj.active_plane and proj.active_plane.name == name)
        proj.remove_plane(name)
        if was_active:
            proj.deactivate_plane()
        if self._selected_name == name:
            self._selected_name = next(iter(proj.custom_planes), None)
        
        self._sync_render()
        logger.info("[PlaneMgr] Silindi: %s", name)

    def _try_rename(self, plane: Plane, new_name: str):
        proj = self._project()
        if not proj:
            return
        clean = new_name.strip()
        if not clean or clean == plane.name:
            return
        if clean in proj.custom_planes:
            logger.debug("[PlaneMgr] '%s' zaten var.", clean)
            return
        old = plane.name
        proj.custom_planes.pop(old, None)
        plane.name = clean
        proj.custom_planes[clean] = plane
        self._selected_name = clean
        logger.info("[PlaneMgr] rename: '%s' → '%s'", old, clean)

    def _update_preview(self):
        eng = self._engine()
        if eng is None or eng.interaction_renderer is None:
            return
        plane = self._preview_plane
        proj = self._project()
        if plane is None or (proj and proj.active_plane is plane):
            eng.interaction_renderer.preview_plane = None
            return
        eng.interaction_renderer.preview_plane = plane

    def _preview_off(self):
        self._preview_plane = None
        eng = self._engine()
        if eng and eng.interaction_renderer:
            eng.interaction_renderer.preview_plane = None
            
    def _do_update_from_preview(self):
        editing = self._editing_plane
        if editing is None or self._preview is None:
            return
        proj = self._project()
        if not proj:
            return

        editing.u_min, editing.u_max = self._pv_u_min, self._pv_u_max
        editing.v_min, editing.v_max = self._pv_v_min, self._pv_v_max
        editing.depth_minus = self._pv_depth_minus
        editing.depth_plus = self._pv_depth_plus

        new_name = self._preview_name.strip()
        if new_name and new_name != editing.name:
            if new_name in proj.custom_planes:
                logger.debug("[PlaneMgr] '%s' zaten var.", new_name)
            else:
                old = editing.name
                proj.custom_planes.pop(old, None)
                editing.name = new_name
                proj.custom_planes[new_name] = editing
                self._selected_name = new_name

        scene = self._scene()
        if scene is not None:
            editing.refresh_assoc(scene)

        self._form_open = False
        self._editing_plane = None
        self._clear_preview()
        
        self._sync_render()
        logger.info("[PlaneMgr] Güncellendi: %s", editing.name)

    def _do_plot(self, plane: Plane):
        proj = self._project()
        if proj is None:
            return
        proj.activate_plane(plane)
        eng = self._engine()
        if eng is None:
            return
        renderer = getattr(eng, "renderer", None)
        if renderer is not None and renderer.projection != "plane_2d":
            renderer.toggle_projection()
        
        self._sync_render()
        logger.info("[PlaneMgr] 2D plot: %s", plane.name)

    def _do_reset_camera(self):
        proj = self._project()
        if proj is not None:
            proj.deactivate_plane()
        eng = self._engine()
        if eng is None:
            return
        
        renderer = getattr(eng, "renderer", None)
        if renderer is not None and renderer.projection == "plane_2d":
            renderer.toggle_projection()
        eng.cam.set_view_preset("iso")
        if eng.cam._saved_3d_view is not None:
            eng.cam._saved_3d_view = None
        self._sync_render()
        
    def reset(self):
        self._selected_name = None
        self._form_open = False
        self._editing_plane = None
        self._clear_preview()

    def shutdown(self) -> None:
        eng = self._engine()
        if eng and eng.interaction_renderer:
            eng.interaction_renderer.preview_plane = None
        for entry in self.app.panels.values() if self.app else ():
            p = entry["instance"]
            if hasattr(p, "_preview_off"):
                p._preview_off()
        
    @staticmethod
    def _fmt(v):
        return "None" if v is None else f"{v:.1f}"