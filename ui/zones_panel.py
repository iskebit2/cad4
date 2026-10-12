# ui/zones_panel.py
"""
ZonesPanel — Sahnedeki rüzgar bölgelerini listeler.

BasePanel'den türer. Sadece draw_content() yazar.
"""
import imgui

from ui.base_panel import BasePanel


class ZonesPanel(BasePanel):

    def __init__(self, on_run_analysis=None):
        super().__init__(
            title="Rüzgar Bölgeleri",
            width=380,
            height=520,
            pos_first_use=(480, 40),      # sol tarafta
            closable=True,
        )
        self.scene = None
        self.on_run_analysis = on_run_analysis
        self._open_groups: set = set()
        self._filter = ""

    # ------------------------------------------------------------------
    # Base'in open()'ını genişlet — scene ver
    # ------------------------------------------------------------------
    def open(self, scene=None):
        if scene is not None:
            self.scene = scene
        super().open()

    def close(self):
        super().close()
        self._open_groups.clear()

    # ------------------------------------------------------------------
    # İçerik
    # ------------------------------------------------------------------
    def draw_content(self):
        # --- Üst: Araç çubuğu ---
        if imgui.button("Rüzgar Analizi Çalıştır"):
            if callable(self.on_run_analysis):
                self.on_run_analysis()
        imgui.same_line()

        zones = self._collect_zones()
        imgui.text_colored(f"{len(zones)} bölge", 0.7, 0.9, 0.7, 1.0)

        imgui.separator()

        # --- Filtre ---
        imgui.push_item_width(-1)
        self._filter = imgui.input_text(
            "##zfilter", self._filter, 128,
            imgui.INPUT_TEXT_ENTER_RETURNS_TRUE,
        )[1]
        imgui.pop_item_width()

        imgui.separator()

        # --- Liste ---
        imgui.begin_child("zones_list", height=0, border=False)

        if not zones:
            imgui.spacing()
            imgui.text_colored("Rüzgar bölgesi yok", 0.5, 0.5, 0.5, 1.0)
            imgui.spacing()
            imgui.text_colored("Analiz çalıştırarak bölge oluştur.",
                               0.7, 0.7, 0.7, 1.0)
        else:
            self._draw_zones(zones)

        imgui.end_child()

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

            # Base'in ascii_arrow yardımcısı
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
        priority_keys = ["label", "surface", "table_type", "pitch"]
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