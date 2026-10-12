# ui/main_menu.py
"""
MainMenuPopup — Kivy MainMenuPanel'inin ImGui karşılığı.

Kullanım:
    menu = MainMenuPopup(on_action=callback)
    # her frame:
    menu.draw()
    # buton tıklanınca callback(action_key) çağrılır
"""
from typing import Callable, Optional

import imgui


class MainMenuPopup:
    """
    Ana menü penceresi. `visible=True` iken çizilir.
    Bir öğeye tıklanınca `on_action(key)` çağrılır ve menü kapanır.
    """

    def __init__(self, on_action: Optional[Callable[[str], None]] = None):
        self.visible = False
        self.on_action = on_action
        self._first_open = True

    def open(self):
        self.visible = True
        self._first_open = True

    def close(self):
        self.visible = False

    # ------------------------------------------------------------------
    def draw(self):
        if not self.visible:
            return

        if self._first_open:
            io = imgui.get_io()
            # Ekranın ortasına yakın bir yere yerleştir
            w, h = 320.0, 340.0
            imgui.set_next_window_position(
                (io.display_size[0] - w) * 0.5,
                (io.display_size[1] - h) * 0.5,
                condition=imgui.FIRST_USE_EVER,
            )
            imgui.set_next_window_size(w, h, condition=imgui.FIRST_USE_EVER)
            self._first_open = False

        flags = (
            imgui.WINDOW_NO_RESIZE
            | imgui.WINDOW_NO_COLLAPSE
            | imgui.WINDOW_NO_SAVED_SETTINGS
        )
        expanded, opened = imgui.begin("Ana Menü", True, flags)
        if not opened:
            self.visible = False
            imgui.end()
            return

        # --- Menü öğeleri ---
        items = [
            ("inspector",    "→  Inspector"),
            ("analysis",     "→  Analysis"),
            ("new_project",  "→  Yeni Proje"),
            ("open_project", "→  Proje Aç"),
            ("save_project", "→  Projeyi Kaydet"),
            ("import_s2k",   "→  S2K İçe Aktar"),
            ("visibility",   "→  Görünürlük"),
        ]

        for key, label in items:
            if imgui.button(label, width=-1):
                if callable(self.on_action):
                    self.on_action(key)
                self.visible = False
                break

        imgui.spacing()
        imgui.separator()
        imgui.spacing()

        if imgui.button("Kapat", width=-1):
            self.visible = False

        imgui.end()