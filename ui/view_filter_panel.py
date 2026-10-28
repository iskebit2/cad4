# ui/view_filter_panel.py
"""
ViewFilterPanel — Kamera + Görünüm Aralığı (aktif UCS'ye göre).
"""
from collections.abc import Callable

from imgui_bundle import imgui

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

    SECTION_MODES = [
        ("Kapalı", "off"),
        ("Aralık", "range"),
        ("Önü",    "after"),
        ("Arkası", "before"),
    ]

    def __init__(self, on_apply: Callable | None = None):
        super().__init__(
            title="Kamera ve Görünüm",
            width=420, height=680,
            pos_first_use=(800, 40),
        )
        self.camera = None
        self.on_apply = on_apply

        # View preset
        self._sel_preset: str | None = None

        # Section filter state
        self._section_mode = "off"
        self._section_min = -1000.0
        self._section_max = 1000.0

        # Aktif UCS ismi (grid tarafından set edilir)
        self.ucs_name = "Global XY"

    def open(self, camera=None):
        super().open()
        if camera is not None:
            self.camera = camera
            self._sel_preset = getattr(camera, "view_preset", None)
            self._section_mode = "off"
            self._section_min = float(getattr(camera, "section_min", -1000.0))
            self._section_max = float(getattr(camera, "section_max", 1000.0))
            if getattr(camera, "section_active", False):
                self._section_mode = "range"

    # ------------------------------------------------------------------
    def draw_content(self):
        if self.camera is None:
            imgui.text_colored(imgui.ImVec4(0.9, 0.5, 0.5, 1.0), 'Kamera bağlı değil')
            return

        imgui.begin_child("camera_content", imgui.ImVec2(0, 0))
        try:
            self._draw_camera_group()
            self._draw_projection_group()
            self._draw_view_presets_group()
            self._draw_section_group()
        finally:
            imgui.end_child()

    # ------------------------------------------------------------------
    # 1) KAMERA
    # ------------------------------------------------------------------
    def _draw_camera_group(self):
        cam = self.camera
        if not imgui.collapsing_header("Kamera", True)[0]:
            return

        imgui.text_colored(imgui.ImVec4(0.7, 0.8, 0.9, 1.0), 'Hedef (target)')
        imgui.push_item_width(-1)
        tx, ty, tz = float(cam.target.x), float(cam.target.y), float(cam.target.z)

        imgui.text("X"); imgui.same_line(30)
        cx, tx = self._input_float("##tx", tx, step=cam.model_size * 0.01)
        imgui.same_line()
        imgui.text("Y"); imgui.same_line(30)
        cy, ty = self._input_float("##ty", ty, step=cam.model_size * 0.01)
        imgui.same_line()
        imgui.text("Z"); imgui.same_line(30)
        cz, tz = self._input_float("##tz", tz, step=cam.model_size * 0.01)
        imgui.pop_item_width()

        if cx or cy or cz:
            import glm
            cam.target = glm.vec3(tx, ty, tz)
            cam._invalidate()

        imgui.spacing()

        imgui.text(f"Mesafe: {cam.distance:.2f}")
        changed, new_val = imgui.slider_float(
            "##distance", float(cam.distance),
            float(cam.min_distance), float(cam.max_distance),
            format="%.2f",
        )
        if changed:
            cam.distance = new_val
            cam._invalidate()

        imgui.text(f"Pitch: {cam.pitch:.1f}°")
        changed, new_val = imgui.slider_float(
            "##pitch", float(cam.pitch),
            float(cam.min_pitch), float(cam.max_pitch),
            format="%.1f°",
        )
        if changed:
            cam.pitch = new_val
            cam._invalidate()

        imgui.text(f"Yaw: {cam.yaw:.1f}°")
        changed, new_val = imgui.slider_float(
            "##yaw", float(cam.yaw), -180.0, 180.0, format="%.1f°",
        )
        if changed:
            cam.yaw = new_val
            cam._invalidate()

        imgui.spacing()

        avail = imgui.get_content_region_avail().x
        btn_w = (avail - 8) * 0.5
        if imgui.button("Model'e Odakla", imgui.ImVec2(btn_w, 0)):
            cam.focus_on_model()
        imgui.same_line()
        if imgui.button("Kamerayı Sıfırla", imgui.ImVec2(btn_w, 0)):
            cam.reset()

        imgui.spacing()
        imgui.separator()

    # ------------------------------------------------------------------
    # 2) PROJEKSİYON
    # ------------------------------------------------------------------
    def _draw_projection_group(self):
        cam = self.camera
        if not imgui.collapsing_header("Projeksiyon", False)[0]:
            return

        imgui.text("Mod:")
        imgui.same_line(120)
        is_persp = (cam.view_mode == "PERSPECTIVE")
        if imgui.radio_button("Perspektif##pm", is_persp):
            if not is_persp:
                cam.view_mode = "PERSPECTIVE"
                cam._projection_matrix = None
        imgui.same_line()
        if imgui.radio_button("Ortho##om", not is_persp):
            if is_persp:
                cam.view_mode = "ORTHO"
                cam._projection_matrix = None

        imgui.spacing()

        if cam.view_mode == "PERSPECTIVE":
            imgui.text(f"FOV: {cam.fov:.1f}°")
            changed, new_val = imgui.slider_float(
                "##fov", float(cam.fov), 10.0, 120.0, format="%.1f°",
            )
            if changed:
                cam.fov = new_val
                cam._projection_matrix = None

        imgui.text(f"Near ratio: {cam.near_ratio:.5f}")
        changed, new_val = imgui.slider_float(
            "##near_r", float(cam.near_ratio), 0.0001, 0.1, format="%.5f",
        )
        if changed:
            cam.near_ratio = max(new_val, 0.0001)
            cam._projection_matrix = None

        imgui.text(f"Far ratio: {cam.far_ratio:.2f}")
        changed, new_val = imgui.slider_float(
            "##far_r", float(cam.far_ratio), 1.0, 100.0, format="%.2f",
        )
        if changed:
            cam.far_ratio = new_val
            cam._projection_matrix = None

        imgui.spacing()
        imgui.text_colored(imgui.ImVec4(0.6, 0.6, 0.6, 1.0), f'near={cam.near:.2f}  far={cam.far:.2f}')



        imgui.spacing()
        imgui.separator()

    # ------------------------------------------------------------------
    # 3) VIEW PRESETS
    # ------------------------------------------------------------------
    def _draw_view_presets_group(self):
        if not imgui.collapsing_header("Hazır Bakışlar", True)[0]:
            return

        for i, (label, key) in enumerate(self.VIEW_PRESETS):
            if i % 4 != 0:
                imgui.same_line()
            active = (self._sel_preset == key)
            if active:
                imgui.push_style_color(
                    imgui.Col_.button, imgui.ImVec4(0.20, 0.50, 0.75, 1.0)
                )
                imgui.push_style_color(
                    imgui.Col_.button_hovered, imgui.ImVec4(0.28, 0.62, 0.88, 1.0)
                )

            if imgui.button(label, imgui.ImVec2(90, 0)):
                self._sel_preset = None if self._sel_preset == key else key
                self._apply_preset()

            if active:
                imgui.pop_style_color(2)

        imgui.spacing()
        imgui.separator()

    # ------------------------------------------------------------------
    # 4) SECTION FILTER
    # ------------------------------------------------------------------
    def _draw_section_group(self):
        if not imgui.collapsing_header("Görünüm Aralığı (Aktif UCS)", True)[0]:
            return

        imgui.text_colored(imgui.ImVec4(0.6, 0.9, 0.6, 1.0), f'Aktif UCS: {self.ucs_name}')

        imgui.text("Mod:")
        for i, (label, key) in enumerate(self.SECTION_MODES):
            if i % 4 != 0:
                imgui.same_line()
            active = (self._section_mode == key)
            if active:
                imgui.push_style_color(
                    imgui.Col_.button, imgui.ImVec4(0.20, 0.50, 0.75, 1.0)
                )
                imgui.push_style_color(
                    imgui.Col_.button_hovered, imgui.ImVec4(0.28, 0.62, 0.88, 1.0)
                )
            if imgui.button(label, imgui.ImVec2(90, 0)):
                self._section_mode = key
                self._apply_section()
            if active:
                imgui.pop_style_color(2)

        imgui.spacing()

        imgui.push_item_width(180)
        imgui.text("Alt sınır (mm):")
        ch_min, self._section_min = imgui.input_float(
            "##min", float(self._section_min), step=100.0, format="%.1f")
        imgui.text("Üst sınır (mm):")
        ch_max, self._section_max = imgui.input_float(
            "##max", float(self._section_max), step=100.0, format="%.1f")
        imgui.pop_item_width()

        if ch_min or ch_max:
            self._apply_section()

        imgui.spacing()
        if imgui.button("Sıfırla", imgui.ImVec2(-1, 0)):
            self._section_min = -1000.0
            self._section_max = 1000.0
            self._apply_section()

    # ------------------------------------------------------------------
    @staticmethod
    def _input_float(label: str, value: float, step: float = 0.1):
        return imgui.input_float(label, float(value), step=step, format="%.2f")

    def _apply_preset(self):
        if self.camera is None:
            return
        if self._sel_preset:
            self.camera.set_view_preset(self._sel_preset)
        else:
            self.camera.clear_view_preset()

    def _apply_section(self):
        if self.camera is None:
            return
        if callable(self.on_apply):
            try:
                self.on_apply(self._section_mode,
                              self._section_min,
                              self._section_max)
            except Exception:
                import traceback
                traceback.print_exc()