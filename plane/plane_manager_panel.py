# plane/plane_manager_panel.py
from __future__ import annotations

import numpy as np
from imgui_bundle import imgui

from plane.plane import Plane
from logging_config import CadLogger
from ui.base_panel import BasePanel

logger = CadLogger.get(__name__)


class PlaneManagerPanel(BasePanel):

    PANEL_W = 620
    PANEL_H = 700

    def __init__(self):
        self.app = None
        self.visible = False
        self._selected_name: str | None = None
        self._preview_plane: Plane | None = None
        self._pending_delete: str | None = None

        self._edit_loaded_for: str | None = None
        self._edit_name = ""
        self._edit_u_min = 0.0
        self._edit_u_max = 0.0
        self._edit_v_min = 0.0
        self._edit_v_max = 0.0
        self._edit_depth_minus = 100.0
        self._edit_depth_plus = 100.0
        self._edit_filter_mode = None

    # ------------------------------------------------------------------
    def _project(self):
        return getattr(self.app, "current_project", None) if self.app else None

    def _engine(self):
        return getattr(self.app, "engine", None) if self.app else None

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

    def _sync_render(self):
        proj = self._project()
        eng = self._engine()
        if proj is not None and eng is not None:
            eng.update_geo(proj)

    # ------------------------------------------------------------------
    def open(self):
        self.visible = True

    def close(self):
        self.visible = False
        self._selected_name = None
        self._preview_off()
        self._edit_loaded_for = None

    def on_key_press(self, key) -> bool:
        return False

    def reset(self):
        self._selected_name = None
        self._preview_plane = None
        self._edit_loaded_for = None

    def shutdown(self) -> None:
        self._preview_off()

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
                self._selected_name = None
                self._preview_off()
                return
            if not opened:
                return

            self._draw_toolbar()
            imgui.separator()

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

        if self._pending_delete:
            self._draw_delete_confirm()

    # ------------------------------------------------------------------
    def _draw_toolbar(self):
        proj = self._project()
        custom_n = len(proj.custom_planes) if proj else 0
        grid_n = len(proj.grid_planes()) if proj else 0
        imgui.text_colored(imgui.ImVec4(0.7, 0.8, 0.9, 1.0),
                           f"{grid_n} grid / {custom_n} custom")

        imgui.same_line(170)
        eng = self._engine()
        pdm = getattr(eng, "plane_draw_mgr", None) if eng else None

        if imgui.button("3pt"):
            if pdm:
                pdm.start_3pt()
        imgui.same_line()
        if imgui.button("2pt+Z"):
            if pdm:
                pdm.start_2pt_z()

        # Arkhe / Sıfırlama (Tüm Model / Filtresiz Gösterim)
        imgui.same_line()
        if imgui.button("Tüm Model"):
            if proj:
                proj.deactivate_plane()
                self._selected_name = None
                self._preview_off()
                self._edit_loaded_for = None
                self._sync_render()

        is_custom = self._selected_is_custom()

        if not is_custom:
            imgui.begin_disabled()
        
        if imgui.button("Sil", imgui.ImVec2(50, 0)) and is_custom:
            if self._selected_name:
                self._pending_delete = self._selected_name

        if not is_custom:
            imgui.end_disabled()

        if self._selected_name is not None:
            imgui.same_line()
            if imgui.button("Cancel", imgui.ImVec2(60, 0)):
                self._selected_name = None
                self._preview_off()
                self._edit_loaded_for = None

    def _draw_delete_confirm(self):
        imgui.open_popup("##pm_delete_confirm")
        ok, open_state = imgui.begin_popup_modal("##pm_delete_confirm", True,
                                                 imgui.WindowFlags_.always_auto_resize)
        if not ok or not open_state:
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
    def _draw_list(self):
        proj = self._project()
        if not proj:
            return

        active = proj.active_plane
        imgui.text_colored(imgui.ImVec4(0.6, 0.6, 0.6, 1.0),
                           f"aktif: {active.name if active else '— (Tüm Model)'}")

        grid_planes = proj.grid_planes()
        if grid_planes:
            imgui.set_next_item_open(True, imgui.Cond_.once)
            if imgui.tree_node(f"Grid ({len(grid_planes)})##pm_grid"):
                for gp in grid_planes:
                    is_sel = (self._selected_name == gp.name)
                    is_active = (active is not None and active.plane_id == gp.plane_id)
                    prefix = "● " if is_active else "  "
                    if imgui.selectable(f"{prefix}{gp.name}##pmg", is_sel)[1]:
                        if self._selected_name != gp.name:
                            self._selected_name = gp.name
                            self._preview_plane = gp
                            self._load_gp(gp)
                imgui.tree_pop()
            imgui.separator()

        if not proj.custom_planes:
            imgui.text_colored(imgui.ImVec4(0.6, 0.6, 0.6, 1.0),
                               "Custom plane yok.")
            return

        imgui.set_next_item_open(True, imgui.Cond_.once)
        if imgui.tree_node(f"Custom ({len(proj.custom_planes)})##pm_custom"):
            for name in sorted(proj.custom_planes.keys()):
                p = proj.custom_planes[name]
                is_sel = (name == self._selected_name)
                is_active = (active is p)
                prefix = "● " if is_active else "  "
                if imgui.selectable(f"{prefix}{name}##pm", is_sel)[1]:
                    if self._selected_name != name:
                        self._selected_name = name
                        self._preview_plane = p
                        self._load_edit(p, force=True)
            imgui.tree_pop()

    # ------------------------------------------------------------------
    def _draw_detail(self):
        sel = self._selected_plane()
        if sel is None:
            self._edit_loaded_for = None
            imgui.text_colored(imgui.ImVec4(0.6, 0.6, 0.6, 1.0),
                               "Soldan bir plane seç veya\n'Tüm Model' ile sıfırla.")
            return

        proj = self._project()
        is_custom = self._selected_is_custom()
        is_active = (proj.active_plane is sel)

        if self._edit_loaded_for != sel.name:
            self._load_edit(sel, force=True)

        if is_active:
            imgui.text_colored(imgui.ImVec4(0.4, 0.9, 0.65, 1.0),
                               "Aktif plane")
            if imgui.button("Deaktif et"):
                proj.deactivate_plane()
                self._sync_render()
        else:
            if imgui.button("Aktif et"):
                proj.activate_plane(sel)
                self._sync_render()

        imgui.separator()

        # Kimlik
        imgui.text_colored(imgui.ImVec4(0.8, 0.85, 0.95, 1.0), "Kimlik")
        imgui.text(f"ID: {sel.plane_id[:12]}…")
        
        imgui.push_item_width(220)
        if not is_custom:
            imgui.begin_disabled()
        _, self._edit_name = imgui.input_text("İsim##pm_name", self._edit_name, 128)
        if not is_custom:
            imgui.end_disabled()
        imgui.pop_item_width()

        imgui.separator()

        # Kesit / Filtreleme Politikası (Intersect / Strict / Clip)
        imgui.text_colored(imgui.ImVec4(0.8, 0.85, 0.95, 1.0), "Kesit Politikası (Filter Mode)")
        from plane.plane_policy import SectionFilterMode
        modes = list(SectionFilterMode)
        current_mode = self._edit_filter_mode if self._edit_filter_mode is not None else SectionFilterMode.INTERSECT
        current_idx = modes.index(current_mode) if current_mode in modes else 0

        imgui.push_item_width(220)
        changed, new_idx = imgui.combo("##pm_filter_mode", current_idx, [m.value.upper() for m in modes])
        if changed:
            self._edit_filter_mode = modes[new_idx]  # Sadece hafızada değişir, Apply beklenir!
        imgui.pop_item_width()

        imgui.separator()

        # Geometri — readonly
        imgui.text_colored(imgui.ImVec4(0.8, 0.85, 0.95, 1.0),
                           "Geometri (readonly)")
        o, n = sel.origin, sel.normal
        imgui.text(f"origin : ({o[0]:.2f}, {o[1]:.2f}, {o[2]:.2f})")
        imgui.text(f"normal : ({n[0]:.3f}, {n[1]:.3f}, {n[2]:.3f})")

        imgui.separator()

        # U/V Sınırlar — Custom için editable, Grid için readonly
        imgui.text_colored(imgui.ImVec4(0.8, 0.85, 0.95, 1.0),
                           "U/V Sınırlar" if is_custom else "U/V Sınırlar (readonly)")
        if not is_custom:
            imgui.begin_disabled()
        imgui.push_item_width(100)
        _, self._edit_u_min = imgui.input_float("u min##pm_umin", self._edit_u_min)
        imgui.same_line()
        _, self._edit_u_max = imgui.input_float("u max##pm_umax", self._edit_u_max)
        _, self._edit_v_min = imgui.input_float("v min##pm_vmin", self._edit_v_min)
        imgui.same_line()
        _, self._edit_v_max = imgui.input_float("v max##pm_vmax", self._edit_v_max)
        imgui.pop_item_width()
        if not is_custom:
            imgui.end_disabled()

        imgui.separator()

        # Derinlikler — Her iki tür için de editable
        imgui.text_colored(imgui.ImVec4(0.8, 0.85, 0.95, 1.0), "Kesit Derinlikleri (Depth)")
        imgui.push_item_width(100)
        _, self._edit_depth_minus = imgui.input_float("depth -##pm_dm", self._edit_depth_minus)
        imgui.same_line()
        _, self._edit_depth_plus = imgui.input_float("depth +##pm_dp", self._edit_depth_plus)
        imgui.pop_item_width()

        imgui.separator()

        # Apply / Revert
        can_apply = self._is_edited(sel)
        if not can_apply:
            imgui.push_style_color(imgui.Col_.button,
                                   imgui.ImVec4(0.25, 0.25, 0.25, 1.0))
        if imgui.button("Apply", imgui.ImVec2(100, 0)) and can_apply:
            self._apply_edit(sel)
        if not can_apply:
            imgui.pop_style_color(1)
        imgui.same_line()
        if imgui.button("Revert", imgui.ImVec2(80, 0)):
            self._load_edit(sel, force=True)

        imgui.separator()

        # Assoc — sadece poly
        n_poly = len(sel.associated.get("poly", set()))
        imgui.text_colored(imgui.ImVec4(0.8, 0.85, 0.95, 1.0), "Assoc (poly)")
        imgui.text(f"  {n_poly}")

        # Assoc hesapla (lazy)
        # math_model = self._math_model()
        # if math_model and math_model._plane_associations_dirty:
        #     math_model.refresh_plane_associations(
        #         proj.all_planes(), scene=self._scene(),
        #     )

    # ------------------------------------------------------------------
    def _load_edit(self, plane: Plane, force: bool = False):
        if not force and self._edit_loaded_for == plane.name:
            return
        self._edit_name = plane.name
        self._edit_u_min = plane.u_min if plane.u_min is not None else 0.0
        self._edit_u_max = plane.u_max if plane.u_max is not None else 0.0
        self._edit_v_min = plane.v_min if plane.v_min is not None else 0.0
        self._edit_v_max = plane.v_max if plane.v_max is not None else 0.0
        self._edit_depth_minus = plane.depth_minus if hasattr(plane, 'depth_minus') else 500.0
        self._edit_depth_plus = plane.depth_plus if hasattr(plane, 'depth_plus') else 500.0
        from plane.plane_policy import SectionFilterMode
        self._edit_filter_mode = getattr(plane, "filter_mode", SectionFilterMode.INTERSECT)  # ★ Yükle
        self._edit_loaded_for = plane.name

    def _load_gp(self, gp: Plane):
        self._selected_name = gp.name
        self._preview_plane = gp
        self._load_edit(gp, force=True)

    def _is_edited(self, plane: Plane) -> bool:
        is_custom = self._selected_is_custom()
        from plane.plane_policy import SectionFilterMode
        p_mode = getattr(plane, "filter_mode", SectionFilterMode.INTERSECT)
        
        if is_custom:
            return (
                self._edit_name != plane.name
                or abs(self._edit_u_min - (plane.u_min or 0.0)) > 1e-6
                or abs(self._edit_u_max - (plane.u_max or 0.0)) > 1e-6
                or abs(self._edit_v_min - (plane.v_min or 0.0)) > 1e-6
                or abs(self._edit_v_max - (plane.v_max or 0.0)) > 1e-6
                or abs(self._edit_depth_minus - plane.depth_minus) > 1e-6
                or abs(self._edit_depth_plus - plane.depth_plus) > 1e-6
                or self._edit_filter_mode != p_mode  # ★ Kontrol
            )
        else:
            return (
                abs(self._edit_depth_minus - plane.depth_minus) > 1e-6
                or abs(self._edit_depth_plus - plane.depth_plus) > 1e-6
                or self._edit_filter_mode != p_mode  # ★ Kontrol
            )
        
    def _apply_edit(self, plane: Plane):
        proj = self._project()
        if not proj:
            return

        is_custom = self._selected_is_custom()

        if is_custom:
            new_name = self._edit_name.strip()
            if new_name and new_name != plane.name:
                if new_name in proj.custom_planes:
                    logger.debug("[PlaneMgr] '%s' zaten var.", new_name)
                else:
                    old = plane.name
                    proj.custom_planes.pop(old, None)
                    plane.name = new_name
                    proj.custom_planes[new_name] = plane
                    self._selected_name = new_name
                    self._edit_loaded_for = new_name

            plane.u_min = self._edit_u_min
            plane.u_max = self._edit_u_max
            plane.v_min = self._edit_v_min
            plane.v_max = self._edit_v_max

        plane.depth_minus = self._edit_depth_minus
        plane.depth_plus = self._edit_depth_plus

        if self._edit_filter_mode is not None:
            if hasattr(plane, "set_filter_mode"):
                plane.set_filter_mode(self._edit_filter_mode)
            else:
                plane.filter_mode = self._edit_filter_mode

        self._sync_render()
        logger.debug("[PlaneMgr] Apply: %s", plane.name)

    # ------------------------------------------------------------------
    def _do_delete(self, name: str):
        proj = self._project()
        if not proj:
            return
        if name not in proj.custom_planes:
            return
        was_active = (proj.active_plane and proj.active_plane.name == name)
        proj.remove_plane(name)
        if was_active:
            proj.deactivate_plane()
        if self._selected_name == name:
            self._selected_name = next(iter(proj.custom_planes), None)
        self._edit_loaded_for = None
        self._sync_render()
        logger.debug("[PlaneMgr] Silindi: %s", name)

    # ------------------------------------------------------------------
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