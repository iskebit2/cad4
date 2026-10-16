# ui/zones_panel.py
"""
ZonesPanel — Rüzgar bölgeleri, yönleri ve yük tablosu.
Rapor tarzı tablo: cpe/cpi/qp/kombinasyon/pattern.
"""
import imgui
from ui.base_panel import BasePanel


class ZonesPanel(BasePanel):

    def __init__(self, on_run_analysis=None, on_select_direction=None,
                 on_distribute=None):
        super().__init__(
            title="Rüzgar Bölgeleri ve Yönleri",
            width=900,
            height=620,
            pos_first_use=(200, 60),
            closable=True,
        )
        self.scene = None
        self.wind_analysis_ref = None
        self.on_run_analysis = on_run_analysis
        self.on_select_direction = on_select_direction
        self.on_distribute = on_distribute

        self._dir_buffers = {}
        self.use_cpe1 = False           # CPE10 / CPE1 toggle
        self._sort_spec = (0, 1)        # (column_idx, direction) — varsayılan Bölge ↑
        self._last_distributed = 0

    # ------------------------------------------------------------------
    def open(self, scene=None, wind_analysis=None):
        if scene is not None:
            self.scene = scene
        if wind_analysis is not None:
            self.wind_analysis_ref = wind_analysis
        super().open()

    def close(self):
        super().close()

    # ------------------------------------------------------------------
    def draw_content(self):
        # === ÜST: Yön yönetimi ===
        self._draw_wind_directions()

        imgui.separator()

        # === ORTA ÜST: Analiz + KIND toggle ===
        self._draw_analysis_controls()

        imgui.separator()

        # === ORTA: Yük tablosu ===
        self._draw_zone_table()

        imgui.separator()

        # === ALT: Dağıtım ===
        self._draw_distribute_controls()

    # ------------------------------------------------------------------
    # 1. YÖN YÖNETİMİ
    # ------------------------------------------------------------------
    def _draw_wind_directions(self):
        expanded = imgui.collapsing_header("Rüzgar Yönleri", True)[0]
        if not expanded:
            return

        if not self.wind_analysis_ref:
            imgui.text_colored("Rüzgar analiz yöneticisi bağlı değil.",
                               0.9, 0.5, 0.5, 1.0)
            return

        # Varsayılan yönler
        if not hasattr(self.wind_analysis_ref, "directions_list") or \
                not self.wind_analysis_ref.directions_list:
            self.wind_analysis_ref.directions_list = [
                [1.0, 0.0, 0.0],
                [-1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, -1.0, 0.0],
            ]

        directions = self.wind_analysis_ref.directions_list
        active_dir = getattr(self.wind_analysis_ref, "active_direction", None)

        to_remove = -1
        for i, d_vec in enumerate(directions):
            imgui.push_id(f"dir_{i}")
            imgui.text_colored(f"{i+1:02d}", 0.5, 0.7, 0.9, 1.0)
            imgui.same_line()

            imgui.push_item_width(180)
            buf_key = f"dir_buf_{i}"
            if buf_key not in self._dir_buffers:
                self._dir_buffers[buf_key] = f"{d_vec[0]}, {d_vec[1]}, {d_vec[2]}"
            changed, new_val = imgui.input_text(f"##dir", self._dir_buffers[buf_key], 64)
            if changed:
                self._dir_buffers[buf_key] = new_val
                try:
                    parts = [float(p.strip()) for p in
                             new_val.replace("[", "").replace("]", "").split(",")]
                    if len(parts) == 3:
                        directions[i] = parts
                except ValueError:
                    pass
            imgui.pop_item_width()

            imgui.same_line()
            is_active = (active_dir == tuple(d_vec))
            if is_active:
                imgui.push_style_color(imgui.COLOR_BUTTON, 0.2, 0.6, 0.3, 1.0)
            if imgui.button("Gösteriliyor" if is_active else "Sahneye Yansıt"):
                self.wind_analysis_ref.active_direction = tuple(d_vec)
                if callable(self.on_select_direction):
                    self.on_select_direction(tuple(d_vec))
            if is_active:
                imgui.pop_style_color(1)

            if len(directions) > 1:
                imgui.same_line()
                if imgui.small_button("X"):
                    to_remove = i

            imgui.pop_id()

        if to_remove != -1:
            directions.pop(to_remove)

        if imgui.button("+ Yön Ekle", width=120):
            directions.append([0.0, 1.0, 0.0])

    # ------------------------------------------------------------------
    # 2. ANALİZ + KIND KONTROLLERİ
    # ------------------------------------------------------------------
    def _draw_analysis_controls(self):
        # Sol: Analiz butonu
        if imgui.button("Rüzgar Analizi Çalıştır", width=220, height=32):
            if callable(self.on_run_analysis):
                self.on_run_analysis()

        imgui.same_line(260)

        # Orta: KIND toggle — standalone radio_button (bool döner)
        imgui.text("Yüzey Tipi:")
        imgui.same_line()

        # CPE10 radio
        if imgui.radio_button("CPE10 (10 m²)", not self.use_cpe1):
            self.use_cpe1 = False

        imgui.same_line()

        # CPE1 radio
        if imgui.radio_button("CPE1 (1 m²)", self.use_cpe1):
            self.use_cpe1 = True

        imgui.same_line(560)

        # Sağ: Özet
        zones = self._collect_zones()
        imgui.text_colored(f"Zone: {len(zones)}", 0.6, 0.85, 0.6, 1.0)

    # ------------------------------------------------------------------
    # 3. YÜK TABLOSU
    # ------------------------------------------------------------------
    def _draw_zone_table(self):
        zones = self._collect_zones()
        if not zones:
            imgui.spacing()
            imgui.text_colored("Zone bulunamadı.", 0.5, 0.5, 0.5, 1.0)
            imgui.spacing()
            imgui.text_colored("Analizi çalıştırarak zone'ları oluşturun.",
                            0.7, 0.7, 0.7, 1.0)
            return

        kind = "CPE1" if self.use_cpe1 else "CPE10"

        # Tablo flag'leri
        flags = (
            imgui.TABLE_BORDERS
            | imgui.TABLE_ROW_BACKGROUND
            | imgui.TABLE_RESIZABLE
            | imgui.TABLE_SIZING_STRETCH_PROP
            | imgui.TABLE_SCROLL_Y
        )
        col_count = 12

        if not imgui.begin_table("zone_table", col_count, flags):
            return

        # Kolon başlıkları (sortable)
        headers = [
            ("Bölge", 120),
            ("Yüzey", 70),
            ("Tablo", 100),
            ("Eğim", 60),
            ("cpe_min", 80),
            ("cpe_max", 80),
            ("q_p", 70),
            ("F_MN_P", 80),
            ("F_MN_M", 80),
            ("F_MX_P", 80),
            ("F_MX_M", 80),
            ("Pattern", 200),
        ]

        for idx, (name, w) in enumerate(headers):
            col_flags = imgui.TABLE_COLUMN_WIDTH_FIXED if idx != 11 else 0
            if idx == 11:
                col_flags = 0  # son kolon esnek
            imgui.table_setup_column(name, col_flags, w)
        imgui.table_headers_row()

        # cpi değerleri
        cpi_pos = 0.2
        cpi_neg = -0.3

        # Veri satırları
        for poly in zones:
            wp = getattr(poly, "windplane", {}) or {}

            label = wp.get("label", "") or poly.label
            surface = wp.get("surface", "-")
            table_type = wp.get("table_type", "-")
            pitch = wp.get("pitch", 0.0)
            q_p = float(wp.get("q_p", 0.0))

            # KIND'a göre cpe
            if kind == "CPE10":
                cpe_raw = wp.get("cpe10", [0.0, 0.0])
            else:
                cpe_raw = wp.get("cpe1", [0.0, 0.0])

            if isinstance(cpe_raw, (tuple, list)):
                cpe_min = float(cpe_raw[0]) if len(cpe_raw) > 0 else 0.0
                cpe_max = float(cpe_raw[1]) if len(cpe_raw) > 1 else cpe_min
            else:
                cpe_min = cpe_max = float(cpe_raw)

            # Kombinasyonlar
            f_mn_p = q_p * (cpe_min - cpi_pos)
            f_mn_m = q_p * (cpe_min - cpi_neg)
            f_mx_p = q_p * (cpe_max - cpi_pos)
            f_mx_m = q_p * (cpe_max - cpi_neg)

            # Pattern adı (bu zone'dan üretilen) — MN ve MX için ayrı ayrı
            # Tabloda örnek olarak MN_P pattern'ını gösterelim
            dir_idx = int(wp.get("dir_idx", 1))
            pattern_mn = f"WIND_{dir_idx:02d}_{kind}_MN_P"
            pattern_mx = f"WIND_{dir_idx:02d}_{kind}_MX_P"

            # Satırı çiz
            imgui.table_next_row()

            # Bölge
            imgui.table_next_column()
            imgui.text_colored(label, 0.85, 0.85, 0.5, 1.0)

            # Yüzey
            imgui.table_next_column()
            imgui.text(str(surface))

            # Tablo
            imgui.table_next_column()
            imgui.text(str(table_type))

            # Eğim
            imgui.table_next_column()
            imgui.text(f"{pitch:.2f}")

            # cpe_min
            imgui.table_next_column()
            c = (0.9, 0.4, 0.4, 1.0) if cpe_min < 0 else (0.4, 0.9, 0.4, 1.0)
            imgui.text_colored(f"{cpe_min:.3f}", *c)

            # cpe_max
            imgui.table_next_column()
            if abs(cpe_max) < 1e-9:
                imgui.text_colored("0.000", 0.5, 0.5, 0.5, 1.0)
            else:
                c = (0.9, 0.4, 0.4, 1.0) if cpe_max < 0 else (0.4, 0.9, 0.4, 1.0)
                imgui.text_colored(f"{cpe_max:.3f}", *c)

            # q_p
            imgui.table_next_column()
            imgui.text(f"{q_p:.3f}")

            # F_MN_P
            imgui.table_next_column()
            imgui.text_colored(f"{f_mn_p:+.3f}", *self._force_color(f_mn_p))

            # F_MN_M
            imgui.table_next_column()
            imgui.text_colored(f"{f_mn_m:+.3f}", *self._force_color(f_mn_m))

            # F_MX_P
            imgui.table_next_column()
            if abs(cpe_max) < 1e-9:
                imgui.text_colored("-", 0.4, 0.4, 0.4, 1.0)
            else:
                imgui.text_colored(f"{f_mx_p:+.3f}", *self._force_color(f_mx_p))

            # F_MX_M
            imgui.table_next_column()
            if abs(cpe_max) < 1e-9:
                imgui.text_colored("-", 0.4, 0.4, 0.4, 1.0)
            else:
                imgui.text_colored(f"{f_mx_m:+.3f}", *self._force_color(f_mx_m))

            # Pattern (örnek)
            imgui.table_next_column()
            if abs(cpe_max) < 1e-9:
                # Sadece MN
                imgui.text_colored(pattern_mn, 0.6, 0.8, 0.9, 1.0)
                if imgui.is_item_hovered():
                    imgui.set_tooltip(
                        f"{pattern_mn}\n"
                        f"{pattern_mn.replace('MN_P', 'MN_M')}\n"
                        f"(MX pattern'ları: cpe_max=0)"
                    )
            else:
                imgui.text_colored(f"{pattern_mn} / {pattern_mx}",
                                   0.6, 0.8, 0.9, 1.0)

        imgui.end_table()

    def _force_color(self, val):
        """Yük değerine göre renk: negatif=emme(mavi), pozitif=basınç(kırmızı)."""
        if abs(val) < 1e-9:
            return (0.5, 0.5, 0.5, 1.0)
        if val < 0:
            return (0.5, 0.7, 0.95, 1.0)   # emme → mavi
        return (0.95, 0.55, 0.4, 1.0)      # basınç → turuncu

    # ------------------------------------------------------------------
    # 4. DAĞITIM KONTROLLERİ
    # ------------------------------------------------------------------
    def _draw_distribute_controls(self):
        zones = self._collect_zones()
        if not zones:
            return

        kind = "CPE1" if self.use_cpe1 else "CPE10"

        if imgui.button("  Frame'lere Dağıt  ", width=200, height=34):
            if callable(self.on_distribute):
                n = self.on_distribute(kind)
                self._last_distributed = n or 0

        imgui.same_line()

        imgui.text_colored(
            f"KIND: {kind}   |   Zone: {len(zones)}",
            0.6, 0.8, 0.9, 1.0,
        )

        if self._last_distributed > 0:
            imgui.same_line(500)
            imgui.text_colored(
                f"✓ Son dağıtım: {self._last_distributed} segment",
                0.4, 0.9, 0.5, 1.0,
            )

    # ------------------------------------------------------------------
    # YARDIMCILAR
    # ------------------------------------------------------------------
    def _collect_zones(self):
        if not self.scene:
            return []
        zones = []
        for poly in self.scene.polygons.values():
            wp = getattr(poly, "windplane", None)
            if not wp or not isinstance(wp, dict) or len(wp) == 0:
                continue
            # Sadece zone olanları al
            pt = getattr(poly, "poly_type", None)
            is_zone = False
            if pt is not None and hasattr(pt, "name") and pt.name == "ZONE":
                is_zone = True
            elif "ZONE" in (poly.label or "").upper():
                is_zone = True
            if is_zone:
                zones.append(poly)
        return zones