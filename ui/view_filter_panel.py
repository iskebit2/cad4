# ui/view_filter_panel.py
"""
ViewFilterPanel — ImGui sürümü.

Kullanım:
    panel = ViewFilterPanel(on_apply=callback)
    panel.open(camera)
    # her frame:
    panel.draw()
"""
from typing import Callable, Optional

import imgui


class ViewFilterPanel:

    VIEW_PRESETS = [
        ("Front",  "front"),
        ("Back",   "back"),
        ("Top",    "top"),
        ("Bottom", "bottom"),
        ("Left",   "left"),
        ("Right",  "right"),
        ("Iso",    "iso"),
    ]

    PLANES = [
        ("Off", None),
        ("XY",  "XY"),
        ("XZ",  "XZ"),
        ("YZ",  "YZ"),
    ]

    def __init__(self, on_apply: Optional[Callable] = None):
        self.visible = False
        self.camera = None
        self.on_apply = on_apply

        self._sel_preset = None
        self._sel_plane = None
        self._sel_direction = "positive"
        self._sel_offset = 0.0

        self._first_open = True

    # ------------------------------------------------------------------
    def open(self, camera):
        self.camera = camera
        self.visible = True
        self._first_open = True

        # Kameranın mevcut durumundan senkronize et
        if camera is not None:
            self._sel_preset = getattr(camera, "view_preset", None)
            self._sel_plane = getattr(camera, "active_plane", None)
            self._sel_direction = getattr(camera, "plane_direction", "positive")
            self._sel_offset = getattr(camera, "plane_offset", 0.0)

    def close(self):
        self.visible = False

    # ------------------------------------------------------------------
    def draw(self):
        if not self.visible:
            return

        if self._first_open:
            io = imgui.get_io()
            w, h = 380, 480
            imgui.set_next_window_position(
                io.display_size[0] - w - 420, 40,
                condition=imgui.FIRST_USE_EVER,
            )
            imgui.set_next_window_size(w, h, condition=imgui.FIRST_USE_EVER)
            self._first_open = False

        expanded, opened = imgui.begin("View & Plan Filter", True)
        if not opened:
            self.visible = False
            imgui.end()
            return

        # --- VIEW ---
        imgui.text_colored("VIEW", 0.5, 0.8, 1.0, 1.0)
        imgui.separator()

        # 4'lü grid — preset butonları
        for i, (label, key) in enumerate(self.VIEW_PRESETS):
            if i % 4 != 0:
                imgui.same_line()
            active = (self._sel_preset == key)
            if active:
                imgui.push_style_color(imgui.COLOR_BUTTON,
                                       0.20, 0.50, 0.75, 1.0)
                imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED,
                                       0.28, 0.62, 0.88, 1.0)
            if imgui.button(label, width=85):
                # Toggle davranışı
                if self._sel_preset == key:
                    self._sel_preset = None
                else:
                    self._sel_preset = key
            if active:
                imgui.pop_style_color(2)

        imgui.spacing()
        imgui.spacing()

        # --- PLAN ---
        imgui.text_colored("PLAN", 0.5, 0.8, 1.0, 1.0)
        imgui.separator()

        for i, (label, key) in enumerate(self.PLANES):
            if i % 4 != 0:
                imgui.same_line()
            active = (self._sel_plane == key)
            if active:
                imgui.push_style_color(imgui.COLOR_BUTTON,
                                       0.20, 0.50, 0.75, 1.0)
                imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED,
                                       0.28, 0.62, 0.88, 1.0)
            if imgui.button(label, width=85):
                self._sel_plane = key
            if active:
                imgui.pop_style_color(2)

        imgui.spacing()

        # --- DIRECTION ---
        plane_active = self._sel_plane is not None
        if not plane_active:
            imgui.push_style_var(imgui.STYLE_ALPHA, 0.4)

        dir_pos = (self._sel_direction == "positive")
        if imgui.radio_button("Positive (+)", dir_pos):
            self._sel_direction = "positive"
        imgui.same_line()
        if imgui.radio_button("Negative (-)", not dir_pos):
            self._sel_direction = "negative"

        # --- OFFSET SLIDER ---
        # Model boyutundan min/max
        if self.camera is not None:
            size = getattr(self.camera, "model_size", 1000.0)
        else:
            size = 1000.0

        # Slider int/float farkı için iki değerli kullan
        imgui.text(f"Offset ({self._sel_offset:.2f})")
        imgui.push_item_width(-1)
        changed, new_val = imgui.slider_float(
            "##offset",
            float(self._sel_offset),
            -float(size), float(size),
            format="%.2f",
        )
        imgui.pop_item_width()
        if changed:
            self._sel_offset = new_val

        # Hızlı offset seçenekleri
        if self.camera is not None and self._sel_plane is not None:
            imgui.spacing()
            imgui.text_colored("Hızlı:", 0.7, 0.7, 0.7, 1.0)
            if imgui.button("Merkez", width=85):
                # Model merkezine göre offset
                center = getattr(self.camera, "model_center",
                                 [0, 0, 0])
                if self._sel_plane == "XY":
                    self._sel_offset = float(center[2])
                elif self._sel_plane == "XZ":
                    self._sel_offset = float(center[1])
                elif self._sel_plane == "YZ":
                    self._sel_offset = float(center[0])

        if not plane_active:
            imgui.pop_style_var(1)

        imgui.spacing()
        imgui.separator()
        imgui.spacing()

        # --- Alt butonlar ---
        avail = imgui.get_content_region_available_width()
        btn_w = (avail - 8) * 0.5

        imgui.push_style_color(imgui.COLOR_BUTTON,
                               0.45, 0.20, 0.20, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED,
                               0.60, 0.28, 0.28, 1.0)
        if imgui.button("Temizle", width=btn_w):
            self._sel_preset = None
            self._sel_plane = None
            self._sel_offset = 0.0
            self._apply()
        imgui.pop_style_color(2)

        imgui.same_line()

        imgui.push_style_color(imgui.COLOR_BUTTON,
                               0.20, 0.55, 0.30, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED,
                               0.28, 0.68, 0.40, 1.0)
        if imgui.button("Apply", width=btn_w):
            self._apply()
        imgui.pop_style_color(2)

        imgui.end()

    # ------------------------------------------------------------------
    def _apply(self):
        if self.camera is None:
            return

        # 1) View preset
        if self._sel_preset:
            self.camera.set_view_preset(self._sel_preset)
        else:
            self.camera.clear_view_preset()

        # 2) Plan filter — doğrudan engine.apply_plane_filter
        if callable(self.on_apply):
            try:
                self.on_apply(
                    self._sel_plane,
                    self._sel_offset,
                    self._sel_direction,
                )
            except Exception:
                import traceback
                traceback.print_exc()