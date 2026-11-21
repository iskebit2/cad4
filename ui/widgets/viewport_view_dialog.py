# ui/widgets/viewport_view_dialog.py
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from imgui_bundle import imgui

from tools.filter_query import ElementFilterQuery
from viewport.viewport import ViewUCS, VolumeClipMode

if TYPE_CHECKING:
    from app.cad_app import CadApp


class ViewportViewDialog:
    def __init__(self, app: "CadApp") -> None:
        self.app = app
        self.visible = False
        self._viewport_name: str | None = None

        self._ucs_preset = 0
        self._origin = [0.0, 0.0, 0.0]
        self._u_axis = [1.0, 0.0, 0.0]
        self._v_axis = [0.0, 1.0, 0.0]

        self._use_uv_bounds = False
        self._u_min = -5000.0
        self._u_max = 5000.0
        self._v_min = -5000.0
        self._v_max = 5000.0

        self._use_depth = False
        self._depth_minus = 1000.0
        self._depth_plus = 1000.0
        self._clip_mode = VolumeClipMode.INTERSECT
        self._is_2d = False

        self._only_beams = False
        self._only_columns = False
        self._only_braces = False
        self._show_nodes = True
        self._show_areas = True
        self._show_links = True
        self._name_pattern = ""
        self._section_filter = ""
        self._material_filter = ""

    def open(self, viewport_name: str | None = None) -> None:
        vm = self.app.viewport_manager
        if vm is None:
            return
        vp = vm.get(viewport_name) if viewport_name else vm.active
        if vp is None:
            return
        self._viewport_name = vp.name
        self._load_from_viewport(vp)
        self.visible = True

    def _load_from_viewport(self, vp) -> None:
        ucs = vp.ucs
        self._ucs_preset = 0
        self._origin = [float(ucs.origin[0]), float(ucs.origin[1]), float(ucs.origin[2])]
        self._u_axis = [float(ucs.u[0]), float(ucs.u[1]), float(ucs.u[2])]
        self._v_axis = [float(ucs.v[0]), float(ucs.v[1]), float(ucs.v[2])]

        vol = vp.volume
        self._use_uv_bounds = None not in (vol.u_min, vol.u_max, vol.v_min, vol.v_max)
        self._u_min = float(vol.u_min) if vol.u_min is not None else -5000.0
        self._u_max = float(vol.u_max) if vol.u_max is not None else 5000.0
        self._v_min = float(vol.v_min) if vol.v_min is not None else -5000.0
        self._v_max = float(vol.v_max) if vol.v_max is not None else 5000.0

        self._use_depth = (vol.depth_minus is not None) or (vol.depth_plus is not None)
        self._depth_minus = float(vol.depth_minus) if vol.depth_minus is not None else 1000.0
        self._depth_plus = float(vol.depth_plus) if vol.depth_plus is not None else 1000.0
        self._clip_mode = vol.mode
        self._is_2d = bool(vp.is_2d)

        q: ElementFilterQuery | None = vp.element_filter
        if q is None or q.is_empty():
            self._only_beams = False
            self._only_columns = False
            self._only_braces = False
            self._show_nodes = True
            self._show_areas = True
            self._show_links = True
            self._name_pattern = ""
            self._section_filter = ""
            self._material_filter = ""
            return

        subs = q.structural_subtypes or set()
        self._only_beams = "beam" in subs
        self._only_columns = "column" in subs
        self._only_braces = "brace" in subs

        etypes = q.element_types or set()
        self._show_nodes = (not etypes) or ("Node" in etypes)
        self._show_areas = (not etypes) or ("Area" in etypes)
        self._show_links = (not etypes) or ("Link" in etypes)
        self._name_pattern = q.name_pattern or ""
        self._section_filter = ", ".join(sorted(q.sections)) if q.sections else ""
        self._material_filter = ", ".join(sorted(q.materials)) if q.materials else ""

    def draw(self) -> None:
        if not self.visible:
            return

        vm = self.app.viewport_manager
        vp = vm.get(self._viewport_name) if (vm and self._viewport_name) else (vm.active if vm else None)
        if vp is None:
            self.visible = False
            return

        imgui.set_next_window_size(imgui.ImVec2(440, 560), imgui.Cond_.first_use_ever)
        expanded, p_open = imgui.begin(f"Görünüm UCS, Sınırlar & Filtre [{vp.name}]###vp_view_cfg", True)
        if not p_open:
            self.visible = False
            imgui.end()
            return
        if not expanded:
            imgui.end()
            return

        imgui.separator_text("1. Çalışma Koordinat Sistemi (UCS)")
        presets = ["Mevcut", "Global XY", "Global XZ", "Global YZ"]
        changed_preset, idx = imgui.combo("Hazır UCS", self._ucs_preset, presets)
        if changed_preset:
            self._ucs_preset = idx
            if idx == 1:
                self._origin = [0.0, 0.0, 0.0]
                self._u_axis = [1.0, 0.0, 0.0]
                self._v_axis = [0.0, 1.0, 0.0]
            elif idx == 2:
                self._origin = [0.0, 0.0, 0.0]
                self._u_axis = [1.0, 0.0, 0.0]
                self._v_axis = [0.0, 0.0, 1.0]
            elif idx == 3:
                self._origin = [0.0, 0.0, 0.0]
                self._u_axis = [0.0, 1.0, 0.0]
                self._v_axis = [0.0, 0.0, 1.0]

        _, self._origin = imgui.input_float3("Orijin (X, Y, Z)", self._origin)
        _, self._u_axis = imgui.input_float3("U Ekseni", self._u_axis)
        _, self._v_axis = imgui.input_float3("V Ekseni", self._v_axis)

        eng = self.app.engine
        sel_nodes = [
            e for e in (eng.sel_mgr.get_selected() if (eng and eng.sel_mgr) else ())
            if hasattr(e, "x") and hasattr(e, "y") and hasattr(e, "z")
        ]
        if len(sel_nodes) >= 1 and imgui.small_button("Orijini Seçili Düğümden Al"):
            n0 = sel_nodes[0]
            self._origin = [float(n0.x), float(n0.y), float(n0.z)]
        if len(sel_nodes) >= 2:
            imgui.same_line()
            if imgui.small_button("2 Düğüm + Z"):
                n0, n1 = sel_nodes[0], sel_nodes[1]
                ucs = ViewUCS.from_2_points_z_up((n0.x, n0.y, n0.z), (n1.x, n1.y, n1.z))
                self._origin = [float(ucs.origin[0]), float(ucs.origin[1]), float(ucs.origin[2])]
                self._u_axis = [float(ucs.u[0]), float(ucs.u[1]), float(ucs.u[2])]
                self._v_axis = [float(ucs.v[0]), float(ucs.v[1]), float(ucs.v[2])]
        if len(sel_nodes) >= 3:
            imgui.same_line()
            if imgui.small_button("3 Düğümden UCS"):
                n0, n1, n2 = sel_nodes[0], sel_nodes[1], sel_nodes[2]
                ucs = ViewUCS.from_3_points((n0.x, n0.y, n0.z), (n1.x, n1.y, n1.z), (n2.x, n2.y, n2.z))
                self._origin = [float(ucs.origin[0]), float(ucs.origin[1]), float(ucs.origin[2])]
                self._u_axis = [float(ucs.u[0]), float(ucs.u[1]), float(ucs.u[2])]
                self._v_axis = [float(ucs.v[0]), float(ucs.v[1]), float(ucs.v[2])]

        _, self._is_2d = imgui.checkbox("2D Düzlem Bakışı", self._is_2d)

        imgui.separator_text("2. Hacimsel Sınırlar (View Volume)")
        _, self._use_uv_bounds = imgui.checkbox("U / V Sınırları Aktif", self._use_uv_bounds)
        if self._use_uv_bounds:
            _, self._u_min = imgui.drag_float("U Min", self._u_min, 10.0)
            _, self._u_max = imgui.drag_float("U Max", self._u_max, 10.0)
            _, self._v_min = imgui.drag_float("V Min", self._v_min, 10.0)
            _, self._v_max = imgui.drag_float("V Max", self._v_max, 10.0)

        _, self._use_depth = imgui.checkbox("Derinlik Sınırları Aktif (-N / +N)", self._use_depth)
        if self._use_depth:
            _, self._depth_minus = imgui.drag_float("Derinlik Alt (-N)", self._depth_minus, 10.0, 0.0, 1e8)
            _, self._depth_plus = imgui.drag_float("Derinlik Üst (+N)", self._depth_plus, 10.0, 0.0, 1e8)

        for mode, label in (
            (VolumeClipMode.INTERSECT, "Intersect (Kesenler Dahil)"),
            (VolumeClipMode.STRICT, "Strict (Tamamı İçinde)"),
            (VolumeClipMode.CLIP, "Clip"),
        ):
            if imgui.radio_button(label, self._clip_mode == mode):
                self._clip_mode = mode

        imgui.separator_text("3. Eleman Filtresi")
        _, self._only_beams = imgui.checkbox("Kiriş (Beam)", self._only_beams)
        imgui.same_line()
        _, self._only_columns = imgui.checkbox("Kolon (Column)", self._only_columns)
        imgui.same_line()
        _, self._only_braces = imgui.checkbox("Çapraz (Brace)", self._only_braces)

        _, self._show_nodes = imgui.checkbox("Node", self._show_nodes)
        imgui.same_line()
        _, self._show_areas = imgui.checkbox("Area", self._show_areas)
        imgui.same_line()
        _, self._show_links = imgui.checkbox("Link", self._show_links)

        _, self._name_pattern = imgui.input_text("Etiket Deseni", self._name_pattern)
        _, self._section_filter = imgui.input_text("Kesitler (virgüllü)", self._section_filter)
        _, self._material_filter = imgui.input_text("Malzemeler (virgüllü)", self._material_filter)

        imgui.separator()
        if imgui.button("Apply", imgui.ImVec2(95, 0)):
            self._apply(vp)
        imgui.same_line()
        if imgui.button("Sınırları Temizle", imgui.ImVec2(125, 0)):
            self._reset_limits(vp)
        imgui.same_line()
        if imgui.button("Kapat", imgui.ImVec2(85, 0)):
            self.visible = False

        imgui.end()

    def _build_ucs(self, fallback: ViewUCS) -> ViewUCS:
        u = np.asarray(self._u_axis, dtype=float)
        v = np.asarray(self._v_axis, dtype=float)
        if np.linalg.norm(u) < 1e-9 or np.linalg.norm(np.cross(u, v)) < 1e-9:
            return fallback
        return ViewUCS.from_axes(self._origin, u, v)

    def _build_filter(self) -> ElementFilterQuery | None:
        subtypes = set()
        if self._only_beams:
            subtypes.add("beam")
        if self._only_columns:
            subtypes.add("column")
        if self._only_braces:
            subtypes.add("brace")

        etypes = set()
        if subtypes or not (self._show_nodes and self._show_areas and self._show_links):
            etypes.add("Frame")
            if self._show_nodes:
                etypes.add("Node")
            if self._show_areas:
                etypes.add("Area")
            if self._show_links:
                etypes.add("Link")
            etypes.update({"Polygon", "Line"})

        sections = {s.strip() for s in self._section_filter.split(",") if s.strip()}
        materials = {m.strip() for m in self._material_filter.split(",") if m.strip()}
        pattern = self._name_pattern.strip() or None

        q = ElementFilterQuery(
            name_pattern=pattern,
            element_types=etypes,
            sections=sections,
            materials=materials,
            structural_subtypes=subtypes,
        )
        return None if q.is_empty() else q

    def _apply(self, vp) -> None:
        eng = self.app.engine
        ucs = self._build_ucs(vp.ucs)
        vp.ucs = ucs
        vp.is_2d = bool(self._is_2d)

        u_min = self._u_min if self._use_uv_bounds else None
        u_max = self._u_max if self._use_uv_bounds else None
        v_min = self._v_min if self._use_uv_bounds else None
        v_max = self._v_max if self._use_uv_bounds else None
        d_minus = max(0.0, self._depth_minus) if self._use_depth else None
        d_plus = max(0.0, self._depth_plus) if self._use_depth else None

        vp.set_volume(
            u_min=u_min,
            u_max=u_max,
            v_min=v_min,
            v_max=v_max,
            depth_minus=d_minus,
            depth_plus=d_plus,
            mode=self._clip_mode,
            refocus=False,
        )
        vp.set_element_filter(self._build_filter())

        bounds = eng._combined_bounds() if eng else None
        vp.focus_on_volume(
            fallback_center=bounds.center if bounds is not None else None,
            fallback_radius=float(bounds.size) if bounds is not None else 2000.0,
        )

    def _reset_limits(self, vp) -> None:
        self._use_uv_bounds = False
        self._use_depth = False
        self._only_beams = False
        self._only_columns = False
        self._only_braces = False
        self._show_nodes = True
        self._show_areas = True
        self._show_links = True
        self._name_pattern = ""
        self._section_filter = ""
        self._material_filter = ""
        vp.clear_volume()
        vp.set_element_filter(None)