# inspector/topbar.py
from __future__ import annotations
from app.commands import project_commands as PC
from imgui_bundle import imgui


class TopBar:

    def __init__(self, inspector):
        self.inspector = inspector
        self._buttons = [
            ("left_toggle", "☰", "Sol paneli aç/kapa", self._on_left_toggle),
            ("apply",  "✔", "Uygula (Ctrl+Enter)", self._on_apply),
            ("cancel", "✖", "İptal", self._on_cancel),
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

                    enabled = self._button_enabled(key)
                    if not enabled:
                        imgui.begin_disabled()
                    if imgui.button(icon, imgui.ImVec2(28, 24)):
                        fn()
                    if imgui.is_item_hovered():
                        imgui.set_tooltip(tip)
                    if not enabled:
                        imgui.end_disabled()
                    imgui.same_line(0, 2)
        finally:
            imgui.end_child()
            imgui.pop_style_var(1)

    def _button_enabled(self, key: str) -> bool:
        c = self.inspector.controller
        if key == "apply":
            return c.is_dirty()
        if key == "cancel":
            return c.is_dirty()
        if key == "delete":
            return bool(c.objects)
        return True

    def _on_apply(self):
        if self.inspector.controller.apply():
            self.inspector.refresh()

    def _on_cancel(self):
        self.inspector.controller.cancel()
        self.inspector.refresh()

    # ------------------------------------------------------------------
    def _on_left_toggle(self):
        self.inspector._left_open = not self.inspector._left_open


    def _on_delete(self):
        if self.app:
            from app.commands import project_commands as PC
            self.app.put_command(PC.DeleteSelected())

    def _on_undo(self):
        if self.app:
            from app.commands import project_commands as PC
            self.app.put_command(PC.Undo())

    def _on_redo(self):
        if self.app:
            from app.commands import project_commands as PC
            self.app.put_command(PC.Redo())

    def _on_fit(self):
        if self.app:
            from app.commands import project_commands as PC
            self.app.put_command(PC.ZoomExtents())

    def _on_draw_line(self):
        if self.app:
            self.app.put_command(PC.StartDrawTool("line"))

    def _on_draw_poly(self):
        if self.app:
            self.app.put_command(PC.StartDrawTool("poly"))

    def _on_to_frame(self):
        pass

    def _on_to_link(self):
        self.app.put_command(PC.ConvertFramesToLinks("DefaultLink"))

    def _on_to_plane(self):
        pass

    def _on_column(self):
        pass
    