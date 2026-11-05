# inspector/topbar.py
from __future__ import annotations

from imgui_bundle import imgui


class TopBar:

    def __init__(self, inspector):
        self.inspector = inspector
        self._buttons = [
            ("left_toggle", "☰", "Sol paneli aç/kapa", self._on_left_toggle),
            ("apply", "✔", "Uygula", self._on_apply),
            ("delete", "🗑", "Sil", self._on_delete),
            ("undo", "↩", "Geri al", self._on_undo),
            ("redo", "↪", "Yinele", self._on_redo),
            ("fit", "⬇", "Sığdır", self._on_fit),
            ("draw_line", "✎", "Line çiz", self._on_draw_line),
            ("draw_poly", "⬡", "Polygon çiz", self._on_draw_poly),
            ("to_frame", "⇄", "Frame'e dönüştür", self._on_to_frame),
            ("to_link", "⊞", "Link'e dönüştür", self._on_to_link),
            ("to_plane", "⊡", "Plane dönüştür", self._on_to_plane),
            ("column", "↕", "Kolon oluştur", self._on_column),
        ]

    @property
    def app(self):
        return self.inspector.app

    def draw(self):
        imgui.push_style_var(imgui.StyleVar_.item_spacing, imgui.ImVec2(4, 4))
        try:
            expanded = imgui.begin_child("##insp_topbar", imgui.ImVec2(0, 32), True,
                                           imgui.WindowFlags_.no_scrollbar)
            if expanded:
                for i, (key, icon, tip, fn) in enumerate(self._buttons):
                    if i in (2, 6, 9) and i > 0:
                        imgui.same_line(0, 8)
                        imgui.text("|")
                        imgui.same_line(0, 8)
                    if imgui.button(icon, imgui.ImVec2(28, 24)):
                        fn()
                    if imgui.is_item_hovered():
                        imgui.set_tooltip(tip)
                    imgui.same_line(0, 2)
        finally:
            imgui.end_child()
            imgui.pop_style_var(1)

    # ------------------------------------------------------------------
    def _on_left_toggle(self):
        self.inspector._left_open = not self.inspector._left_open

    def _on_apply(self):
        self.inspector.controller.apply()

    def _on_delete(self):
        eng = self.app.engine if self.app else None
        if eng and eng.sel_mgr:
            eng.sel_mgr.delete_selected()

    def _on_undo(self):
        eng = self.app.engine if self.app else None
        if eng and eng.sel_mgr:
            eng.sel_mgr.undo()

    def _on_redo(self):
        eng = self.app.engine if self.app else None
        if eng and eng.sel_mgr:
            eng.sel_mgr.redo()

    def _on_fit(self):
        eng = self.app.engine if self.app else None
        if eng:
            eng.zoom_extents()

    def _on_draw_line(self):
        if self.app:
            self.app.input.toggle_draw("line")

    def _on_draw_poly(self):
        if self.app:
            self.app.input.toggle_draw("poly")

    def _on_to_frame(self):
        if self.app:
            self.app.input.convert_frames_to_links("DefaultLink")

    def _on_to_link(self):
        pass

    def _on_to_plane(self):
        pass

    def _on_column(self):
        pass