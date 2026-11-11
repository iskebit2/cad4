# ui/viewport_panel.py
from __future__ import annotations

from imgui_bundle import imgui

from ui.base_panel import BasePanel


class ViewportPanel(BasePanel):
    _PRESET_POSITIONS = {
        "top": (50, 100), "bottom": (50, 100),
        "front": (400, 100), "back": (400, 100),
        "left": (750, 100), "right": (750, 100),
        "iso": (400, 300), "iso_sw": (400, 300),
        "iso_se": (750, 300), "iso_ne": (400, 500),
        "iso_nw": (750, 500),
    }
    _MIN_W = 400
    _MIN_H = 300

    def __init__(self, app, viewport_name: str, manager, preset: str | None = None):
        super().__init__(
            title=f"Viewport: {viewport_name}",
            width=800, height=600,
            pos_first_use=self._PRESET_POSITIONS.get(preset or "", (300, 200)),
        )
        self.viewport_name = viewport_name
        self.manager = manager
        self.app = app
        self.visible = True

        self._is_hovered: bool = False
        self._item_min = imgui.ImVec2(0.0, 0.0)

    # ------------------------------------------------------------------
    def draw(self):
        vp = self.manager.get(self.viewport_name)
        if vp is None:
            return

        flags = (
            imgui.WindowFlags_.no_scrollbar
            | imgui.WindowFlags_.no_scroll_with_mouse
        )
        expanded, p_open = imgui.begin(
            f"{self.title}###vp_{self.viewport_name}", True, flags,
        )
        
        try:
            if not p_open:
                self._close_and_remove()
                return
            if not expanded:
                self._is_hovered = False
                return
            vp.visible = True
            self._draw_content(vp)
        finally:
            imgui.end()

    def _draw_content(self, vp):
        avail = imgui.get_content_region_avail()
        w = max(self._MIN_W, int(avail.x))
        h = max(self._MIN_H, int(avail.y))
        vp.resize(w, h)

        imgui.image(
            imgui.ImTextureRef(vp.texture_id()),
            imgui.ImVec2(float(w), float(h)),
            imgui.ImVec2(0, 1),
            imgui.ImVec2(1, 0),
        )
        self._item_min = imgui.get_item_rect_min()
        self._is_hovered = imgui.is_item_hovered()
        self._draw_marquee_overlay(vp)

    def _draw_marquee_overlay(self, vp):
        eng = self.app.engine if self.app is not None else None
        if eng is None:
            return
        marquee = eng.marquee
        if marquee is None or not marquee.is_active:
            return
        if (marquee.viewport_name is not None
                and marquee.viewport_name != self.viewport_name):
            return
        coords = marquee.get_box_coords()
        if coords is None:
            return
        x1, y1, x2, y2 = coords
        if abs(x2 - x1) < 2 and abs(y2 - y1) < 2:
            return

        mn_x, mx_x = min(x1, x2), max(x1, x2)
        mn_y, mx_y = min(y1, y2), max(y1, y2)
        p0 = imgui.ImVec2(self._item_min.x + mn_x, self._item_min.y + mn_y)
        p1 = imgui.ImVec2(self._item_min.x + mx_x, self._item_min.y + mx_y)

        if x2 < x1:
            fill = imgui.ImVec4(0.20, 0.85, 0.20, 0.22)
            border = imgui.ImVec4(0.30, 1.00, 0.30, 0.95)
        else:
            fill = imgui.ImVec4(0.20, 0.50, 0.95, 0.22)
            border = imgui.ImVec4(0.40, 0.75, 1.00, 0.95)

        dl = imgui.get_window_draw_list()
        dl.add_rect_filled(p0, p1, imgui.get_color_u32(fill))
        dl.add_rect(p0, p1, imgui.get_color_u32(border))

    def _close_and_remove(self):
        self.manager.remove_viewport(self.viewport_name)
        if self.app is not None:
            try:
                self.app._viewport_panels.remove(self)
            except ValueError:
                pass
            if self.app._last_active_viewport_name == self.viewport_name:
                self.app._last_active_viewport_name = None