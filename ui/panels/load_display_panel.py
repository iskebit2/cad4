# ui/panels/load_display_panel.py
from __future__ import annotations

from imgui_bundle import imgui

from logging_config import CadLogger
from ui.base.panel_base import PanelBase, Category

logger = CadLogger.get(__name__)


class LoadDisplayPanel(PanelBase):
    __abstract__ = False
    panel_name = "load_display"
    title = "Yük Görüntüleme"
    category = Category.VIEW
    quick = True
    context = ("math_model", "renderer")
    uses_draft = False
    show_apply_bar = False
    use_standard_layout = True
    preview_flags = {"loads": True}

    width = 460
    height = 640
    pos_first_use = (480.0, 60.0)

    def __init__(self, app=None, **overrides):
        super().__init__(app=app, **overrides)
        self.math_model = None
        self.renderer = None
        self.on_change = None
        self.on_clear_loads = None
        self.on_clear_all = None

        self.show_loads = False
        self.show_frame_loads = True
        self.show_area_loads = False
        self.show_point_loads = False

        self.active_pattern: str | None = None
        self.available_patterns: list[str] = []

        self.profile_scale = 1.0
        self.line_width = 2.0
        self.fill_alpha = 0.28
        self.show_arrows = True
        self.show_fill = True

        self.clear_pattern_combo_idx = 0
        self._pattern_signature = None

    # ------------------------------------------------------------------
    def _on_context_ready(self) -> None:
        self.math_model = getattr(self, "math_model", None)
        self.renderer = getattr(self, "renderer", None)
        lr = getattr(self.renderer, "load_renderer", None) if self.renderer else None
        if lr:
            self.show_frame_loads = bool(getattr(lr, "show_frame_loads", True))
            self.show_point_loads = bool(getattr(lr, "show_point_loads", True))
            self.active_pattern = getattr(lr, "active_pattern", None)
            self.profile_scale = float(getattr(lr, "profile_scale", 1.0))
            self.line_width = float(getattr(lr, "line_width", 2.0))
            self.fill_alpha = float(getattr(lr, "fill_alpha", 0.28))
            self.show_arrows = bool(getattr(lr, "show_arrows", True))
            self.show_fill = bool(getattr(lr, "show_fill", True))
        self._refresh_patterns()

    def set_loads_visible(self, enabled: bool, renderer=None, math_model=None) -> None:
        if renderer is not None:
            self.renderer = renderer
        if math_model is not None:
            self.math_model = math_model
        self.show_loads = bool(enabled)
        self._apply()

    # ------------------------------------------------------------------
    # SETTINGS — master + tip + pattern
    # ------------------------------------------------------------------
    def draw_settings(self) -> None:
        # Master toggle
        changed, new_val = imgui.checkbox("Yükleri Göster", self.show_loads)
        if changed:
            self.show_loads = new_val
            self._apply()
        imgui.same_line()
        if self.show_loads:
            imgui.text_colored(imgui.ImVec4(0.4, 0.9, 0.5, 1.0), "✓")
        else:
            imgui.text_colored(imgui.ImVec4(0.9, 0.4, 0.4, 1.0), "✗")
        imgui.same_line(280)
        imgui.text_disabled(f"Toplam pattern: {len(self.available_patterns)}")

        imgui.separator()

        # Tip filtresi
        self.section_label("Yük Tipi")
        changed, self.show_frame_loads = imgui.checkbox(
            "Frame (kiriş/kolon) yayılı", self.show_frame_loads
        )
        if changed:
            self._apply()
        changed, self.show_area_loads = imgui.checkbox(
            "Area (yüzey) alan yükleri", self.show_area_loads
        )
        if changed:
            self._apply()
        changed, self.show_point_loads = imgui.checkbox(
            "Point (nokta) yükler", self.show_point_loads
        )
        if changed:
            self._apply()

        imgui.separator()

        # Pattern filtresi
        self.section_label("Pattern Filtresi")
        if not self.available_patterns:
            imgui.text_disabled("(Pattern bulunamadı)")
            return

        items = ["<Tümü>"] + self.available_patterns
        current = self.active_pattern
        if current is None:
            idx = 0
        elif current in self.available_patterns:
            idx = 1 + self.available_patterns.index(current)
        else:
            idx = 0
            self.active_pattern = None

        imgui.push_item_width(-1)
        changed, new_idx = imgui.combo("##pattern", idx, items)
        if changed:
            self.active_pattern = None if new_idx == 0 else items[new_idx]
            self._apply()
        imgui.pop_item_width()

        avail = imgui.get_content_region_avail().x
        btn_w = (avail - 8) / 2.0
        if imgui.button("Tümünü Seç", imgui.ImVec2(btn_w, 0)):
            self.active_pattern = None
            self._apply()
        imgui.same_line()
        if imgui.button("WIND Filtrele", imgui.ImVec2(btn_w, 0)):
            wind_pats = [p for p in self.available_patterns if p.upper().startswith("WIND")]
            if wind_pats:
                self.active_pattern = wind_pats[0]
            self._apply()

    # ------------------------------------------------------------------
    # TABLE — görsel ayarlar
    # ------------------------------------------------------------------
    def draw_table(self) -> None:
        self.section_label("Görsel Ayarlar")

        flags = (
            imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
            | imgui.TableFlags_.sizing_stretch_prop
        )
        if not imgui.begin_table("load_display_vis", 3, flags, imgui.ImVec2(0, 160)):
            return

        imgui.table_setup_column("Parametre", imgui.TableColumnFlags_.width_stretch)
        imgui.table_setup_column("Değer",     imgui.TableColumnFlags_.width_stretch)
        imgui.table_setup_column("",          imgui.TableColumnFlags_.width_fixed, 60)
        imgui.table_headers_row()

        # Profil ölçeği
        imgui.table_next_row()
        imgui.table_set_column_index(0)
        imgui.text("Profil Ölçeği")
        imgui.table_set_column_index(1)
        imgui.push_item_width(-1)
        ch, val = imgui.slider_float("##scale", self.profile_scale, 0.3, 3.0, f"{self.profile_scale:.2f}x")
        if ch:
            self.profile_scale = val
            self._apply()
        imgui.pop_item_width()
        imgui.table_set_column_index(2)
        imgui.text_disabled("x")

        # Çizgi kalınlığı
        imgui.table_next_row()
        imgui.table_set_column_index(0)
        imgui.text("Çizgi Kalınlığı")
        imgui.table_set_column_index(1)
        imgui.push_item_width(-1)
        ch, val = imgui.slider_float("##lw", self.line_width, 1.0, 5.0, f"{self.line_width:.1f}")
        if ch:
            self.line_width = val
            self._apply()
        imgui.pop_item_width()
        imgui.table_set_column_index(2)
        imgui.text_disabled("px")

        # Dolgu alpha
        imgui.table_next_row()
        imgui.table_set_column_index(0)
        imgui.text("Dolgu Şeffaflığı")
        imgui.table_set_column_index(1)
        imgui.push_item_width(-1)
        ch, val = imgui.slider_float("##alpha", self.fill_alpha, 0.0, 1.0, f"{self.fill_alpha:.2f}")
        if ch:
            self.fill_alpha = val
            self._apply()
        imgui.pop_item_width()
        imgui.table_set_column_index(2)
        imgui.text_disabled("α")

        # Okları göster
        imgui.table_next_row()
        imgui.table_set_column_index(0)
        imgui.text("Okları Göster")
        imgui.table_set_column_index(1)
        ch, self.show_arrows = imgui.checkbox("##arrows", self.show_arrows)
        if ch:
            self._apply()

        # Dolguyu göster
        imgui.table_next_row()
        imgui.table_set_column_index(0)
        imgui.text("Dolguyu Göster")
        imgui.table_set_column_index(1)
        ch, self.show_fill = imgui.checkbox("##fill", self.show_fill)
        if ch:
            self._apply()

        imgui.end_table()

    # ------------------------------------------------------------------
    # ACTIONS — temizleme
    # ------------------------------------------------------------------
    def draw_actions(self) -> None:
        self.section_label("Yük Temizleme")

        items = ["<Seçili pattern>"] + self.available_patterns
        if not self.available_patterns:
            imgui.text_disabled("(Pattern yok)")
            return

        imgui.push_item_width(-1)
        changed, new_idx = imgui.combo("##clear_pat", self.clear_pattern_combo_idx, items)
        if changed:
            self.clear_pattern_combo_idx = new_idx
        imgui.pop_item_width()

        pattern_to_clear = (
            self.active_pattern
            if self.clear_pattern_combo_idx == 0
            else self.available_patterns[self.clear_pattern_combo_idx - 1]
        )

        if not pattern_to_clear:
            self.status_line("⚠ Önce bir pattern seçin", "warn")
            return

        count = self._count_pattern_usage(pattern_to_clear)
        imgui.text_colored(
            imgui.ImVec4(0.7, 0.85, 0.9, 1.0),
            f"'{pattern_to_clear}' → {count} elemanda var",
        )

        imgui.spacing()

        imgui.push_style_color(imgui.Col_.button, imgui.ImVec4(0.65, 0.30, 0.30, 1.0))
        imgui.push_style_color(imgui.Col_.button_hovered, imgui.ImVec4(0.80, 0.40, 0.40, 1.0))
        if imgui.button("Seçili Elemanlardan Sil", imgui.ImVec2(-1, 32)):
            if callable(self.on_clear_loads):
                self.on_clear_loads(pattern_to_clear)
                self._refresh_patterns()
        imgui.pop_style_color(2)

        imgui.push_style_color(imgui.Col_.button, imgui.ImVec4(0.55, 0.20, 0.20, 1.0))
        imgui.push_style_color(imgui.Col_.button_hovered, imgui.ImVec4(0.70, 0.28, 0.28, 1.0))
        if imgui.button("Tüm Sahneden Sil", imgui.ImVec2(-1, 32)):
            if callable(self.on_clear_all):
                self.on_clear_all(pattern_to_clear)
                self._refresh_patterns()
        imgui.pop_style_color(2)

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------
    def _refresh_patterns(self) -> None:
        if not self.math_model:
            self.available_patterns = []
            return
        pats: set[str] = set()
        for f in self.math_model.frames.values():
            sets = getattr(f, "dist_load_sets", None)
            if sets:
                pats.update(sets.keys())
            for dl in getattr(f, "dist_loads", []) or []:
                p = getattr(dl, "pattern_name", None)
                if p:
                    pats.add(p)
        for n in self.math_model.nodes.values():
            for pl in getattr(n, "loads", None) or []:
                p = getattr(pl, "pattern_name", None)
                if p:
                    pats.add(p)
        self.available_patterns = sorted(pats)
        self._pattern_signature = tuple(self.available_patterns)
        if self.active_pattern and self.active_pattern not in self.available_patterns:
            self.active_pattern = None
        if self.clear_pattern_combo_idx > len(self.available_patterns):
            self.clear_pattern_combo_idx = 0

    def _count_pattern_usage(self, pattern: str) -> int:
        if not self.math_model or not pattern:
            return 0
        count = 0
        for f in self.math_model.frames.values():
            if pattern in (getattr(f, "dist_load_sets", {}) or {}):
                count += 1
        for n in self.math_model.nodes.values():
            for pl in getattr(n, "loads", None) or []:
                if getattr(pl, "pattern_name", None) == pattern:
                    count += 1
                    break
        return count

    def _apply(self) -> None:
        if self.renderer:
            if hasattr(self.renderer, "set_loads_enabled"):
                self.renderer.set_loads_enabled(self.show_loads)
            lr = getattr(self.renderer, "load_renderer", None)
            if lr:
                lr.active_pattern = self.active_pattern
                for attr, val in (
                    ("show_frame_loads", self.show_frame_loads),
                    ("show_point_loads", self.show_point_loads),
                    ("profile_scale", self.profile_scale),
                    ("line_width", self.line_width),
                    ("fill_alpha", self.fill_alpha),
                    ("show_arrows", self.show_arrows),
                    ("show_fill", self.show_fill),
                    ("show_area_loads", self.show_area_loads),
                ):
                    if hasattr(lr, attr):
                        setattr(lr, attr, val)
                if hasattr(self.renderer, "area_loads"):
                    self.renderer.area_loads.active_pattern = self.active_pattern
                    self.renderer.area_loads.enabled = self.show_area_loads
                    self.renderer.area_loads.arrow_scale = self.profile_scale

        if self.math_model:
            self.math_model.mark_dirty()
            if self.renderer and hasattr(self.renderer, "load_renderer"):
                cam_scale = (
                    self.renderer._compute_cam_scale()
                    if hasattr(self.renderer, "_compute_cam_scale") else 1.0
                )
                scene_size = getattr(self.renderer, "size", 1.0)
                try:
                    self.renderer.load_renderer.update(
                        self.math_model,
                        camera_scale=cam_scale,
                        scene_size=scene_size,
                    )
                except Exception:
                    logger.exception("[APPLY] update hatası")

        if callable(self.on_change):
            self.on_change()