# viewport/viewport_panel.py
from __future__ import annotations

from typing import TYPE_CHECKING

from imgui_bundle import imgui

if TYPE_CHECKING:
    from ui.ui_host import UIHost
    from viewport.viewport_manager import ViewportManager


class ViewportPanel:
    _MIN_W = 64
    _MIN_H = 64

    def __init__(self, host: "UIHost", viewport_name: str,
                 manager: "ViewportManager") -> None:
        self.host = host
        self.viewport_name = viewport_name
        self.manager = manager
        self.title = f"Viewport: {viewport_name}"
        self.visible = True
        self._is_hovered = False
        self._item_min = imgui.ImVec2(0.0, 0.0)
        self._item_size = imgui.ImVec2(0.0, 0.0)

    def draw(self) -> None:
        vp = self.manager.get(self.viewport_name)
        if vp is None:
            return

        flags = (
            imgui.WindowFlags_.no_scrollbar
            | imgui.WindowFlags_.no_scroll_with_mouse
        )
        expanded, p_open = imgui.begin(f"{self.title}###vp_{self.viewport_name}", True, flags)
        try:
            if not p_open:
                self._close()
                return
            if not expanded:
                self._is_hovered = False
                return
            self._draw_image(vp)
        finally:
            imgui.end()

    def _draw_image(self, vp) -> None:
        avail = imgui.get_content_region_avail()
        w = max(self._MIN_W, int(avail.x))
        h = max(self._MIN_H, int(avail.y))
        if w < 8 or h < 8:
            return

        scale = 1.0
        win_vp = imgui.get_window_viewport()
        if win_vp is not None:
            scale = getattr(win_vp, "dpi_scale", 1.0)

        vp.resize(int(w * scale), int(h * scale))

        imgui.image(
            imgui.ImTextureRef(vp.texture_id()),
            imgui.ImVec2(float(w), float(h)),
            imgui.ImVec2(0.0, 1.0),
            imgui.ImVec2(1.0, 0.0),
        )
        self._item_min = imgui.get_item_rect_min()
        self._item_size = imgui.get_item_rect_size()
        self._is_hovered = imgui.is_item_hovered()

    def _close(self) -> None:
        self.manager.remove_viewport(self.viewport_name)
        self.host.on_viewport_panel_closed(self)