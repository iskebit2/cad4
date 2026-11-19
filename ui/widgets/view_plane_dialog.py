# ui/widgets/view_plane_dialog.py
from __future__ import annotations

from typing import TYPE_CHECKING

from imgui_bundle import imgui
from plane.plane_policy import SectionFilterMode
from tools.filter_query import ElementFilterQuery

if TYPE_CHECKING:
    from app.cad_app import CadApp


class ViewPlanePropertiesDialog:
    """
    Her yerden (Sağ Tık Menüsü, PlaneManager, Komut Satırı) aynı şekilde
    çağrılabilen Tekla tarzı View Plane + Depth + Filter düzenleyici.
    """

    def __init__(self, app: "CadApp") -> None:
        self.app = app
        self.visible = False
        self._viewport_name: str | None = None
        self._plane_name: str | None = None
        self._snapshot: dict | None = None

        # Düzenleme tamponları
        self._use_bounds = True
        self._u_min = -5000.0
        self._u_max = 5000.0
        self._v_min = -5000.0
        self._v_max = 5000.0
        self._depth_minus = 500.0
        self._depth_plus = 500.0
        self._filter_mode = SectionFilterMode.INTERSECT
        self._is_2d = False
        self._live_preview = True

        # ElementFilterQuery tamponları (Sadece Kiriş, Kolon, Node, Area vb.)
        self._only_beams = False
        self._only_columns = False
        self._only_braces = False
        self._show_nodes = True
        self._show_areas = True
        self._show_links = True
        self._name_pattern = ""
        self._section_filter = ""

    def open(self, viewport_name: str | None = None, plane=None) -> None:
        vm = self.app.viewport_manager
        vp = None
        if vm is not None:
            vp = vm.get(viewport_name) if viewport_name else vm.active

        if plane is None and vp is not None:
            plane = getattr(vp, "plane", None)

        if plane is None and self.app.current_project is not None:
            plane = self.app.current_project.active_plane

        if plane is None:
            return

        self._viewport_name = vp.name if vp is not None else None
        self._plane_name = plane.name
        self._load_from(plane, vp)
        self._snapshot = self._capture_snapshot(plane, vp)
        self.visible = True

    def _load_from(self, plane, vp) -> None:
        self._use_bounds = None not in (plane.u_min, plane.u_max, plane.v_min, plane.v_max)
        self._u_min = float(plane.u_min) if plane.u_min is not None else -5000.0
        self._u_max = float(plane.u_max) if plane.u_max is not None else 5000.0
        self._v_min = float(plane.v_min) if plane.v_min is not None else -5000.0
        self._v_max = float(plane.v_max) if plane.v_max is not None else 5000.0
        self._depth_minus = float(plane.depth_minus)
        self._depth_plus = float(plane.depth_plus)
        self._filter_mode = plane.filter_mode
        self._is_2d = bool(getattr(vp, "is_2d", False)) if vp is not None else False

        q: ElementFilterQuery | None = getattr(vp, "element_filter", None) if vp is not None else None
        if q is None or q.is_empty():
            self._only_beams = self._only_columns = self._only_braces = False
            self._show_nodes = self._show_areas = self._show_links = True
            self._name_pattern = ""
            self._section_filter = ""
        else:
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

    @staticmethod
    def _capture_snapshot(plane, vp) -> dict:
        return {
            "u_min": plane.u_min, "u_max": plane.u_max,
            "v_min": plane.v_min, "v_max": plane.v_max,
            "depth_minus": plane.depth_minus, "depth_plus": plane.depth_plus,
            "filter_mode": plane.filter_mode,
            "is_2d": getattr(vp, "is_2d", False) if vp else False,
            "element_filter": getattr(vp, "element_filter", None) if vp else None,
        }

    def draw(self) -> None:
        if not self.visible:
            return

        vm = self.app.viewport_manager
        vp = vm.get(self._viewport_name) if (vm and self._viewport_name) else None
        prj = self.app.current_project
        plane = prj.get_plane(self._plane_name) if (prj and self._plane_name) else (getattr(vp, "plane", None) if vp else None)

        if plane is None:
            self.visible = False
            return

        title = f"View & Plane Ayarları — {plane.name}"
        if vp is not None:
            title += f" [{vp.name}]"

        imgui.set_next_window_size(imgui.ImVec2(430, 520), imgui.Cond_.first_use_ever)
        expanded, p_open = imgui.begin(f"{title}###view_plane_props", True)
        try:
            if not p_open:
                self._cancel(plane, vp)
                return
            if not expanded:
                return

            changed = False

            # --- 1. SINIRLAR (UCS U / V) ---
            imgui.separator_text("1. Düzlem Sınırları (Lokal UCS)")
            c_bnd, self._use_bounds = imgui.checkbox("Sınır Kutusu Aktif", self._use_bounds)
            changed |= c_bnd
            imgui.same_line()
            if imgui.small_button("Modele Sığdır"):
                eng = self.app.engine
                plane.fit_to_math_model(eng.math_model if eng else None, include_depth=True)
                self._load_from(plane, vp)
                changed = True

            if self._use_bounds:
                c1, self._u_min = imgui.drag_float("U Min (Sol)", self._u_min, 10.0)
                c2, self._u_max = imgui.drag_float("U Max (Sağ)", self._u_max, 10.0)
                c3, self._v_min = imgui.drag_float("V Min (Alt)", self._v_min, 10.0)
                c4, self._v_max = imgui.drag_float("V Max (Üst)", self._v_max, 10.0)
                changed |= (c1 or c2 or c3 or c4)

            # --- 2. DERİNLİK (View Depth Up / Down) ---
            imgui.separator_text("2. Görüş Derinliği (View Depth)")
            cd1, self._depth_minus = imgui.drag_float("Derinlik Alt (-N)", self._depth_minus, 10.0, 0.0, 1e7)
            cd2, self._depth_plus = imgui.drag_float("Derinlik Üst (+N)", self._depth_plus, 10.0, 0.0, 1e7)
            changed |= (cd1 or cd2)

            # --- 3. KESİT & KIRPMA MODU ---
            imgui.separator_text("3. Kesit Süzme Modu")
            for mode, label in (
                (SectionFilterMode.INTERSECT, "Intersect (Kutuya Giren/Kesen)"),
                (SectionFilterMode.STRICT, "Strict (Tamamı Kutu İçinde)"),
                (SectionFilterMode.CLIP, "Clip (Shader Düzlem Kesiti)"),
            ):
                if imgui.radio_button(label, self._filter_mode == mode):
                    self._filter_mode = mode
                    changed = True

            # --- 4. UCS BAKIŞ YÖNÜ ---
            if vp is not None:
                imgui.separator_text("4. Kamera & UCS Bakışı")
                c2d, self._is_2d = imgui.checkbox("Düzleme Dik 2D Bakış (UCS Kilitli)", self._is_2d)
                changed |= c2d
                imgui.same_line()
                if imgui.small_button("Kamerayı Hizala") and vm is not None:
                    vm.focus_viewport_on_plane(vp, plane)

            # --- 5. ELEMAN FİLTRESİ (Tekla View Filter) ---
            if vp is not None:
                imgui.separator_text("5. Görünüm Eleman Filtresi")
                fb, self._only_beams = imgui.checkbox("Sadece Kirişler (Beam)", self._only_beams)
                imgui.same_line()
                fc, self._only_columns = imgui.checkbox("Kolonlar (Column)", self._only_columns)
                fbr, self._only_braces = imgui.checkbox("Çaprazlar (Brace)", self._only_braces)

                fn, self._show_nodes = imgui.checkbox("Nodes", self._show_nodes)
                imgui.same_line()
                fa, self._show_areas = imgui.checkbox("Areas", self._show_areas)
                imgui.same_line()
                fl, self._show_links = imgui.checkbox("Links", self._show_links)

                fp, self._name_pattern = imgui.input_text("Etiket Filtresi (örn: K*)", self._name_pattern)
                fs, self._section_filter = imgui.input_text("Kesitler (örn: IPE300)", self._section_filter)
                changed |= (fb or fc or fbr or fn or fa or fl or fp or fs)

            imgui.separator()
            _, self._live_preview = imgui.checkbox("Canlı Önizleme", self._live_preview)
            if changed and self._live_preview:
                self._apply(plane, vp, refocus=False)

            if imgui.button("Apply", imgui.ImVec2(90, 0)):
                self._apply(plane, vp, refocus=True)
            imgui.same_line()
            if imgui.button("OK", imgui.ImVec2(90, 0)):
                self._apply(plane, vp, refocus=True)
                self.visible = False
            imgui.same_line()
            if imgui.button("İptal", imgui.ImVec2(90, 0)):
                self._cancel(plane, vp)
        finally:
            imgui.end()

    def _build_element_filter(self) -> ElementFilterQuery | None:
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

        secs = {s.strip() for s in self._section_filter.split(",") if s.strip()}
        pat = self._name_pattern.strip() or None

        q = ElementFilterQuery(
            name_pattern=pat,
            element_types=etypes,
            sections=secs,
            structural_subtypes=subtypes,
        )
        return None if q.is_empty() else q

    def _apply(self, plane, vp, refocus: bool = False) -> None:
        if self._use_bounds:
            plane.set_bounds(self._u_min, self._u_max, self._v_min, self._v_max, recenter=False)
        else:
            plane.clear_bounds()

        plane.depth_minus = max(0.0, float(self._depth_minus))
        plane.depth_plus = max(0.0, float(self._depth_plus))
        plane.set_filter_mode(self._filter_mode)

        if vp is not None:
            vp.is_2d = bool(self._is_2d)
            vp.set_element_filter(self._build_element_filter())

        vm = self.app.viewport_manager
        if vm is not None:
            vm.sync_plane(plane, refocus=refocus)

    def _cancel(self, plane, vp) -> None:
        if self._snapshot is not None:
            s = self._snapshot
            plane.set_bounds(s["u_min"], s["u_max"], s["v_min"], s["v_max"], recenter=False)
            plane.depth_minus = s["depth_minus"]
            plane.depth_plus = s["depth_plus"]
            plane.set_filter_mode(s["filter_mode"])
            if vp is not None:
                vp.is_2d = s["is_2d"]
                vp.set_element_filter(s["element_filter"])
            if self.app.viewport_manager is not None:
                self.app.viewport_manager.sync_plane(plane, refocus=False)
        self.visible = False