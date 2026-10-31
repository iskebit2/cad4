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

    PANEL_W = 560
    PANEL_H = 620

    def __init__(self):
        self.app = None
        self.visible = False
        self._compact: bool = False
        self._selected_name: str | None = None

        # Yeni plane formu
        self._form_open = False
        self._new_source: int = SRC_GRID

        # Grid kaynağı
        self._grid_plane_name = "XY"
        self._depth_unit_system = None
        self._grid_options_grid = None
        self._grid_options_key = None
        self._grid_options: tuple[tuple[str, str], ...] = ()
        self._grid_option_labels: dict[str, str] = {}

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
        """Scene bounds (Faz A.3 cache) — (center, size) veya None."""
        scene = self._scene()
        if scene is None:
            return None
        try:
            b = scene.bounds   # property, cache
            if b is None:
                return None
            return (b.center, b.size)
        except Exception:
            return None

    def _default_depth(self) -> float:
        """Program varsayılanı: 500 mm (unit sistemine göre)."""
        project = self._project()
        return Plane.default_grid_plane_depth(
            project.unit_system if project else None
        )
    
    # ------------------------------------------------------------------
    #  open / close
    # ------------------------------------------------------------------
    def open(self):
        self.visible = True
        

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

        # # ★ Konum + boyut — kompakt: sağ alt; tam: sol üst
        # if self._compact:
        #     io = imgui.get_io()
        #     disp = io.display_size
        #     w, h = 360, 280
        #     imgui.set_next_window_pos(
        #         imgui.ImVec2(disp.x - w - 10, disp.y - h - 10),
        #         imgui.Cond_.always,
        #     )
        #     imgui.set_next_window_size(
        #         imgui.ImVec2(w, h), imgui.Cond_.always,
        #     )
        # else:
        #     imgui.set_next_window_pos(
        #         imgui.ImVec2(1300 - self.PANEL_W - 20, 60),
        #         imgui.Cond_.first_use_ever,
        #     )
        #     imgui.set_next_window_size(
        #         imgui.ImVec2(self.PANEL_W, self.PANEL_H),
        #         imgui.Cond_.first_use_ever,
        #     )

        # ★ Pencere kimliği sabit — kompakt/tam aynı pencere
        expanded, opened = imgui.begin("Plane Manager##pm", True)
        try:
            if not opened:
                self.visible = False
                self._form_open = False
                self._clear_preview()
                return
            if not expanded:
                return

            if self._compact:
                self._draw_compact_toolbar()
                imgui.separator()
                self._draw_compact_body()
            else:
                self._draw_toolbar()
                imgui.separator()

                imgui.begin_child(
                    "pm_list", imgui.ImVec2(230, 0),
                    imgui.ChildFlags_.borders,
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
        # Kompakt mod toggle
        icon = "▣" if self._compact else "▢"
        if imgui.button(icon, imgui.ImVec2(30, 0)):
            self._compact = not self._compact

        proj = self._project()
        n = len(proj.planes) if proj else 0
        imgui.text_colored(
            imgui.ImVec4(0.7, 0.8, 0.9, 1.0), f"{n} plane"
        )

        imgui.same_line(100)
        if imgui.button("+ Yeni"):
            self._open_new_plane_form()

        imgui.same_line()
        sel = self._selected_plane()
        if sel is None:
            imgui.push_style_color(
                imgui.Col_.button, imgui.ImVec4(0.25, 0.25, 0.25, 1.0)
            )
            imgui.button("Sil", imgui.ImVec2(50, 0))
            imgui.pop_style_color(1)
        else:
            if imgui.button("Sil", imgui.ImVec2(50, 0)):
                self._pending_delete = sel.name

        imgui.same_line()
        if sel is not None and imgui.button("Düzenle", imgui.ImVec2(65, 0)):
            self._open_new_plane_form(from_plane=sel)

        imgui.same_line()
        if sel is not None and imgui.button("Plot", imgui.ImVec2(50, 0)):
            self._do_plot(sel)

        imgui.same_line()
        if sel is not None and imgui.button("Yenile", imgui.ImVec2(60, 0)):
            scene = self._scene()
            if scene is not None:
                sel.refresh_assoc(scene)
                proj = self._project()
                if (proj is not None
                        and proj.plane_mgr.active_plane is sel
                        and self.app is not None
                        and self.app.engine is not None):
                    eng = self.app.engine
                    if eng.renderer is not None:
                        eng.apply_plane_filter()
                        eng.renderer.update_geo(scene)
                logger.info(f"[PlaneMgr] '{sel.name}' assoc yenilendi.")

        # ★ Kaynak seçimi toolbar'da (form açıksa)
        if self._form_open and getattr(self, "_editing_plane", None) is None:
            imgui.separator()
            imgui.text_colored(
                imgui.ImVec4(0.85, 0.9, 0.95, 1.0), "Kaynak:"
            )
            imgui.same_line()
            for i, label in enumerate(
                ("Grid", "2pt", "3pt", "Eleman")
            ):
                if i > 0:
                    imgui.same_line()
                if imgui.radio_button(
                    f"{label}##pm_src{i}",
                    self._new_source == i,
                ):
                    self._new_source = i
                    self._picked_nodes = []
                    self._picked_element_id = None
                    self._preview_error = None
                    self._refresh_preview()

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

        # Default scene — sadece seç
        is_default = (self._selected_name is None)
        if imgui.selectable(
            "◆ Tüm Scene (Default)##pm_default", is_default
        )[0]:
            self._selected_name = None
            self._set_render_preview(None)

        imgui.separator()

        planes = proj.planes
        if not planes:
            imgui.text_colored(
                imgui.ImVec4(0.6, 0.6, 0.6, 1.0), "Henüz plane yok."
            )
            imgui.spacing()
            imgui.text_colored(
                imgui.ImVec4(0.5, 0.5, 0.5, 1.0), "'+ Yeni' ile başla."
            )
            return

        for name in sorted(planes.keys()):
            p = planes[name]
            is_sel = (name == self._selected_name)
            if imgui.selectable(f"{name}##pm", is_sel)[1]:
                self._selected_name = name
                # ★ Sadece boundary preview — activate/update_geo YOK
                self._set_render_preview(p)
            imgui.same_line(180)
            n_assoc = sum(len(s) for s in p.associated.values())
            imgui.text_colored(
                imgui.ImVec4(0.5, 0.7, 0.85, 1.0), f"{n_assoc:4d}"
            )

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
            proj = self._project()
            is_active_default = (
                proj is not None
                and proj.plane_mgr.active_plane is None
            )
            if is_active_default and self._selected_name is None:
                imgui.text_colored(
                    imgui.ImVec4(0.4, 0.9, 0.65, 1.0),
                    "◆ Tüm Scene aktif (default)",
                )
                imgui.text_colored(
                    imgui.ImVec4(0.6, 0.6, 0.6, 1.0),
                    "Bir plane seçmek için listeden tıkla.",
                )
            else:
                imgui.text_colored(
                    imgui.ImVec4(0.6, 0.6, 0.6, 1.0),
                    "Bir plane seç veya '+ Yeni'.",
                )
            return

        proj = self._project()
        active_plane = proj.plane_mgr.active_plane
        if active_plane is sel:
            imgui.text_colored(
                imgui.ImVec4(0.4, 0.9, 0.65, 1.0),
                "Aktif çalışma düzlemi",
            )
            if imgui.button("Etkin düzlemi devre dışı bırak"):
                if self.app is not None and hasattr(self.app, "_on_plane_selected"):
                    self.app._on_plane_selected(None)
                else:
                    proj.plane_mgr.deactivate()
        elif imgui.button("Bu plane'i etkinleştir"):
            if self.app is not None and hasattr(self.app, "_on_plane_selected"):
                self.app._on_plane_selected(sel)
            else:
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

    # ------------------------------------------------------------------
    #  Kompakt mod — mode toggle, plane listesi, mouse, depth
    # ------------------------------------------------------------------
    def _draw_compact_toolbar(self):
        """Kompakt mod üst toolbar — sadece ikonlar."""
        proj = self._project()
        if proj is None:
            return
        app = self.app
        eng = getattr(app, "engine", None) if app else None
        sel = self._selected_plane()
        active = proj.plane_mgr.active_plane
        editing = getattr(self, "_editing_plane", None) is not None

        # Tooltip'li ikon buton — tek satır helper
        def _ibtn(label, tip, enabled=True, color=None):
            if color is not None:
                imgui.push_style_color(imgui.Col_.button, color)
            if not enabled:
                imgui.push_style_color(
                    imgui.Col_.button,
                    imgui.ImVec4(0.25, 0.25, 0.25, 1.0),
                )
                imgui.push_style_color(
                    imgui.Col_.text, imgui.ImVec4(0.5, 0.5, 0.5, 1.0)
                )
            clicked = imgui.button(label, imgui.ImVec2(26, 24))
            if not enabled:
                imgui.pop_style_color(2)
            if color is not None:
                imgui.pop_style_color(1)
            if imgui.is_item_hovered():
                imgui.set_tooltip(tip)
            return clicked and enabled

        # 1) Kompakt/tam toggle
        if _ibtn("▢", "Tam mod"):
            self._compact = False
        imgui.same_line(0, 2)

        # 2) + Yeni
        if _ibtn("+", "Yeni plane"):
            self._open_new_plane_form()
        imgui.same_line(0, 2)

        # 3) Sil
        if sel is not None:
            if _ibtn("x", "Sil"):
                self._pending_delete = sel.name
            imgui.same_line(0, 2)

        # 4) Düzenle
        if sel is not None:
            if _ibtn("*", "Düzenle"):
                self._open_new_plane_form(from_plane=sel)
            imgui.same_line(0, 2)

        # 5) Aktif / Deaktif
        if sel is not None:
            is_active = (active is sel)
            tip = "Deaktif et" if is_active else "Aktif et"
            col = (
                imgui.ImVec4(0.20, 0.55, 0.30, 1.0) if is_active
                else None
            )
            if _ibtn("O", tip, color=col):
                if app is not None and hasattr(app, "_on_plane_selected"):
                    app._on_plane_selected(None if is_active else sel)
            imgui.same_line(0, 2)

        # 6) Kamera hizala
        if sel is not None:
            if _ibtn("@", "Kamera hizala"):
                if eng is not None:
                    eng.focus_plane(sel)
            imgui.same_line(0, 2)

        # 7) Plot (2D)
        if sel is not None:
            if _ibtn(">", "2D görünüm"):
                self._do_plot(sel)
            imgui.same_line(0, 2)

        # 8) Kaynak (form açıkken)
        if self._form_open and not editing:
            for src_id, icon, tip in (
                (SRC_GRID, "#", "Grid"),
                (SRC_2PT, "|", "2 Nokta"),
                (SRC_3PT, "/", "3 Nokta"),
                (SRC_ELEMENT, "~", "Eleman"),
            ):
                is_cur = (self._new_source == src_id)
                col = (
                    imgui.ImVec4(0.20, 0.45, 0.75, 1.0) if is_cur
                    else None
                )
                if _ibtn(icon, tip, color=col):
                    if not is_cur:
                        self._new_source = src_id
                        self._picked_nodes = []
                        self._picked_element_id = None
                        self._preview_error = None
                        self._refresh_preview()
                imgui.same_line(0, 2)

        # 9) Oluştur / Güncelle
        if self._form_open and self._preview is not None:
            if editing:
                if _ibtn("v", "Güncelle",
                         color=imgui.ImVec4(0.20, 0.55, 0.30, 1.0)):
                    self._do_update_from_preview()
            else:
                if _ibtn("v", "Oluştur",
                         color=imgui.ImVec4(0.20, 0.55, 0.30, 1.0)):
                    self._do_create_from_preview()
            imgui.same_line(0, 2)

        # 10) Vazgeç
        if self._form_open:
            if _ibtn("^", "Vazgeç",
                     color=imgui.ImVec4(0.55, 0.25, 0.25, 1.0)):
                self._form_open = False
                self._editing_plane = None
                self._clear_preview()

    def _draw_compact_body(self):
        proj = self._project()
        if proj is None:
            return
        app = self.app
        eng = getattr(app, "engine", None) if app else None
        r = eng.renderer if eng else None

        # ★ Mode toggle
        if r is not None:
            is_2d = (r.projection == "plane_2d")
            mode_label = "2D" if is_2d else "3D"
            color = (
                imgui.ImVec4(0.20, 0.55, 0.85, 1.0) if is_2d
                else imgui.ImVec4(0.25, 0.65, 0.35, 1.0)
            )
            imgui.push_style_color(imgui.Col_.button, color)
            if imgui.button(mode_label, imgui.ImVec2(44, 22)):
                if app is not None and hasattr(app, "_toggle_2d"):
                    app._toggle_2d()
            imgui.pop_style_color(1)

        imgui.separator()

        # ★ Plane listesi
        active = proj.plane_mgr.active_plane
        imgui.begin_child(
            "##pm_compact_list", imgui.ImVec2(0, 130),
            imgui.ChildFlags_.borders,
        )
        try:
            is_default = (active is None)
            label = "◆ Tüm Scene"
            if is_default:
                label = "* " + label
            if imgui.selectable(
                f"{label}##c", (self._selected_name is None)
            )[0]:
                self._selected_name = None
                if app is not None and hasattr(
                    app, "_on_plane_selected"
                ):
                    app._on_plane_selected(None)

            for name in sorted(proj.planes.keys()):
                p = proj.planes[name]
                is_sel = (name == self._selected_name)
                is_act = (active is p)
                prefix = "* " if is_act else "  "
                if imgui.selectable(f"{prefix}{name}##c", is_sel)[0]:
                    self._selected_name = name
                    if app is not None and hasattr(
                        app, "_on_plane_selected"
                    ):
                        app._on_plane_selected(p)
        finally:
            imgui.end_child()

        imgui.separator()

        # ★ Mouse uv/W
        if active is not None and app is not None:
            io = imgui.get_io()
            if not io.want_capture_mouse:
                mx, my = io.mouse_pos
                uv = app._screen_to_plane_uv(mx, my, active)
                if uv is not None:
                    world = active.to_3d(uv)
                    imgui.text(f"u={uv[0]:.1f} v={uv[1]:.1f}")
                    imgui.text(
                        f"W=({world[0]:.1f},{world[1]:.1f},"
                        f"{world[2]:.1f})"
                    )
                else:
                    imgui.text_colored(
                        imgui.ImVec4(0.6, 0.5, 0.5, 1.0),
                        "(plane dışında)",
                    )
        else:
            imgui.text_colored(
                imgui.ImVec4(0.6, 0.6, 0.6, 1.0),
                "(aktif plane yok)",
            )

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
            imgui.text_colored(
                imgui.ImVec4(0.9, 0.8, 0.5, 1.0), "─── Plane Düzenle ───"
            )
        else:
            imgui.text_colored(
                imgui.ImVec4(0.85, 0.9, 0.95, 1.0), "─── Yeni Plane ───"
            )
            # Kaynak detayı (radio toolbar'da)
            if self._new_source == SRC_GRID:
                self._draw_grid_source()
            elif self._new_source == SRC_2PT:
                self._draw_points_source(required=2)
            elif self._new_source == SRC_3PT:
                self._draw_points_source(required=3)
            elif self._new_source == SRC_ELEMENT:
                self._draw_element_source()
            imgui.spacing()

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
            imgui.text_colored(
                imgui.ImVec4(0.6, 0.6, 0.6, 1.0), "Önizleme yok."
            )
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

        options = self._get_grid_options(grid)
        if not options:
            imgui.text_colored(
                imgui.ImVec4(0.9, 0.6, 0.5, 1.0),
                "Grid'de seçilebilir düzlem yok.",
            )
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
            clipper = imgui.ListClipper()
            clipper.begin(len(options))
            while clipper.step():
                for index in range(
                    clipper.display_start, clipper.display_end
                ):
                    name, label = options[index]
                    is_selected = name == self._grid_plane_name
                    if imgui.selectable(label, is_selected)[1]:
                        self._grid_plane_name = name
                        self._refresh_preview()
                    if is_selected:
                        imgui.set_item_default_focus()
            clipper.end()
            imgui.end_combo()

    def _get_grid_options(self, grid) -> tuple[tuple[str, str], ...]:
        coordinate_lists = tuple(
            getattr(grid, f"{axis.lower()}_coords", ())
            for axis in "XYZ"
        )
        user_planes = getattr(grid, "user_planes", ())
        cache_key = (
            *((id(values), len(values)) for values in coordinate_lists),
            id(user_planes),
            len(user_planes),
            tuple((id(plane), plane.name) for plane in user_planes),
        )
        if grid is self._grid_options_grid and cache_key == self._grid_options_key:
            return self._grid_options

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
            for plane in user_planes
        )

        self._grid_options_grid = grid
        self._grid_options_key = cache_key
        self._grid_options = tuple(options)
        self._grid_option_labels = dict(options)
        return self._grid_options

    def _apply_smart_bounds(self, p: Plane):
        """u/v sınırları sahne bbox'tan; depth program varsayılanı."""
        bbox = self._scene_bbox()

        us, vs = [], []
        scene = self._scene()
        if scene is not None:
            for nd in scene.nodes.values():
                u, v = p.to_2d((nd.x, nd.y, nd.z))
                us.append(u)
                vs.append(v)

        if us:
            margin_u = max(0.05 * (max(us) - min(us)), 100.0)
            margin_v = max(0.05 * (max(vs) - min(vs)), 100.0)
            p.u_min = min(us) - margin_u
            p.u_max = max(us) + margin_u
            p.v_min = min(vs) - margin_v
            p.v_max = max(vs) + margin_v
        elif bbox is not None:
            center, size = bbox
            half = max(float(size), 1.0) * 0.6
            p.u_min = -half
            p.u_max = +half
            p.v_min = -half
            p.v_max = +half
        else:
            p.u_min, p.u_max = -5000.0, 5000.0
            p.v_min, p.v_max = -5000.0, 5000.0

        # ★ Depth — sabit program varsayılanı
        default = self._default_depth()
        p.depth_minus = default
        p.depth_plus = default

        self._sync_pv_from_plane(p)

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
        imgui.text_colored(
            imgui.ImVec4(0.85, 0.9, 0.95, 1.0), "─── Önizleme ───"
        )
        imgui.push_item_width(220)
        _, self._preview_name = imgui.input_text(
            "İsim##pm_pvname", self._preview_name, 128
        )
        imgui.pop_item_width()

        o, n = p.origin, p.normal
        imgui.text(f"origin : ({o[0]:.1f}, {o[1]:.1f}, {o[2]:.1f})")
        imgui.text(f"normal : ({n[0]:.2f}, {n[1]:.2f}, {n[2]:.2f})")

        total = sum(len(s) for s in p.associated.values())
        imgui.text_colored(
            imgui.ImVec4(0.6, 0.85, 0.7, 1.0), f"assoc : {total}"
        )
        for k in ASSOC_KINDS:
            n_a = len(p.associated.get(k, set()))
            if n_a:
                imgui.text_colored(
                    imgui.ImVec4(0.7, 0.8, 0.85, 1.0),
                    f"  {k:6s}: {n_a}",
                )

        # u/v sınırları — collapse, depth YOK
        if imgui.tree_node("Sınırları Düzenle##pm_bounds"):
            imgui.push_item_width(120)
            changed = False

            imgui.text("u")
            imgui.same_line()
            c, self._pv_u_min = imgui.input_float(
                "##pv_umin", self._pv_u_min, 0.0, 0.0
            )
            changed = changed or c
            imgui.same_line()
            c, self._pv_u_max = imgui.input_float(
                "##pv_umax", self._pv_u_max, 0.0, 0.0
            )
            changed = changed or c
            imgui.text("v")
            imgui.same_line()
            c, self._pv_v_min = imgui.input_float(
                "##pv_vmin", self._pv_v_min, 0.0, 0.0
            )
            changed = changed or c
            imgui.same_line()
            c, self._pv_v_max = imgui.input_float(
                "##pv_vmax", self._pv_v_max, 0.0, 0.0
            )
            changed = changed or c
            imgui.pop_item_width()

            # ★ Sadece değişince refresh
            if changed:
                p.u_min = self._pv_u_min
                p.u_max = self._pv_u_max
                p.v_min = self._pv_v_min
                p.v_max = self._pv_v_max
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
        clean_name = new_name.strip()
        if not clean_name:
            return
        old = plane.name
        if clean_name in proj.planes and clean_name != old:
            logger.debug(f"[PlaneMgr] '{clean_name}' zaten var.")
            return
        proj.planes.pop(old, None)
        plane.name = clean_name
        proj.planes[clean_name] = plane
        self._selected_name = clean_name
        logger.info(f"[PlaneMgr] Yeniden adlandırıldı: '{old}' → '{clean_name}'")

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
        old_name = editing.name

        # Mevcut plane'in alanlarını güncelle
        editing.u_min = self._pv_u_min
        editing.u_max = self._pv_u_max
        editing.v_min = self._pv_v_min
        editing.v_max = self._pv_v_max
        editing.depth_minus = self._pv_depth_minus
        editing.depth_plus = self._pv_depth_plus

        preview_name = self._preview_name.strip()
        if preview_name and preview_name != old_name:
            if preview_name in proj.planes and preview_name != old_name:
                logger.debug(f"[PlaneMgr] '{preview_name}' zaten var.")
                preview_name = old_name
            else:
                proj.planes.pop(old_name, None)
                editing.name = preview_name
                proj.planes[preview_name] = editing
                self._selected_name = preview_name

        # Assoc yenile
        scene = self._scene()
        if scene is not None:
            editing.refresh_assoc(scene)

        self._form_open = False
        self._editing_plane = None
        self._clear_preview()
        logger.info(f"[PlaneMgr] '{editing.name}' güncellendi")

    def _do_plot(self, plane: Plane):
        """2D görünümü aç — plane'i aktif et + kamera plane'e dik."""
        if plane is None:
            return
        if self.app is not None and hasattr(self.app, "_on_plane_selected"):
            self.app._on_plane_selected(plane)
        if self.app is not None and hasattr(self.app, "_toggle_2d"):
            r = self.app.engine.renderer if self.app.engine else None
            if r is not None and r.projection != "plane_2d":
                self.app._toggle_2d()
        logger.info(f"[PlaneMgr] Plot (2D): {plane.name}")
        
    @staticmethod
    def _fmt(v):
        return "None" if v is None else f"{v:.1f}"