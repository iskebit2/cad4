# ui/view_filter_panel.py
"""
ViewFilterPanel — BasePanel türevi. Eş zamanlı (real-time) görünüm ve düzlem filtreleme.
"""
from typing import Callable, Optional
import imgui

from ui.base_panel import BasePanel


class ViewFilterPanel(BasePanel):

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
        super().__init__(title="View & Plan Filter", width=380, height=440, pos_first_use=(800, 40))
        self.camera = None
        self.on_apply = on_apply

        self._sel_preset = None
        self._sel_plane = None
        self._sel_direction = "positive"
        self._sel_offset = 0.0

    def open(self, camera=None):
        super().open()
        if camera is not None:
            self.camera = camera
            self._sel_preset = getattr(camera, "view_preset", None)
            self._sel_plane = getattr(camera, "active_plane", None)
            self._sel_direction = getattr(camera, "plane_direction", "positive")
            self._sel_offset = getattr(camera, "plane_offset", 0.0)

    def draw_content(self):
        # --- VIEW ---
        imgui.text_colored("VIEW", 0.5, 0.8, 1.0, 1.0)
        imgui.separator()

        for i, (label, key) in enumerate(self.VIEW_PRESETS):
            if i % 4 != 0:
                imgui.same_line()
            active = (self._sel_preset == key)
            if active:
                imgui.push_style_color(imgui.COLOR_BUTTON, 0.20, 0.50, 0.75, 1.0)
                imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.28, 0.62, 0.88, 1.0)
            
            if imgui.button(label, width=85):
                if self._sel_preset == key:
                    self._sel_preset = None
                else:
                    self._sel_preset = key
                self._apply()  # ← Eş zamanlı tetikle
                
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
                imgui.push_style_color(imgui.COLOR_BUTTON, 0.20, 0.50, 0.75, 1.0)
                imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.28, 0.62, 0.88, 1.0)
            
            if imgui.button(label, width=85):
                self._sel_plane = key
                self._apply()  # ← Eş zamanlı tetikle
                
            if active:
                imgui.pop_style_color(2)

        imgui.spacing()

        # --- DIRECTION ---
        plane_active = self._sel_plane is not None
        if not plane_active:
            imgui.push_style_var(imgui.STYLE_ALPHA, 0.4)

        dir_pos = (self._sel_direction == "positive")
        if imgui.radio_button("Positive (+)", dir_pos):
            if self._sel_direction != "positive":
                self._sel_direction = "positive"
                self._apply()
        imgui.same_line()
        if imgui.radio_button("Negative (-)", not dir_pos):
            if self._sel_direction != "negative":
                self._sel_direction = "negative"
                self._apply()

        # --- OFFSET SLIDER ---
        size = getattr(self.camera, "model_size", 1000.0) if self.camera is not None else 1000.0

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
            self._apply()  # ← Slider sürüklendikçe anlık tetikle

        # Hızlı offset seçenekleri
        if self.camera is not None and self._sel_plane is not None:
            imgui.spacing()
            imgui.text_colored("Hızlı:", 0.7, 0.7, 0.7, 1.0)
            if imgui.button("Merkez", width=85):
                center = getattr(self.camera, "model_center", [0, 0, 0])
                if self._sel_plane == "XY":
                    self._sel_offset = float(center[2])
                elif self._sel_plane == "XZ":
                    self._sel_offset = float(center[1])
                elif self._sel_plane == "YZ":
                    self._sel_offset = float(center[0])
                self._apply()  # ← Eş zamanlı tetikle

        if not plane_active:
            imgui.pop_style_var(1)

        imgui.spacing()
        imgui.separator()
        imgui.spacing()

        # --- Alt Tek Buton (Sadece Temizle / Sıfırla) ---
        avail = imgui.get_content_region_available_width()
        imgui.push_style_color(imgui.COLOR_BUTTON, 0.45, 0.20, 0.20, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.60, 0.28, 0.28, 1.0)
        
        if imgui.button("Filtreyi Temizle", width=avail):
            self._sel_preset = None
            self._sel_plane = None
            self._sel_offset = 0.0
            self._apply()
            
        imgui.pop_style_color(2)

    def _apply(self):
        if self.camera is None:
            return

        if self._sel_preset:
            self.camera.set_view_preset(self._sel_preset)
        else:
            self.camera.clear_view_preset()

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