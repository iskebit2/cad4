# plane/plane_source_dialog.py

from __future__ import annotations

from imgui_bundle import imgui

from domain.element import Area, Frame
from domain.polygon import Polygon
from plane.plane import Plane

SRC_3PT = "3pt"
SRC_2PT_Z = "2pt_z"
SRC_ELEMENT = "element"


class PlaneSourceDialog:

    def __init__(self, app):
        self.app = app
        self.visible = False
        self.source = SRC_3PT
        self.frame_axis_12 = False

    def open(self):
        self.visible = True
        self.source = SRC_3PT
        self.frame_axis_12 = False
        imgui.open_popup("##plane_source")

    def close(self):
        self.visible = False
        imgui.close_current_popup()

    def draw(self):
        if not self.visible:
            return

        if not imgui.begin_popup_modal("##plane_source", True,
                                       imgui.WindowFlags_.always_auto_resize)[0]:
            self.visible = False
            imgui.end_popup()
            return

        imgui.text("Yeni Plane Kaynağı")
        imgui.separator()

        for key, label in (
            (SRC_3PT, "3 Noktadan (ekranda seç)"),
            (SRC_2PT_Z, "2 Nokta + Z ekseni"),
            (SRC_ELEMENT, "Seçili Eleman"),
        ):
            if imgui.radio_button(f"{label}##psrc_{key}", self.source == key):
                self.source = key

        if self.source == SRC_ELEMENT:
            imgui.separator()
            selected = self._selected_element()
            if selected is None:
                imgui.text_colored(imgui.ImVec4(0.9, 0.6, 0.5, 1.0),
                                   "Sahnede tek bir eleman seç.")
            else:
                imgui.text(f"Eleman: {selected.element_type} "
                           f"{selected.label or selected.unique_id}")
                if isinstance(selected, Frame):
                    imgui.text("Eksen:")
                    imgui.same_line()
                    if imgui.radio_button("1-2##psrc_ax",
                                          self.frame_axis_12):
                        self.frame_axis_12 = True
                    imgui.same_line()
                    if imgui.radio_button("1-3##psrc_ax",
                                          not self.frame_axis_12):
                        self.frame_axis_12 = False

        imgui.separator()
        if imgui.button("Başlat", imgui.ImVec2(120, 0)):
            self._start()
        imgui.same_line()
        if imgui.button("Vazgeç", imgui.ImVec2(100, 0)):
            self.close()

        imgui.end_popup()

    def _selected_element(self):
        eng = getattr(self.app, "engine", None)
        if eng is None or eng.sel_mgr is None:
            return None
        selected = [e for e in eng.sel_mgr.get_selected()
                    if isinstance(e, (Frame, Area, Polygon))]
        return selected[0] if len(selected) == 1 else None

    def _start(self):
        eng = self.app.engine
        proj = self.app.current_project

        if self.source == SRC_3PT:
            eng.plane_draw_mgr.start_3pt()
            self.close()
            return

        if self.source == SRC_2PT_Z:
            eng.plane_draw_mgr.start_2pt_z()
            self.close()
            return

        if self.source == SRC_ELEMENT:
            el = self._selected_element()
            if el is None:
                return
            plane = Plane.from_element(
                el, frame_local_12=self.frame_axis_12,
                name=f"Plane_Element_{el.unique_id}",
            )
            plane.fit_to_math_model(eng.math_model)
            proj.add_plane(plane)

            pm = self.app.panels.get("plane_manager", {}).get("instance")
            if pm is not None:
                pm._selected_name = plane.name
                pm.visible = True

            eng.update_geo(proj)
            self.close()
        