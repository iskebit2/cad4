# ui/toolbar.py
"""
ImGui Toolbar — Kivy'deki build_toolbar'ın karşılığı.

Viewport üstünde sabit bir şerit olarak çizilir.
Buton durumlarını ve callback'leri dışarıdan alır.

Kullanım:
    toolbar = Toolbar(callbacks)
    # her frame:
    toolbar.draw(state)
"""
from typing import Callable, Dict, Optional

import imgui


class Toolbar:
    """
    Üst toolbar. `BeginViewportSideBar` ile viewport'a sabitlenir.

    callbacks: {
        "menu":        fn,
        "open":        fn,
        "save":        fn,
        "draw":        fn,       # toggle
        "import_sap":  fn,
        "visibility":  fn,
        "wind":        fn,
        "print":       fn,
    }
    """

    HEIGHT = 34.0

    def __init__(self, callbacks: Dict[str, Callable]):
        self.callbacks = callbacks or {}

    # ------------------------------------------------------------------
    def draw(self, model_text: str = "MODEL: YENİ SAHNE",
             draw_active: bool = False):
        """Toolbar'ı çiz. draw_active, 'çizim modu' butonunun rengi için."""
        flags = (
            imgui.WINDOW_NO_SCROLLBAR
            | imgui.WINDOW_NO_SCROLL_WITH_MOUSE
            | imgui.WINDOW_NO_SAVED_SETTINGS
        )

        # Viewport üstünde sabit bir bar
        # pyimgui 2.0'da begin_viewport_side_bar YOK ise fallback:
        try:
            imgui.begin_viewport_side_bar(
                imgui.DIRECTION_UP,
                True,
                self.HEIGHT,
                flags,
            )
        except AttributeError:
            # Fallback: eski pyimgui sürümleri için BeginMainMenuBar
            imgui.begin_main_menu_bar()
            self._draw_content(model_text, draw_active)
            imgui.end_main_menu_bar()
            return

        self._draw_content(model_text, draw_active)
        imgui.end()

    # ------------------------------------------------------------------
    def _draw_content(self, model_text: str, draw_active: bool):
        # --- Menü ---
        if imgui.button("←"):
            self._fire("menu")
        imgui.same_line()

        # --- Open ---
        self._styled_button(
            "open", (0.18, 0.35, 0.55, 1.00),
            lambda: self._fire("open"),
        )
        imgui.same_line()

        # --- Save ---
        self._styled_button(
            "save", (0.18, 0.50, 0.32, 1.00),
            lambda: self._fire("save"),
        )
        imgui.same_line()

        # --- Draw (toggle) ---
        if draw_active:
            draw_color = (0.20, 0.60, 0.35, 1.00)
            draw_hover = (0.28, 0.72, 0.45, 1.00)
            draw_label = "draw [AÇIK]"
        else:
            draw_color = (0.22, 0.28, 0.38, 1.00)
            draw_hover = (0.30, 0.38, 0.50, 1.00)
            draw_label = "draw (D)"

        self._styled_button(
            draw_label, draw_color, lambda: self._fire("draw"),
            hovered=draw_hover,
        )
        imgui.same_line()

        # --- SAP Import ---
        self._styled_button(
            "SAP Import", (0.25, 0.22, 0.38, 1.00),
            lambda: self._fire("import_sap"),
        )
        imgui.same_line()

        # --- MODEL etiketi (sağa yaslamak yerine ortada bırak) ---
        imgui.text_colored(model_text, 0.60, 0.65, 0.72, 1.00)

        # --- Sağa yaslanan butonlar ---
        # Mevcut pencere genişliğinden yer hesabı:
        avail = imgui.get_content_region_available_width()

        # Print + Zones + Vis butonlarını sağa yerleştir
        # (kabaca, 3 buton ~ 200px)
        right_block = 260.0
        if avail > right_block:
            imgui.same_line(position=imgui.get_window_width() - right_block)

        self._styled_button(
            "VIS", (0.20, 0.40, 0.50, 1.00),
            lambda: self._fire("visibility"),
        )
        imgui.same_line()

        self._styled_button(
            "zones", (0.15, 0.45, 0.60, 1.00),
            lambda: self._fire("wind"),
        )
        imgui.same_line()

        self._styled_button(
            "print", (0.15, 0.45, 0.60, 1.00),
            lambda: self._fire("print"),
        )

    # ------------------------------------------------------------------
    def _styled_button(self, label: str, base_color, on_click,
                        hovered=None, active=None):
        """Renkli ImGui butonu."""
        if hovered is None:
            hovered = tuple(min(c + 0.08, 1.0) for c in base_color[:3]) + (1.0,)
        if active is None:
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

    # ------------------------------------------------------------------
    def _fire(self, key: str):
        fn = self.callbacks.get(key)
        if callable(fn):
            fn()