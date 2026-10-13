# ui/zones_panel.py
"""
ZonesPanel — Sahnedeki rüzgar bölgelerini ve çoklu rüzgar yönlerini yönetir.

BasePanel'den türer. Sadece draw_content() yazar.
"""
import imgui
from ui.base_panel import BasePanel


class ZonesPanel(BasePanel):

    def __init__(self, on_run_analysis=None, on_select_direction=None):
        super().__init__(
            title="Rüzgar Bölgeleri ve Yönleri",
            width=400,
            height=600,
            pos_first_use=(480, 40),
            closable=True,
        )
        self.scene = None
        self.wind_analysis_ref = None  # WindAnalysisResult referansı
        self.on_run_analysis = on_run_analysis
        self.on_select_direction = on_select_direction
        self._open_groups: set = set()
        self._filter = ""
        
        # Geçici metin tamponları (ImGui input_text için)
        self._dir_buffers = {}

    def open(self, scene=None, wind_analysis=None):
        if scene is not None:
            self.scene = scene
        if wind_analysis is not None:
            self.wind_analysis_ref = wind_analysis
        super().open()

    def close(self):
        super().close()
        self._open_groups.clear()

    def draw_content(self):
        # --- ÜST: Rüzgar Yönleri Yönetim Bölümü ---
        expanded = imgui.collapsing_header("Rüzgar Yönleri (Multi-Direction)", True)[0]
        if expanded:
            self._draw_wind_directions_manager()
            imgui.separator()

        # --- ORTA: Analiz Çalıştırma ve İstatistik ---
        if imgui.button("Tüm Yönler İçin Rüzgar Analizi Çalıştır", width=-1):
            if callable(self.on_run_analysis):
                self.on_run_analysis()

        imgui.spacing()
        zones = self._collect_zones()
        imgui.text_colored(f"Aktif Gösterilen Bölge Sayısı: {len(zones)}", 0.7, 0.9, 0.7, 1.0)

        imgui.separator()

        # --- FİLTRE ---
        imgui.push_item_width(-1)
        self._filter = imgui.input_text(
            "##zfilter", self._filter, 128,
            imgui.INPUT_TEXT_ENTER_RETURNS_TRUE,
        )[1]
        imgui.pop_item_width()

        imgui.separator()

        # --- LİSTE ---
        imgui.begin_child("zones_list", height=0, border=False)

        if not zones:
            imgui.spacing()
            imgui.text_colored("Rüzgar bölgesi bulunamadı.", 0.5, 0.5, 0.5, 1.0)
            imgui.spacing()
            imgui.text_colored("Yukarıdan analiz çalıştırarak bölgeleri oluşturun.", 0.7, 0.7, 0.7, 1.0)
        else:
            self._draw_zones(zones)

        imgui.end_child()

    def _draw_wind_directions_manager(self):
        """Çoklu rüzgar yönlerinin listelendiği, eklendiği ve seçildiği tatlı mimari."""
        if not self.wind_analysis_ref:
            imgui.text_colored("Rüzgar analiz yöneticisi bağlı değil.", 0.9, 0.5, 0.5, 1.0)
            return

        # Eğer henüz hiç yön yoksa varsayılan 4 ana yönü ekle
        if not hasattr(self.wind_analysis_ref, "directions_list") or not self.wind_analysis_ref.directions_list:
            self.wind_analysis_ref.directions_list = [
                [1.0, 0.0, 0.0],   # X+
                [-1.0, 0.0, 0.0],  # X-
                [0.0, 1.0, 0.0],   # Y+
                [0.0, -1.0, 0.0]   # Y-
            ]

        directions = self.wind_analysis_ref.directions_list
        active_dir = getattr(self.wind_analysis_ref, "active_direction", None)

        imgui.text_colored("Analize dahil edilecek rüzgar yönü vektörleri:", 0.8, 0.8, 0.8, 1.0)
        imgui.spacing()

        to_remove = -1
        for i, d_vec in enumerate(directions):
            vec_str = f"{d_vec[0]}, {d_vec[1]}, {d_vec[2]}"
            buf_key = f"dir_buf_{i}"
            if buf_key not in self._dir_buffers:
                self._dir_buffers[buf_key] = vec_str

            imgui.push_item_width(180)
            changed, new_val = imgui.input_text(f"##dir_{i}", self._dir_buffers[buf_key], 64)
            if changed:
                self._dir_buffers[buf_key] = new_val
                # Metni parse etmeye çalış [x, y, z]
                try:
                    parts = [float(p.strip()) for p in new_val.replace("[", "").replace("]", "").split(",")]
                    if len(parts) == 3:
                        directions[i] = parts
                except ValueError:
                    pass
            imgui.pop_item_width()

            imgui.same_line()
            
            # Aktif Görselleştirme Seçim Butonu (Radyo tarzı)
            is_active = (active_dir == tuple(d_vec))
            btn_label = "Gösteriliyor" if is_active else "Sahneye Yansıt##" + str(i)
            if is_active:
                imgui.push_style_color(imgui.COLOR_BUTTON, 0.2, 0.6, 0.3, 1.0)
            
            if imgui.button(btn_label):
                self.wind_analysis_ref.active_direction = tuple(d_vec)
                if callable(self.on_select_direction):
                    self.on_select_direction(tuple(d_vec))
            
            if is_active:
                imgui.pop_style_color(1)

            # Silme butonu (en az 1 tane kalmalı)
            if len(directions) > 1:
                imgui.same_line()
                if imgui.button(f"Sil##{i}"):
                    to_remove = i

        if to_remove != -1:
            directions.pop(to_remove)

        imgui.spacing()
        # + Yeni Yön Ekle Butonu
        if imgui.button("+ Yeni Rüzgar Yönü Ekle", width=-1):
            directions.append([0.0, 1.0, 0.0])  # Varsayılan yeni yön

    # ------------------------------------------------------------------
    def _collect_zones(self):
        if not self.scene:
            return []
        zones = []
        for poly in self.scene.polygons.values():
            wp = getattr(poly, "windplane", None)
            if wp and isinstance(wp, dict) and len(wp) > 0:
                zones.append((poly, wp))
        return zones

    def _draw_zones(self, zones):
        for poly, wp in zones:
            label = wp.get("label", "") or f"Polygon #{poly.unique_id}"

            if self._filter:
                f = self._filter.lower()
                if f not in label.lower() and f not in str(poly.unique_id):
                    continue

            key = f"zone_{poly.unique_id}"
            is_open = key in self._open_groups

            arrow = self.ascii_arrow(is_open)
            header = f"{arrow}  {label}  (#{poly.unique_id})##{key}"

            clicked = imgui.selectable(header, False)[0]
            if clicked:
                if is_open:
                    self._open_groups.discard(key)
                else:
                    self._open_groups.add(key)
                is_open = not is_open

            if is_open:
                imgui.indent(20)
                self._draw_zone_detail(wp)
                imgui.unindent(20)

    def _draw_zone_detail(self, wp):
        priority_keys = ["label", "surface", "table_type", "pitch", "q_p"]
        for k in priority_keys:
            if k in wp:
                self._draw_kv(k, wp[k])
        for k, v in wp.items():
            if k in priority_keys:
                continue
            self._draw_kv(k, v)

    def _draw_kv(self, key, val):
        if val is None:
            text, color = "-", (0.5, 0.5, 0.5, 1.0)
        elif isinstance(val, bool):
            text = "True" if val else "False"
            color = (0.4, 0.9, 0.5, 1.0) if val else (0.9, 0.5, 0.5, 1.0)
        elif isinstance(val, (int, float)):
            text, color = f"{val:.4g}", (0.9, 0.85, 0.5, 1.0)
        elif isinstance(val, str):
            text, color = (val or '""'), (0.85, 0.85, 0.85, 1.0)
        elif isinstance(val, (list, tuple)):
            parts = [f"{v:.3f}" if isinstance(v, float) else str(v) for v in val]
            text, color = "[" + ", ".join(parts) + "]", (0.7, 0.85, 0.95, 1.0)
        else:
            text, color = str(val), (0.85, 0.85, 0.85, 1.0)

        imgui.text_colored(f"{key}: ", 0.6, 0.6, 0.7, 1.0)
        imgui.same_line()
        imgui.text_colored(text, *color)