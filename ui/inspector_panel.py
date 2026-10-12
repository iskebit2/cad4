# ui/inspector_panel.py
"""
InspectorPanel — İki sekmeli ana panel.

Sekmeler:
  1) Inspector   → seçili elemanı düzenle
  2) Tanımlar    → scene.def_mgr içeriği (malzeme, kesit, yükler, ...)

Kullanım:
    panel = InspectorPanel(on_apply_element=...)
    panel.open_element(element)             # Inspector sekmesi
    panel.open_scene(scene)                 # Tanımlar sekmesi
    panel.open_multi(elements)              # Çoklu seçim
    panel.draw()
"""
import json
from typing import Any, Callable, Dict, List, Optional

import imgui

from ui.inspector_tab import InspectorTab
from ui.definitions_tab import DefinitionsTab


class InspectorPanel:

    TAB_INSPECTOR = 0
    TAB_DEFINITIONS = 1

    def __init__(self,
                 width=380, height=620,
                 on_apply_element: Optional[Callable[[Any, Dict], None]] = None):
        self.visible = False
        self.width = width
        self.height = height

        self.on_apply_element = on_apply_element

        # İki alt sekme
        self.inspector_tab = InspectorTab(
            on_apply=self._on_inspector_apply,
        )
        self.definitions_tab = DefinitionsTab()

        # Aktif sekme
        self._active_tab = self.TAB_INSPECTOR

        # Sahne referansı (Tanımlar sekmesi için)
        self.scene = None

        # Element referansları
        self._element = None
        self._elements: Optional[List] = None

        self._first_open = True

    # ------------------------------------------------------------------
    # AÇMA
    # ------------------------------------------------------------------
    def open_element(self, element):
        """Tek eleman için Inspector sekmesi."""
        self._element = element
        self._elements = None
        self.visible = True
        self._first_open = True
        self._active_tab = self.TAB_INSPECTOR
        self.inspector_tab.open_element(element)

    def open_multi(self, elements):
        """Çoklu seçim için Inspector sekmesi."""
        self._element = None
        self._elements = list(elements)
        self.visible = True
        self._first_open = True
        self._active_tab = self.TAB_INSPECTOR
        self.inspector_tab.open_multi(elements)

    def open_definitions(self, scene):
        """Tanımlar sekmesini aç."""
        self.scene = scene
        self.definitions_tab.open(scene)
        self.visible = True
        self._first_open = True
        self._active_tab = self.TAB_DEFINITIONS

    def close(self):
        self.visible = False

    def has_result(self) -> bool:
        """Geriye dönük uyumluluk — alt sekmeden sonuç geldi mi?"""
        return self.inspector_tab.has_result()

    def consume_result(self):
        return self.inspector_tab.consume_result()

    # ------------------------------------------------------------------
    # DRAW
    # ------------------------------------------------------------------
    def draw(self):
        if not self.visible:
            return

        if self._first_open:
            io = imgui.get_io()
            imgui.set_next_window_position(
                io.display_size[0] - self.width - 20, 40,
                condition=imgui.FIRST_USE_EVER,
            )
            imgui.set_next_window_size(self.width, self.height,
                                       condition=imgui.FIRST_USE_EVER)
            self._first_open = False

        expanded, opened = imgui.begin(self._make_title(), True)
        if not opened:
            self.visible = False
            imgui.end()
            return

        # --- Sekmeler ---
        self._draw_tabs()
        imgui.separator()

        # --- Aktif sekme içeriği ---
        if self._active_tab == self.TAB_INSPECTOR:
            self.inspector_tab.draw_content()
        elif self._active_tab == self.TAB_DEFINITIONS:
            self.definitions_tab.draw_content()

        imgui.end()

    # ------------------------------------------------------------------
    def _make_title(self):
        if self._element is not None:
            et = getattr(self._element, "element_type", "?")
            lbl = getattr(self._element, "label", "?")
            return f"{et}: {lbl}###InspectorMain"
        elif self._elements:
            return f"{len(self._elements)} eleman seçili###InspectorMain"
        return "Inspector###InspectorMain"

    def _draw_tabs(self):
        # Sekme butonları
        tabs = [
            (self.TAB_INSPECTOR, "Inspector"),
            (self.TAB_DEFINITIONS, "Tanımlar"),
        ]

        avail = imgui.get_content_region_available_width()
        btn_w = (avail - 8) / len(tabs)

        for i, (tab_id, label) in enumerate(tabs):
            if i > 0:
                imgui.same_line()

            active = (self._active_tab == tab_id)
            if active:
                imgui.push_style_color(imgui.COLOR_BUTTON,
                                       0.20, 0.50, 0.75, 1.0)
                imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED,
                                       0.28, 0.62, 0.88, 1.0)

            if imgui.button(label, width=btn_w):
                self._active_tab = tab_id
                # Tanımlar sekmesi açılırken scene'i tazele
                if tab_id == self.TAB_DEFINITIONS and self.scene is not None:
                    self.definitions_tab.refresh(self.scene)

            if active:
                imgui.pop_style_color(2)

    # ------------------------------------------------------------------
    def _on_inspector_apply(self, element, values):
        """InspectorTab Apply → dışarı haber ver."""
        if callable(self.on_apply_element):
            self.on_apply_element(element, values)