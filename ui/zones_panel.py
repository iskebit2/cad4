# ui/zones_panel.py
"""
ZonesPanel — Rüzgar bölgeleri, yönleri ve yük tablosu.
WindAnalysisResult yapısı:
    result.directions: Dict[str, WindDirectionResult]
    result.active_direction: Optional[Tuple[float, float, float]]
WindDirectionResult:
    w_dir: Tuple[float, float, float]
"""
from logging_config import CadLogger
import imgui
from ui.base_panel import BasePanel
from domain.definition import WindDirectionResult

logger = CadLogger.get(__name__)


class ZonesPanel(BasePanel):

    ROW_HEIGHT = 24
    VISIBLE_ROWS = 8

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
        self.use_cpe1 = False
        self._last_distributed = 0
        self._dist_type = "one_way"

        self._zones_cache = None
        self._zones_cache_frame = -1

    # ------------------------------------------------------------------
    def open(self, scene=None, wind_analysis=None):
        if scene is not None:
            self.scene = scene
            self._invalidate_zones_cache()
        if wind_analysis is not None:
            self.wind_analysis_ref = wind_analysis
        super().open()

    def close(self):
        super().close()

    def _invalidate_zones_cache(self):
        self._zones_cache = None
        self._zones_cache_frame = -1

    # ------------------------------------------------------------------
    # WindAnalysisResult erişim yardımcıları
    # ------------------------------------------------------------------
    def _get_directions_dict(self) -> dict:
        """WindAnalysisResult.directions dict'ini döndürür."""
        ref = self.wind_analysis_ref
        if ref is None:
            return {}
        if isinstance(ref, dict):
            return ref.get("directions", {}) or {}
        return getattr(ref, "directions", {}) or {}

    def _get_active_direction(self):
        ref = self.wind_analysis_ref
        if ref is None:
            return None
        if isinstance(ref, dict):
            return ref.get("active_direction")
        return getattr(ref, "active_direction", None)

    def _set_active_direction(self, vec):
        ref = self.wind_analysis_ref
        if ref is None:
            return
        if isinstance(ref, dict):
            ref["active_direction"] = vec
        else:
            ref.active_direction = vec

    @staticmethod
    def _wdr_vector(wdr) -> tuple:
        """WindDirectionResult.w_dir → (x, y, z)."""
        if wdr is None:
            return (0.0, 0.0, 0.0)
        v = getattr(wdr, "w_dir", None)
        if v is None and isinstance(wdr, dict):
            v = wdr.get("w_dir")
        if v is None:
            return (0.0, 0.0, 0.0)
        return (float(v[0]), float(v[1]), float(v[2]))

    @staticmethod
    def _set_wdr_vector(wdr, vec):
        """WindDirectionResult.w_dir'i güncelle."""
        if wdr is None:
            return
        if hasattr(wdr, "w_dir"):
            wdr.w_dir = tuple(vec)
        elif isinstance(wdr, dict):
            wdr["w_dir"] = tuple(vec)

    # ------------------------------------------------------------------
    def draw_content(self):
        self._draw_wind_directions()
        imgui.separator()
        self._draw_analysis_controls()
        imgui.separator()
        self._draw_zone_table()
        imgui.separator()
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

        directions_dict = self._get_directions_dict()
        if not directions_dict:
            imgui.text_colored("Yön bulunamadı. Analizi çalıştırın.",
                               0.7, 0.7, 0.7, 1.0)
            return

        active_dir = self._get_active_direction()
        keys = sorted(directions_dict.keys())

        remove_key = None

        for key in keys:
            wdr = directions_dict[key]
            vec = self._wdr_vector(wdr)

            imgui.push_id(f"dir_{key}")

            # Key etiketi
            imgui.text_colored(f"{key}", 0.5, 0.7, 0.9, 1.0)
            imgui.same_line()

            # Vektör input
            imgui.push_item_width(180)
            buf_key = f"dir_buf_{key}"
            if buf_key not in self._dir_buffers:
                self._dir_buffers[buf_key] = f"{vec[0]}, {vec[1]}, {vec[2]}"
            changed, new_val = imgui.input_text("##dir", self._dir_buffers[buf_key], 64)
            if changed:
                self._dir_buffers[buf_key] = new_val
                try:
                    parts = [float(p.strip()) for p in
                             new_val.replace("[", "").replace("]", "").split(",")]
                    if len(parts) == 3:
                        self._set_wdr_vector(wdr, parts)
                except ValueError:
                    pass
            imgui.pop_item_width()

            imgui.same_line()

            # Aktif yön butonu
            is_active = (active_dir == vec)
            if is_active:
                imgui.push_style_color(imgui.COLOR_BUTTON, 0.2, 0.6, 0.3, 1.0)
            if imgui.button("Gösteriliyor" if is_active else "Sahneye Yansıt"):
                self._set_active_direction(vec)
                if callable(self.on_select_direction):
                    self.on_select_direction(vec)
            if is_active:
                imgui.pop_style_color(1)

            # Silme
            if len(keys) > 1:
                imgui.same_line()
                if imgui.small_button(f"X##del_{key}"):
                    remove_key = key

            imgui.pop_id()

        # Silme işlemini döngü dışında yap
        if remove_key is not None:
            directions_dict.pop(remove_key, None)
            self._dir_buffers.clear()

        if imgui.button("+ Yön Ekle", width=120):
            # Yeni anahtar üret (sayısal key'ler için)
            existing_nums = []
            for k in directions_dict.keys():
                try:
                    existing_nums.append(int(k))
                except (ValueError, TypeError):
                    pass
            next_num = max(existing_nums, default=0) + 1
            new_key = f"{next_num:02d}"
            # Yeni WindDirectionResult oluştur
            try:
                
                directions_dict[new_key] = WindDirectionResult(w_dir=(0.0, 1.0, 0.0))
            except ImportError:
                logger.warning("[ZonesPanel] WindDirectionResult import edilemedi, dict fallback")
                directions_dict[new_key] = {"w_dir": (0.0, 1.0, 0.0)}
            self._dir_buffers.clear()

    # ------------------------------------------------------------------
    # 2. ANALİZ + KIND
    # ------------------------------------------------------------------
    def _draw_analysis_controls(self):
        if imgui.button("Rüzgar Analizi Çalıştır", width=220, height=32):
            if callable(self.on_run_analysis):
                try:
                    self.on_run_analysis()
                    self._invalidate_zones_cache()
                except Exception:
                    logger.exception("[ZonesPanel] Analiz hatası")

        imgui.same_line(260)

        imgui.text("Yüzey Tipi:")
        imgui.same_line()

        if imgui.radio_button("CPE10 (10 m²)", not self.use_cpe1):
            self.use_cpe1 = False
            self._invalidate_zones_cache()

        imgui.same_line()

        if imgui.radio_button("CPE1 (1 m²)", self.use_cpe1):
            self.use_cpe1 = True
            self._invalidate_zones_cache()

        imgui.same_line(560)
        zones = self._collect_zones()
        imgui.text_colored(f"Zone: {len(zones)}", 0.6, 0.85, 0.6, 1.0)

    # ------------------------------------------------------------------
    # 3. TABLO
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

        flags = (
            imgui.TABLE_BORDERS
            | imgui.TABLE_ROW_BACKGROUND
            | imgui.TABLE_RESIZABLE
            | imgui.TABLE_SIZING_STRETCH_PROP
            | imgui.TABLE_SCROLL_Y
        )
        col_count = 12
        table_height = self.ROW_HEIGHT * self.VISIBLE_ROWS + 30

        if not imgui.begin_table("zone_table", col_count, flags,
                                 outer_size_height=table_height):
            return

        headers = [
            ("Bölge", 120), ("Yüzey", 70), ("Tablo", 100), ("Eğim", 60),
            ("cpe_min", 80), ("cpe_max", 80), ("q_p", 70),
            ("F_MN_P", 80), ("F_MN_M", 80), ("F_MX_P", 80), ("F_MX_M", 80),
            ("Pattern", 200),
        ]

        for idx, (name, w) in enumerate(headers):
            col_flags = imgui.TABLE_COLUMN_WIDTH_FIXED if idx != 11 else 0
            imgui.table_setup_column(name, col_flags, w)
        imgui.table_headers_row()

        cpi_pos = 0.2
        cpi_neg = -0.3

        for poly in zones:
            wp = getattr(poly, "windplane", {}) or {}
            label = wp.get("label", "") or poly.label
            surface = wp.get("surface", "-")
            table_type = wp.get("table_type", "-")
            pitch = wp.get("pitch", 0.0)
            q_p = float(wp.get("q_p", 0.0))

            if kind == "CPE10":
                cpe_raw = wp.get("cpe10", [0.0, 0.0])
            else:
                cpe_raw = wp.get("cpe1", [0.0, 0.0])

            if isinstance(cpe_raw, (tuple, list)):
                cpe_min = float(cpe_raw[0]) if len(cpe_raw) > 0 else 0.0
                cpe_max = float(cpe_raw[1]) if len(cpe_raw) > 1 else cpe_min
            else:
                cpe_min = cpe_max = float(cpe_raw)

            f_mn_p = q_p * (cpe_min - cpi_pos)
            f_mn_m = q_p * (cpe_min - cpi_neg)
            f_mx_p = q_p * (cpe_max - cpi_pos)
            f_mx_m = q_p * (cpe_max - cpi_neg)

            dir_idx = int(wp.get("dir_idx", 1))
            pattern_mn = f"WIND_{dir_idx:02d}_{kind}_MN_P"
            pattern_mx = f"WIND_{dir_idx:02d}_{kind}_MX_P"

            imgui.table_next_row()

            imgui.table_next_column(); imgui.text_colored(label, 0.85, 0.85, 0.5, 1.0)
            imgui.table_next_column(); imgui.text(str(surface))
            imgui.table_next_column(); imgui.text(str(table_type))
            imgui.table_next_column(); imgui.text(f"{pitch:.2f}")

            imgui.table_next_column()
            c = (0.9, 0.4, 0.4, 1.0) if cpe_min < 0 else (0.4, 0.9, 0.4, 1.0)
            imgui.text_colored(f"{cpe_min:.3f}", *c)

            imgui.table_next_column()
            if abs(cpe_max) < 1e-9:
                imgui.text_colored("0.000", 0.5, 0.5, 0.5, 1.0)
            else:
                c = (0.9, 0.4, 0.4, 1.0) if cpe_max < 0 else (0.4, 0.9, 0.4, 1.0)
                imgui.text_colored(f"{cpe_max:.3f}", *c)

            imgui.table_next_column(); imgui.text(f"{q_p:.3f}")

            imgui.table_next_column()
            imgui.text_colored(f"{f_mn_p:+.3f}", *self._force_color(f_mn_p))
            imgui.table_next_column()
            imgui.text_colored(f"{f_mn_m:+.3f}", *self._force_color(f_mn_m))

            imgui.table_next_column()
            if abs(cpe_max) < 1e-9:
                imgui.text_colored("-", 0.4, 0.4, 0.4, 1.0)
            else:
                imgui.text_colored(f"{f_mx_p:+.3f}", *self._force_color(f_mx_p))

            imgui.table_next_column()
            if abs(cpe_max) < 1e-9:
                imgui.text_colored("-", 0.4, 0.4, 0.4, 1.0)
            else:
                imgui.text_colored(f"{f_mx_m:+.3f}", *self._force_color(f_mx_m))

            imgui.table_next_column()
            if abs(cpe_max) < 1e-9:
                imgui.text_colored(pattern_mn, 0.6, 0.8, 0.9, 1.0)
            else:
                imgui.text_colored(f"{pattern_mn} / {pattern_mx}",
                                   0.6, 0.8, 0.9, 1.0)

        imgui.end_table()

    def _force_color(self, val):
        if abs(val) < 1e-9:
            return (0.5, 0.5, 0.5, 1.0)
        if val < 0:
            return (0.5, 0.7, 0.95, 1.0)
        return (0.95, 0.55, 0.4, 1.0)

    # ------------------------------------------------------------------
    # 4. DAĞITIM
    # ------------------------------------------------------------------
    def _draw_distribute_controls(self):
        zones = self._collect_zones()
        if not zones:
            return

        kind = "CPE1" if self.use_cpe1 else "CPE10"

        if imgui.button("  Frame'lere Dağıt  ", width=200, height=34):
            if callable(self.on_distribute):
                try:
                    n = self.on_distribute(kind, self._dist_type)
                    self._last_distributed = n or 0
                except Exception:
                    logger.exception("[ZonesPanel] Dağıtım hatası")
                    self._last_distributed = -1

        imgui.same_line()
        imgui.text_colored(
            f"KIND: {kind}   |   Zone: {len(zones)}   |   Tip: {self._dist_type}",
            0.6, 0.8, 0.9, 1.0,
        )

        if self._last_distributed > 0:
            imgui.same_line(500)
            imgui.text_colored(
                f"✓ Son dağıtım: {self._last_distributed} segment",
                0.4, 0.9, 0.5, 1.0,
            )
        elif self._last_distributed == -1:
            imgui.same_line(500)
            imgui.text_colored("✗ Dağıtım hatası (log'a bak)",
                               0.9, 0.4, 0.4, 1.0)

    # ------------------------------------------------------------------
    def _collect_zones(self):
        try:
            current_frame = imgui.get_frame_count()
        except Exception:
            current_frame = -1

        if current_frame != -1 and self._zones_cache_frame == current_frame:
            return self._zones_cache

        zones = []
        if self.scene:
            for poly in self.scene.polygons.values():
                wp = getattr(poly, "windplane", None)
                if not wp or not isinstance(wp, dict) or len(wp) == 0:
                    continue
                pt = getattr(poly, "poly_type", None)
                is_zone = False
                if pt is not None and hasattr(pt, "name") and pt.name == "ZONE":
                    is_zone = True
                elif "ZONE" in (poly.label or "").upper():
                    is_zone = True
                if is_zone:
                    zones.append(poly)

        self._zones_cache = zones
        self._zones_cache_frame = current_frame
        return zones