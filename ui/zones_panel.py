# ui/zones_panel.py
"""
ZonesPanel — Rüzgar bölgeleri, yönleri ve yük tablosu.
WindAnalysisResult yapısı:
    result.directions: Dict[str, WindDirectionResult]
    result.active_direction: Optional[Tuple[float, float, float]]
WindDirectionResult:
    w_dir: Tuple[float, float, float]
"""
from imgui_bundle import imgui
import numpy as np

from domain.definition import WindDirectionResult
from logging_config import CadLogger
from ui.base_panel import BasePanel

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
        self.project = None
        self.wind_analysis_ref = None
        self.on_run_analysis = on_run_analysis
        self.on_select_direction = on_select_direction
        self.on_distribute = on_distribute

        self._dir_buffers = {}
        self.use_cpe1 = False
        self._last_distributed = 0
        self._dist_type = "one_way"

        self._zones_cache = None
        self._zones_cache_key = None

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
        self._zones_cache_key = None

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
        self._draw_zone_preview()
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
            imgui.text_colored(imgui.ImVec4(0.9, 0.5, 0.5, 1.0), 'Rüzgar analiz yöneticisi bağlı değil.')

            return

        directions_dict = self._get_directions_dict()
        if not directions_dict:
            imgui.text_colored(imgui.ImVec4(0.7, 0.7, 0.7, 1.0), 'Yön bulunamadı. Analizi çalıştırın.')

            return

        active_dir = self._get_active_direction()
        keys = sorted(directions_dict.keys())

        remove_key = None

        for key in keys:
            wdr = directions_dict[key]
            vec = self._wdr_vector(wdr)

            imgui.push_id(f"dir_{key}")

            # Key etiketi
            imgui.text_colored(imgui.ImVec4(0.5, 0.7, 0.9, 1.0), f'{key}')
            imgui.same_line()

            # Vektör input
            imgui.push_item_width(180)
            buf_key = f"dir_buf_{key}"
            if buf_key not in self._dir_buffers:
                self._dir_buffers[buf_key] = f"{vec[0]}, {vec[1]}, {vec[2]}"
            changed, new_val = imgui.input_text(
                "##dir", self._dir_buffers[buf_key]
            )
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
                imgui.push_style_color(
                    imgui.Col_.button, imgui.ImVec4(0.2, 0.6, 0.3, 1.0)
                )
            if imgui.button("Gösteriliyor" if is_active else "Önizle"):
                self._set_active_direction(vec)
                self._invalidate_zones_cache()
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

        if imgui.button("+ Yön Ekle", imgui.ImVec2(120, 0)):
            # Yeni anahtar üret (sayısal key'ler için)
            existing_nums = []
            for k in directions_dict:
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
        if imgui.button("Rüzgar Analizi Çalıştır", imgui.ImVec2(220, 32)):
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
        imgui.text_colored(imgui.ImVec4(0.6, 0.85, 0.6, 1.0), f'Zone: {len(zones)}')

    # ------------------------------------------------------------------
    # 3. TABLO
    # ------------------------------------------------------------------
    def _draw_zone_table(self):
        zones = self._collect_zones()
        if not zones:
            imgui.spacing()
            imgui.text_colored(imgui.ImVec4(0.5, 0.5, 0.5, 1.0), 'Zone bulunamadı.')
            imgui.spacing()
            imgui.text_colored(imgui.ImVec4(0.7, 0.7, 0.7, 1.0), "Analizi çalıştırarak zone'ları oluşturun.")

            return

        kind = "CPE1" if self.use_cpe1 else "CPE10"

        flags = (
            imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
            | imgui.TableFlags_.resizable
            | imgui.TableFlags_.sizing_stretch_prop
            | imgui.TableFlags_.scroll_y
        )
        col_count = 12
        table_height = self.ROW_HEIGHT * self.VISIBLE_ROWS + 30

        if not imgui.begin_table(
            "zone_table", col_count, flags,
            outer_size=imgui.ImVec2(0, table_height),
        ):
            return

        headers = [
            ("Bölge", 120), ("Yüzey", 70), ("Tablo", 100), ("Eğim", 60),
            ("cpe_min", 80), ("cpe_max", 80), ("q_p", 70),
            ("F_MN_P", 80), ("F_MN_M", 80), ("F_MX_P", 80), ("F_MX_M", 80),
            ("Pattern", 200),
        ]

        for idx, (name, w) in enumerate(headers):
            col_flags = imgui.TableColumnFlags_.width_fixed if idx != 11 else 0
            imgui.table_setup_column(name, col_flags, w)
        imgui.table_headers_row()

        cpi_pos = 0.2
        cpi_neg = -0.3
        wind_record = self._active_wind_record()
        q_p = float(self._record_value(wind_record, "q_p", 0.0))
        direction_key = self._active_direction_key()

        for zone in zones:
            label = zone.label
            surface = zone.surface
            table_type = zone.table_type
            pitch = float(zone.pitch)

            cpe_min, cpe_max = self._zone_coefficients(zone, kind)

            f_mn_p = q_p * (cpe_min - cpi_pos)
            f_mn_m = q_p * (cpe_min - cpi_neg)
            f_mx_p = q_p * (cpe_max - cpi_pos)
            f_mx_m = q_p * (cpe_max - cpi_neg)

            dir_idx = int("".join(c for c in direction_key if c.isdigit()) or "1")
            pattern_mn = f"WIND_{dir_idx:02d}_{kind}_MN_P"
            pattern_mx = f"WIND_{dir_idx:02d}_{kind}_MX_P"

            imgui.table_next_row()

            imgui.table_next_column(); imgui.text_colored(imgui.ImVec4(0.85, 0.85, 0.5, 1.0), label)
            imgui.table_next_column(); imgui.text(str(surface))
            imgui.table_next_column(); imgui.text(str(table_type))
            imgui.table_next_column(); imgui.text(f"{pitch:.2f}")

            imgui.table_next_column()
            c = (0.9, 0.4, 0.4, 1.0) if cpe_min < 0 else (0.4, 0.9, 0.4, 1.0)
            imgui.text_colored(imgui.ImVec4(*c), f"{cpe_min:.3f}")

            imgui.table_next_column()
            if abs(cpe_max) < 1e-9:
                imgui.text_colored(imgui.ImVec4(0.5, 0.5, 0.5, 1.0), '0.000')
            else:
                c = (0.9, 0.4, 0.4, 1.0) if cpe_max < 0 else (0.4, 0.9, 0.4, 1.0)
                imgui.text_colored(imgui.ImVec4(*c), f"{cpe_max:.3f}")

            imgui.table_next_column(); imgui.text(f"{q_p:.3f}")

            imgui.table_next_column()
            imgui.text_colored(
                imgui.ImVec4(*self._force_color(f_mn_p)), f"{f_mn_p:+.3f}"
            )
            imgui.table_next_column()
            imgui.text_colored(
                imgui.ImVec4(*self._force_color(f_mn_m)), f"{f_mn_m:+.3f}"
            )

            imgui.table_next_column()
            if abs(cpe_max) < 1e-9:
                imgui.text_colored(imgui.ImVec4(0.4, 0.4, 0.4, 1.0), '-')
            else:
                imgui.text_colored(
                    imgui.ImVec4(*self._force_color(f_mx_p)), f"{f_mx_p:+.3f}"
                )

            imgui.table_next_column()
            if abs(cpe_max) < 1e-9:
                imgui.text_colored(imgui.ImVec4(0.4, 0.4, 0.4, 1.0), '-')
            else:
                imgui.text_colored(
                    imgui.ImVec4(*self._force_color(f_mx_m)), f"{f_mx_m:+.3f}"
                )

            imgui.table_next_column()
            if abs(cpe_max) < 1e-9:
                imgui.text_colored(imgui.ImVec4(0.6, 0.8, 0.9, 1.0), pattern_mn)
            else:
                imgui.text_colored(imgui.ImVec4(0.6, 0.8, 0.9, 1.0), f'{pattern_mn} / {pattern_mx}')


        imgui.end_table()

    def _active_direction_key(self) -> str:
        active = self._get_active_direction()
        if active is None:
            return ""
        active = self._wdr_vector({"w_dir": active})
        for key, record in self._get_directions_dict().items():
            if np.allclose(self._wdr_vector(record), active, atol=1e-8):
                return str(key)
        return ""

    def _active_wind_record(self):
        return self._get_directions_dict().get(self._active_direction_key())

    @staticmethod
    def _record_value(record, name, default=None):
        if isinstance(record, dict):
            return record.get(name, default)
        return getattr(record, name, default)

    @staticmethod
    def _zone_coefficients(zone, kind):
        raw = zone.cpe1 if kind == "CPE1" else zone.cpe10
        if np.isscalar(raw):
            value = float(raw)
            return value, value
        values = tuple(float(value) for value in raw)
        if not values:
            return 0.0, 0.0
        return values[0], values[1] if len(values) > 1 else values[0]

    def _draw_zone_preview(self):
        zones = self._collect_zones()
        imgui.text("Zone görünümü")
        imgui.begin_child(
            "wind_zone_preview",
            imgui.ImVec2(0, 190),
            imgui.ChildFlags_.borders,
        )
        try:
            if not zones:
                imgui.text_disabled("Gösterilecek zone yok.")
                return

            origin = imgui.get_cursor_screen_pos()
            size = imgui.get_content_region_avail()
            canvas_w = max(float(size.x), 1.0)
            canvas_h = max(float(size.y), 1.0)
            imgui.invisible_button(
                "##wind_zone_canvas", imgui.ImVec2(canvas_w, canvas_h)
            )
            draw_list = imgui.get_window_draw_list()

            projected_zones = []
            all_points = []
            for zone in zones:
                coords = np.asarray(zone.coords, dtype=float)
                if coords.ndim != 2 or coords.shape[0] < 3 or coords.shape[1] != 3:
                    continue
                projected = np.column_stack(
                    (coords[:, 0] - coords[:, 1],
                     coords[:, 2] - (coords[:, 0] + coords[:, 1]) * 0.5)
                )
                projected_zones.append((zone, projected))
                all_points.extend(projected)

            if not projected_zones:
                imgui.text_disabled("Çizilebilir zone geometrisi yok.")
                return

            points = np.asarray(all_points, dtype=float)
            mins = points.min(axis=0)
            spans = np.maximum(points.max(axis=0) - mins, 1e-9)
            margin = 14.0
            scale = min(
                max(canvas_w - 2 * margin, 1.0) / spans[0],
                max(canvas_h - 2 * margin, 1.0) / spans[1],
            )
            used_w, used_h = spans * scale
            offset_x = origin.x + (canvas_w - used_w) * 0.5
            offset_y = origin.y + (canvas_h - used_h) * 0.5

            for zone, polygon in projected_zones:
                screen_points = [
                    imgui.ImVec2(
                        offset_x + (point[0] - mins[0]) * scale,
                        offset_y + used_h - (point[1] - mins[1]) * scale,
                    )
                    for point in polygon
                ]
                cpe_min, _ = self._zone_coefficients(zone, "CPE10")
                fill = (
                    imgui.get_color_u32(imgui.ImVec4(0.75, 0.35, 0.30, 0.72))
                    if cpe_min >= 0
                    else imgui.get_color_u32(imgui.ImVec4(0.30, 0.52, 0.78, 0.72))
                )
                outline = imgui.get_color_u32(imgui.ImVec4(0.9, 0.9, 0.9, 1.0))
                draw_list.add_convex_poly_filled(screen_points, fill)
                draw_list.add_polyline(
                    screen_points, outline, imgui.ImDrawFlags_.closed, 1.0
                )
                center = np.mean(polygon, axis=0)
                label_pos = imgui.ImVec2(
                    offset_x + (center[0] - mins[0]) * scale,
                    offset_y + used_h - (center[1] - mins[1]) * scale,
                )
                draw_list.add_text(
                    label_pos, imgui.get_color_u32(imgui.ImVec4(1, 1, 1, 1)),
                    str(zone.label),
                )
        finally:
            imgui.end_child()

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

        if not callable(self.on_distribute):
            imgui.text("Frame'lere dağıtım henüz etkin değil.")
            return

        kind = "CPE1" if self.use_cpe1 else "CPE10"

        if imgui.button(" Frame'lere Dağıt ", imgui.ImVec2(200, 34)):
            if callable(self.on_distribute):
                try:
                    n = self.on_distribute(kind, self._dist_type)
                    self._last_distributed = n or 0
                except Exception:
                    logger.exception("[ZonesPanel] Dağıtım hatası")
                    self._last_distributed = -1

        imgui.same_line()
        imgui.text_colored(imgui.ImVec4(0.6, 0.8, 0.9, 1.0), f'KIND: {kind}   |   Zone: {len(zones)}   |   Tip: {self._dist_type}')




        if self._last_distributed > 0:
            imgui.same_line(500)
            imgui.text_colored(imgui.ImVec4(0.4, 0.9, 0.5, 1.0), f'✓ Son dağıtım: {self._last_distributed} segment')



        elif self._last_distributed == -1:
            imgui.same_line(500)
            imgui.text_colored(imgui.ImVec4(0.9, 0.4, 0.4, 1.0), "✗ Dağıtım hatası (log'a bak)")


    # ------------------------------------------------------------------
    def _collect_zones(self):
        direction_key = self._active_direction_key()
        cache_key = (id(self.project), direction_key)
        if self._zones_cache_key == cache_key:
            return self._zones_cache

        wind_zones = getattr(self.project.loads, "wind_zones", {}) if self.project else {}
        zones = list(wind_zones.get(direction_key, []))

        self._zones_cache = zones
        self._zones_cache_key = cache_key
        return zones