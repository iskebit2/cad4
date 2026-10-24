# ui/load_display_panel.py
"""
Load Display Panel — Frame/Area yük görselleştirme kontrolü.
- Pattern filtresi (tek veya tümü)
- Tip filtresi (frame/area/point)
- Scale slider
- Renk seçenekleri
- Seçili elemanlardan yük temizleme
"""
import imgui
from typing import Optional, Callable, List, Set

from ui.base_panel import BasePanel


class LoadDisplayPanel(BasePanel):
    """
    Yük görüntüleme kontrol paneli.
    """

    def __init__(self,
                 on_change=None,
                 on_clear_loads=None,
                 on_clear_all=None):
        super().__init__(
            title="Yük Görüntüleme",
            width=420,
            height=520,
            pos_first_use=(480, 60),
            closable=True,
        )
        self.scene = None
        self.renderer = None

        # Callbacks
        self.on_change = on_change           # herhangi bir ayar değişince
        self.on_clear_loads = on_clear_loads # seçili elemandan pattern temizle
        self.on_clear_all = on_clear_all     # tüm WIND_* veya seçili pattern

        # --- State ---
        self.show_loads = False

        # Tip filtreleri
        self.show_frame_loads = True
        self.show_area_loads = False    # henüz yok
        self.show_point_loads = False   # henüz yok

        # Pattern
        self.active_pattern: Optional[str] = None   # None = hepsi
        self.available_patterns: List[str] = []

        # Görsel ayarlar
        self.profile_scale = 1.0        # 0.3 .. 3.0
        self.line_width = 2.0
        self.fill_alpha = 0.28
        self.show_arrows = True
        self.show_fill = True

        # Temizleme
        self.clear_pattern_combo_idx = 0
        self.clear_patterns: List[str] = []

        # Önbellek
        self._pattern_signature = None

    # ------------------------------------------------------------------
        
    def open(self, scene=None, renderer=None):
        if scene is not None:
            self.scene = scene
        if renderer is not None:
            self.renderer = renderer
        self._refresh_patterns()
        super().open()

    # ------------------------------------------------------------------
    # DRAW
    # ------------------------------------------------------------------
    def draw_content(self):
        if not self.scene:
            imgui.text_colored("Sahne bağlı değil.", 0.7, 0.5, 0.5, 1.0)
            return

        # --- Master toggle ---
        self._draw_master_toggle()
        imgui.separator()

        # --- Tip filtresi ---
        self._draw_type_filter()
        imgui.separator()

        # --- Pattern ---
        self._draw_pattern_filter()
        imgui.separator()

        # --- Görsel ayarlar ---
        self._draw_visual_settings()
        imgui.separator()

        # --- Temizleme ---
        self._draw_clear_section()

    # ------------------------------------------------------------------
    # 1. MASTER TOGGLE
    # ------------------------------------------------------------------
    def _draw_master_toggle(self):
        imgui.spacing()
        changed, new_val = imgui.checkbox("Yükleri Göster", self.show_loads)
        if changed:
            self.show_loads = new_val
            self._apply()

        imgui.same_line()
        if self.show_loads:
            imgui.text_colored("✓", 0.4, 0.9, 0.5, 1.0)
        else:
            imgui.text_colored("✗", 0.9, 0.4, 0.4, 1.0)

        imgui.same_line(250)
        imgui.text_colored(
            f"Toplam pattern: {len(self.available_patterns)}",
            0.6, 0.7, 0.8, 1.0
        )

    # ------------------------------------------------------------------
    # 2. TIP FİLTRESİ
    # ------------------------------------------------------------------
    def _draw_type_filter(self):
        imgui.text_colored("Yük Tipi", 0.8, 0.8, 0.6, 1.0)
        imgui.spacing()

        # Frame
        changed, self.show_frame_loads = imgui.checkbox(
            "Frame (kiriş/kolon) yayılı yükler", self.show_frame_loads
        )
        if changed:
            self._apply()

        # Area
        imgui.push_style_color(imgui.COLOR_TEXT, 0.5, 0.5, 0.5, 1.0)
        changed, self.show_area_loads = imgui.checkbox(
            "Area (yüzey) yükler (yakında)", self.show_area_loads
        )
        if changed:
            # Henüz desteklenmiyor
            self.show_area_loads = False
        imgui.pop_style_color(1)

        # Point
        imgui.push_style_color(imgui.COLOR_TEXT, 0.5, 0.5, 0.5, 1.0)
        changed, self.show_point_loads = imgui.checkbox(
            "Point (nokta) yükler (yakında)", self.show_point_loads
        )
        if changed:
            self.show_point_loads = False
        imgui.pop_style_color(1)

    # ------------------------------------------------------------------
    # 3. PATTERN FİLTRESİ
    # ------------------------------------------------------------------
    def _draw_pattern_filter(self):
        imgui.text_colored("Pattern Filtresi", 0.8, 0.8, 0.6, 1.0)
        imgui.spacing()

        # "<Tümü>" + pattern listesi
        items = ["<Tümü>"] + self.available_patterns
        if not self.available_patterns:
            imgui.text_colored("(Pattern bulunamadı)", 0.6, 0.6, 0.6, 1.0)
            return

        # Aktif index
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

        # Renk örneği
        if self.active_pattern and self.renderer:
            lr = getattr(self.renderer, "load_renderer", None)
            if lr and hasattr(lr, "_pattern_color"):
                try:
                    color = lr._pattern_color(self.active_pattern)
                    imgui.same_line()
                    imgui.color_button(
                        "##pat_color", color[0], color[1], color[2], 1.0,
                        imgui.COLOR_EDIT_NO_LABEL, 20, 20
                    )
                except Exception:
                    pass

        # Kısayol butonlar
        imgui.spacing()
        avail = imgui.get_content_region_available_width()
        btn_w = (avail - 8) / 2.0

        if imgui.button("Tümünü Seç", width=btn_w):
            self.active_pattern = None
            self._apply()

        imgui.same_line()
        if imgui.button("WIND Filtrele", width=btn_w):
            wind_pats = [p for p in self.available_patterns
                         if p.upper().startswith("WIND")]
            if wind_pats:
                self.active_pattern = wind_pats[0]
            self._apply()

    # ------------------------------------------------------------------
    # 4. GÖRSEL AYARLAR
    # ------------------------------------------------------------------
    def _draw_visual_settings(self):
        imgui.text_colored("Görsel Ayarlar", 0.8, 0.8, 0.6, 1.0)
        imgui.spacing()

        # Ölçek
        imgui.text("Profil Ölçeği")
        imgui.same_line(150)
        imgui.push_item_width(-1)
        changed, new_val = imgui.slider_float(
            "##scale", self.profile_scale, 0.3, 3.0, f"{self.profile_scale:.2f}x"
        )
        if changed:
            self.profile_scale = new_val
            self._apply()
        imgui.pop_item_width()

        # Çizgi kalınlığı
        imgui.text("Çizgi Kalınlığı")
        imgui.same_line(150)
        imgui.push_item_width(-1)
        changed, new_val = imgui.slider_float(
            "##lw", self.line_width, 1.0, 5.0, f"{self.line_width:.1f}px"
        )
        if changed:
            self.line_width = new_val
            self._apply()
        imgui.pop_item_width()

        # Dolgu alpha
        imgui.text("Dolgu Şeffaflığı")
        imgui.same_line(150)
        imgui.push_item_width(-1)
        changed, new_val = imgui.slider_float(
            "##alpha", self.fill_alpha, 0.0, 1.0, f"{self.fill_alpha:.2f}"
        )
        if changed:
            self.fill_alpha = new_val
            self._apply()
        imgui.pop_item_width()

        # Oklar / dolgu
        imgui.spacing()
        changed, self.show_arrows = imgui.checkbox("Okları Göster", self.show_arrows)
        if changed:
            self._apply()

        imgui.same_line()
        changed, self.show_fill = imgui.checkbox("Dolguyu Göster", self.show_fill)
        if changed:
            self._apply()

    # ------------------------------------------------------------------
    # 5. TEMİZLEME
    # ------------------------------------------------------------------
    def _draw_clear_section(self):
        imgui.text_colored("Yük Temizleme", 1.0, 0.6, 0.5, 1.0)
        imgui.spacing()

        # Temizlenecek pattern seçimi
        items = ["<Seçili pattern>"] + self.available_patterns
        if not self.available_patterns:
            imgui.text_colored("(Pattern yok)", 0.6, 0.6, 0.6, 1.0)
            return

        imgui.push_item_width(-1)
        changed, new_idx = imgui.combo("##clear_pat", self.clear_pattern_combo_idx, items)
        if changed:
            self.clear_pattern_combo_idx = new_idx
        imgui.pop_item_width()

        # Seçili pattern
        if self.clear_pattern_combo_idx == 0:
            pattern_to_clear = self.active_pattern
        else:
            pattern_to_clear = self.available_patterns[self.clear_pattern_combo_idx - 1]

        if not pattern_to_clear:
            imgui.text_colored(
                "⚠ Önce bir pattern seçin veya listeden seçin",
                1.0, 0.7, 0.4, 1.0
            )
            return

        imgui.spacing()

        # Kaç elemanda bu pattern var?
        count = self._count_pattern_usage(pattern_to_clear)
        imgui.text_colored(
            f"'{pattern_to_clear}' → {count} elemanda var",
            0.7, 0.85, 0.9, 1.0
        )

        imgui.spacing()
        avail = imgui.get_content_region_available_width()

        # Seçili elemlerden temizle
        imgui.push_style_color(imgui.COLOR_BUTTON, 0.65, 0.30, 0.30, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.80, 0.40, 0.40, 1.0)
        if imgui.button("Seçili Elemanlardan Sil", width=-1):
            if callable(self.on_clear_loads):
                n = self.on_clear_loads(pattern_to_clear)
                self._refresh_patterns()
        imgui.pop_style_color(2)

        # Tüm sahneden temizle
        imgui.push_style_color(imgui.COLOR_BUTTON, 0.55, 0.20, 0.20, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.70, 0.28, 0.28, 1.0)
        if imgui.button("Tüm Sahneden Sil", width=-1):
            if imgui.is_item_hovered():
                imgui.set_tooltip("Bu pattern'ı tüm frame'lerden kaldırır")
            if callable(self.on_clear_all):
                n = self.on_clear_all(pattern_to_clear)
                self._refresh_patterns()
        imgui.pop_style_color(2)

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------
    def _refresh_patterns(self):
        """Sahnedeki pattern'ları yeniden topla."""
        if not self.scene:
            self.available_patterns = []
            return

        pats: Set[str] = set()
        for f in self.scene.frames.values():
            sets = getattr(f, "dist_load_sets", None)
            if sets:
                pats.update(sets.keys())
            # Fallback: ham dist_loads
            for dl in getattr(f, "dist_loads", []) or []:
                p = getattr(dl, "pattern_name", None)
                if p:
                    pats.add(p)

        self.available_patterns = sorted(pats)
        self._pattern_signature = tuple(self.available_patterns)

        # Aktif pattern artık yoksa sıfırla
        if self.active_pattern and self.active_pattern not in self.available_patterns:
            self.active_pattern = None

        # Combo index sınırla
        max_idx = len(self.available_patterns)
        if self.clear_pattern_combo_idx > max_idx:
            self.clear_pattern_combo_idx = 0

    def _count_pattern_usage(self, pattern: str) -> int:
        """Sahnedeki kaç elemanda bu pattern var."""
        if not self.scene or not pattern:
            return 0
        count = 0
        for f in self.scene.frames.values():
            if pattern in (getattr(f, "dist_load_sets", {}) or {}):
                count += 1
        return count

    def _apply(self):
        """Renderer'a tüm ayarları uygula."""
        if self.renderer:
            lr = getattr(self.renderer, "load_renderer", None)
            if lr:
                lr.enabled = self.show_loads
                lr.active_pattern = self.active_pattern
                # Yeni özellikler
                if hasattr(lr, "profile_scale"):
                    lr.profile_scale = self.profile_scale
                if hasattr(lr, "line_width"):
                    lr.line_width = self.line_width
                if hasattr(lr, "fill_alpha"):
                    lr.fill_alpha = self.fill_alpha
                if hasattr(lr, "show_arrows"):
                    lr.show_arrows = self.show_arrows
                if hasattr(lr, "show_fill"):
                    lr.show_fill = self.show_fill

        # Sahneyi kirli işaretle → yeniden çizilecek
        if self.scene:
            self.scene.mark_dirty()
            if self.renderer and hasattr(self.renderer, "load_renderer"):
                try:
                    self.renderer.load_renderer.update(self.scene, camera_scale=1.0)
                except Exception:
                    pass

        # Dış callback
        if callable(self.on_change):
            self.on_change()