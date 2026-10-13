# ui/toolbar.py
"""
ImGui Toolbar — Açılır menü grubu ile sadeleştirilmiş üst şerit.
"""
from typing import Callable, Dict
import imgui


class Toolbar:
    HEIGHT = 34.0

    def __init__(self, callbacks: Dict[str, Callable]):
        self.callbacks = callbacks or {}

    def draw(self, model_text: str = "MODEL: YENİ SAHNE", draw_active: bool = False):
        flags = (
            imgui.WINDOW_NO_SCROLLBAR
            | imgui.WINDOW_NO_SCROLL_WITH_MOUSE
            | imgui.WINDOW_NO_SAVED_SETTINGS
        )

        try:
            imgui.begin_viewport_side_bar(imgui.DIRECTION_UP, True, self.HEIGHT, flags)
        except AttributeError:
            imgui.begin_main_menu_bar()
            self._draw_content(model_text, draw_active)
            imgui.end_main_menu_bar()
            return

        self._draw_content(model_text, draw_active)
        imgui.end()

    def _draw_content(self, model_text: str, draw_active: bool):
        if imgui.button("←"):
            self._fire("menu")
        imgui.same_line()

        self._styled_button("Aç", (0.18, 0.35, 0.55, 1.00), lambda: self._fire("open"))
        imgui.same_line()
        self._styled_button("Kaydet", (0.18, 0.50, 0.32, 1.00), lambda: self._fire("save"))
        imgui.same_line()

        if draw_active:
            draw_color, draw_label = (0.20, 0.60, 0.35, 1.00), "Çizim [AÇIK]"
        else:
            draw_color, draw_label = (0.22, 0.28, 0.38, 1.00), "Çiz (D)"

        self._styled_button(draw_label, draw_color, lambda: self._fire("draw"))
        imgui.same_line()

        # --- Proje & Yönetim Açılır Menü Grubu ---
        if imgui.begin_menu("Proje & Yönetim"):
            if imgui.menu_item("Tanımlar (Definitions)")[0]:
                self._fire("definitions")
            if imgui.menu_item("Proje Bilgileri (Info)")[0]:
                self._fire("project_info")
            if imgui.menu_item("Yapılandırma (Config)")[0]:
                self._fire("project_config")
            if imgui.menu_item("Analiz (Analysis)")[0]:
                self._fire("analysis")
            if imgui.menu_item("Rapor (Report)")[0]:
                self._fire("report")
            imgui.end_menu()
        imgui.same_line()

        imgui.text_colored(model_text, 0.60, 0.65, 0.72, 1.00)

        avail = imgui.get_content_region_available_width()
        right_block = 180.0
        if avail > right_block:
            imgui.same_line(position=imgui.get_window_width() - right_block)

        self._styled_button("VIS", (0.20, 0.40, 0.50, 1.00), lambda: self._fire("visibility"))
        imgui.same_line()
        self._styled_button("Zones", (0.15, 0.45, 0.60, 1.00), lambda: self._fire("wind"))

    def _styled_button(self, label: str, base_color, on_click):
        hovered = tuple(min(c + 0.08, 1.0) for c in base_color[:3]) + (1.0,)
        active = tuple(min(c + 0.15, 1.0) for c in base_color[:3]) + (1.0,)

        imgui.push_style_color(imgui.COLOR_BUTTON, *base_color)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, *hovered)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, *active)
        imgui.push_style_var(imgui.STYLE_FRAME_ROUNDING, 4.0)

        clicked = imgui.button(label)

        imgui.pop_style_var(1)
        imgui.pop_style_color(3)

        if clicked and callable(on_click):
            on_click()

    def _fire(self, key: str):
        fn = self.callbacks.get(key)
        if callable(fn):
            fn()